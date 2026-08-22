"""
Google Gemini AI Provider implementatsiyasi.
SDK: google-genai (yangi, rasmiy)  pip install google-genai
Model: gemini-2.5-flash (settings.GEMINI_MODEL orqali o'zgartiriladi)

FAZA-0 yaxshilanishlari:
  - 503/500 xatolar uchun to'liq ERROR log: user_id, session_id, request_id
  - chat() va chat_stream() log_context parametrini qabul qiladi
  - Retry tugaganda aniq ERROR (exception trace bilan) yoziladi
"""

from __future__ import annotations

import logging
import time
from django.conf import settings

from .base import BaseAIProvider, AIMessage, AIResponse

logger = logging.getLogger(__name__)

RETRYABLE_STATUSES = {500, 503}

def _max_attempts() -> int:
    return getattr(settings, 'AI_MAX_ATTEMPTS', 2)

def _retry_delay() -> float:
    return getattr(settings, 'AI_RETRY_DELAY', 0.5)


def _extract_status(exc: Exception) -> int | None:
    """Exception dan HTTP status code olish (har xil SDK formatlar uchun)."""
    return (
        getattr(exc, 'code', None)
        or getattr(exc, 'status_code', None)
        or getattr(exc, 'status', None)
    )


def _log_retry_warning(method: str, attempt: int, status_code, exc: Exception, wait_s: float) -> None:
    logger.warning(
        'Gemini %s xatosi (attempt %d/%d, status=%s): %s — %.1fs kutib qayta uriniladi',
        method, attempt, _max_attempts(), status_code, exc, wait_s,
    )


def _log_final_error(method: str, attempt: int, status_code, exc: Exception, ctx: dict) -> None:
    """
    Barcha retry tugaganda aniq ERROR yozuv.
    ctx = {'user_id': ..., 'session_id': ..., 'request_id': ...}
    """
    logger.error(
        'Gemini %s: barcha %d urinish MUVAFFAQIYATSIZ. '
        'status=%s | user_id=%s | session_id=%s | request_id=%s | xato: %s',
        method, _max_attempts(),
        status_code,
        ctx.get('user_id', '?'),
        ctx.get('session_id', '?'),
        ctx.get('request_id', '?'),
        exc,
        exc_info=True,
    )


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini API provider — google-genai SDK.
    Tool-calling Claude bilan bir xil interfeys orqali ishlaydi.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model   = model  or settings.GEMINI_MODEL

        from google import genai
        self._client = genai.Client(api_key=self.api_key)
        self._genai  = genai

    def get_model_name(self) -> str:
        return self.model

    def _build_config(self, tools, system, max_tokens):
        """chat() va chat_stream() uchun umumiy config tayyorlash."""
        from google.genai import types

        if max_tokens is None:
            max_tokens = getattr(settings, 'AI_MAX_TOKENS', 4096)

        max_output_cap = getattr(settings, 'AI_MAX_OUTPUT_TOKENS', 400)
        max_output_tokens = min(max_tokens, max_output_cap)

        config_kwargs: dict = {
            'max_output_tokens': max_output_tokens,
            'temperature': getattr(settings, 'AI_TEMPERATURE', 0.2),
        }
        if system:
            config_kwargs['system_instruction'] = system
        if tools:
            config_kwargs['tools'] = [self._convert_tools(tools)]

        return types.GenerateContentConfig(**config_kwargs)

    @staticmethod
    def _format_message_content(content) -> str:
        """
        AIMessage.content string bo'lishi mumkin, yoki services.py'dan
        Claude-uslubidagi tool_result bloklari ro'yxati sifatida kelishi
        mumkin: [{'type': 'tool_result', 'tool_use_id': ..., 'content': ...}, ...]

        Avval bu yerda shunchaki str(content) qilinar edi — natijada model
        Python ro'yxatining xom matn ko'rinishini ("[{'type': 'tool_result', ...}]")
        ko'rar edi, bu token isrofi va tushunish sifatini pasaytiradi.
        Endi tool natijalari o'qiladigan matn ko'rinishida beriladi.
        """
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get('type') == 'tool_result':
                    parts.append(f"[Tool natijasi]\n{block.get('content', '')}")
                else:
                    parts.append(str(block))
            return '\n\n'.join(parts)
        return str(content)

    def _build_contents(self, messages: list[AIMessage]):
        from google.genai import types

        gemini_contents = []
        for msg in messages:
            if msg.role == 'system':
                continue
            role    = 'user' if msg.role == 'user' else 'model'
            content = self._format_message_content(msg.content)
            gemini_contents.append(
                types.Content(role=role, parts=[types.Part(text=content)])
            )
        return gemini_contents

    def chat(
        self,
        messages: list[AIMessage],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
        log_context: dict | None = None,
    ) -> AIResponse:
        """
        log_context = {'user_id': ..., 'session_id': ..., 'request_id': ...}
        503/500 xato bo'lganda bu ma'lumotlar ERROR logga yoziladi.
        """
        ctx = log_context or {}
        gemini_contents = self._build_contents(messages)
        config = self._build_config(tools, system, max_tokens)

        # ── Vaqtinchalik xatolar (500/503) uchun tez, cheklangan retry ──
        last_exc = None
        last_status = None

        max_attempts = _max_attempts()
        for attempt in range(1, max_attempts + 1):
            try:
                response = self._client.models.generate_content(
                    model    = self.model,
                    contents = gemini_contents,
                    config   = config,
                )
                break
            except Exception as e:
                last_exc = e
                last_status = _extract_status(e)
                retryable = last_status in RETRYABLE_STATUSES

                if retryable and attempt < max_attempts:
                    wait_s = _retry_delay() * attempt
                    _log_retry_warning('chat', attempt, last_status, e, wait_s)
                    time.sleep(wait_s)
                    continue

                # Oxirgi urinish yoki retry bo'lmaydigan xato — aniq ERROR
                _log_final_error('chat', attempt, last_status, e, ctx)
                raise

        # Javobni parse qilish
        text_content = ''
        tool_calls   = []

        candidate = response.candidates[0] if response.candidates else None
        if candidate:
            for part in (candidate.content.parts or []):
                if part.text:
                    text_content += part.text
                elif part.function_call:
                    fc = part.function_call
                    tool_calls.append({
                        'id':    f'gemini-{fc.name}',
                        'name':  fc.name,
                        'input': dict(fc.args) if fc.args else {},
                    })

        try:
            tokens_used = (
                response.usage_metadata.prompt_token_count +
                response.usage_metadata.candidates_token_count
            )
        except Exception:
            tokens_used = 0

        return AIResponse(
            content     = text_content,
            tool_calls  = tool_calls,
            tokens_used = tokens_used,
            stop_reason = 'end_turn',
            raw         = response,
        )

    def chat_stream(
        self,
        messages: list[AIMessage],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
        log_context: dict | None = None,
    ):
        """
        HAQIQIY Gemini streaming — generate_content_stream orqali.

        log_context = {'user_id': ..., 'session_id': ..., 'request_id': ...}
        503/500 xato bo'lganda bu ma'lumotlar ERROR logga yoziladi.

        Gemini so'z-so'z javob berayotganda, har bir chunk DARHOL yield
        qilinadi (avvalgi fallback versiyada butun javob kutib olinib,
        keyin sun'iy bo'laklarga bo'lingan edi — bu esa haqiqiy tezlashuv
        bermas edi, faqat vizual effekt edi).

        Tool-call bo'lsa: Gemini odatda function_call'ni bitta yaxlit
        qism sifatida qaytaradi (matn kabi bo'lib-bo'lib kelmaydi).
        Shuning uchun tool_calls faqat oxirgi '__final' event ichida
        to'liq ko'rinadi — chaqiruvchi (services.py) buni chat() bilan
        bir xil tarzda ishlata oladi.
        """
        ctx = log_context or {}
        gemini_contents = self._build_contents(messages)
        config = self._build_config(tools, system, max_tokens)

        last_exc = None
        last_status = None
        max_attempts = _max_attempts()
        for attempt in range(1, max_attempts + 1):
            try:
                text_content = ''
                tool_calls   = []
                usage_meta   = None

                stream = self._client.models.generate_content_stream(
                    model    = self.model,
                    contents = gemini_contents,
                    config   = config,
                )
                for chunk in stream:
                    if not chunk.candidates:
                        continue
                    candidate = chunk.candidates[0]
                    if not candidate.content or not candidate.content.parts:
                        continue
                    for part in candidate.content.parts:
                        if getattr(part, 'text', None):
                            text_content += part.text
                            yield part.text  # ← darhol frontendga uzatiladi
                        elif getattr(part, 'function_call', None):
                            fc = part.function_call
                            tool_calls.append({
                                'id':    f'gemini-{fc.name}',
                                'name':  fc.name,
                                'input': dict(fc.args) if fc.args else {},
                            })
                    if getattr(chunk, 'usage_metadata', None):
                        usage_meta = chunk.usage_metadata

                tokens_used = 0
                if usage_meta:
                    try:
                        tokens_used = (
                            usage_meta.prompt_token_count +
                            usage_meta.candidates_token_count
                        )
                    except Exception:
                        tokens_used = 0

                yield {
                    '__final': True,
                    'tokens_used': tokens_used,
                    'tool_calls': tool_calls,
                    'raw': None,  # streamda yaxlit 'raw' response yo'q
                }
                return

            except Exception as e:
                last_exc = e
                last_status = _extract_status(e)
                retryable = last_status in RETRYABLE_STATUSES

                if retryable and attempt < max_attempts:
                    wait_s = _retry_delay() * attempt
                    _log_retry_warning('stream', attempt, last_status, e, wait_s)
                    time.sleep(wait_s)
                    continue

                # Oxirgi urinish yoki retry bo'lmaydigan xato — aniq ERROR
                _log_final_error('stream', attempt, last_status, e, ctx)
                raise

    @staticmethod
    def _convert_tools(tools: list[dict]):
        """
        Claude tool format → Gemini Tool formatiga o'girish.

        Claude format:
            {'name': '...', 'description': '...', 'input_schema': {...}}

        Gemini format:
            Tool(function_declarations=[FunctionDeclaration(...)])
        """
        from google.genai import types

        declarations = []
        for tool in tools:
            schema = tool.get('input_schema', {})

            properties = {}
            for prop_name, prop_val in schema.get('properties', {}).items():
                prop_type = prop_val.get('type', 'string')
                schema_kwargs: dict = {
                    'type':        _map_type(prop_type),
                    'description': prop_val.get('description', ''),
                }
                if prop_val.get('enum'):
                    # Gemini enum qiymatlari string bo'lishi kerak.
                    schema_kwargs['enum'] = [str(v) for v in prop_val['enum']]
                if prop_type == 'array':
                    # Gemini array-type parametrlar uchun 'items' SHART —
                    # bo'lmasa API xato qaytaradi. Hozircha tool ta'riflarida
                    # array parametr yo'q, lekin kelajakda qo'shilsa (masalan
                    # passenger_details) bu yerda avtomatik ishlaydi.
                    item_schema = prop_val.get('items', {'type': 'string'})
                    schema_kwargs['items'] = types.Schema(
                        type=_map_type(item_schema.get('type', 'string')),
                    )
                properties[prop_name] = types.Schema(**schema_kwargs)

            parameters = types.Schema(
                type       = types.Type.OBJECT,
                properties = properties,
                required   = schema.get('required', []),
            )

            declarations.append(
                types.FunctionDeclaration(
                    name        = tool['name'],
                    description = tool.get('description', ''),
                    parameters  = parameters,
                )
            )

        return types.Tool(function_declarations=declarations)


def _map_type(json_type: str):
    """JSON Schema type → Gemini Type."""
    from google.genai.types import Type
    mapping = {
        'string':  Type.STRING,
        'integer': Type.INTEGER,
        'number':  Type.NUMBER,
        'boolean': Type.BOOLEAN,
        'array':   Type.ARRAY,
        'object':  Type.OBJECT,
    }
    return mapping.get(json_type, Type.STRING)