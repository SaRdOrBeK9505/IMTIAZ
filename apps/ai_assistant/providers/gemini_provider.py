"""
Google Gemini AI Provider implementatsiyasi.
SDK: google-genai (yangi, rasmiy)  pip install google-genai
Model: gemini-3.6-flash (settings.GEMINI_MODEL orqali o'zgartiriladi)
"""

from __future__ import annotations

import logging
import time
from django.conf import settings

from .base import BaseAIProvider, AIMessage, AIResponse

logger = logging.getLogger(__name__)

RETRYABLE_STATUSES = {500, 503}
MAX_ATTEMPTS = 2


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

    def _build_contents(self, messages: list[AIMessage]):
        from google.genai import types

        gemini_contents = []
        for msg in messages:
            if msg.role == 'system':
                continue
            role    = 'user' if msg.role == 'user' else 'model'
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
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
    ) -> AIResponse:
        gemini_contents = self._build_contents(messages)
        config = self._build_config(tools, system, max_tokens)

        # ── Vaqtinchalik xatolar (500/503) uchun tez, cheklangan retry ──
        response = None
        last_exc = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._client.models.generate_content(
                    model    = self.model,
                    contents = gemini_contents,
                    config   = config,
                )
                break
            except Exception as e:
                last_exc = e
                status_code = getattr(e, 'code', None) or getattr(e, 'status_code', None)
                retryable = status_code in RETRYABLE_STATUSES

                if retryable and attempt < MAX_ATTEMPTS:
                    wait_s = 1.5 * attempt
                    logger.warning(
                        'Gemini chaqiruv xatosi (attempt %d/%d, status=%s): %s — %.1fs kutib qayta uriniladi',
                        attempt, MAX_ATTEMPTS, status_code, e, wait_s,
                    )
                    time.sleep(wait_s)
                    continue

                logger.exception('Gemini API xatosi (attempt %d/%d): %s', attempt, MAX_ATTEMPTS, e)
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
    ):
        """
        HAQIQIY Gemini streaming — generate_content_stream orqali.
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
        gemini_contents = self._build_contents(messages)
        config = self._build_config(tools, system, max_tokens)

        last_exc = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
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
                status_code = getattr(e, 'code', None) or getattr(e, 'status_code', None)
                retryable = status_code in RETRYABLE_STATUSES

                if retryable and attempt < MAX_ATTEMPTS:
                    wait_s = 1.5 * attempt
                    logger.warning(
                        'Gemini stream xatosi (attempt %d/%d, status=%s): %s — %.1fs kutib qayta uriniladi',
                        attempt, MAX_ATTEMPTS, status_code, e, wait_s,
                    )
                    time.sleep(wait_s)
                    continue

                logger.exception('Gemini stream xatosi (attempt %d/%d): %s', attempt, MAX_ATTEMPTS, e)
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
                properties[prop_name] = types.Schema(
                    type        = _map_type(prop_type),
                    description = prop_val.get('description', ''),
                )

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