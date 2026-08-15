"""
Google Gemini AI Provider implementatsiyasi.
SDK: google-genai (yangi, rasmiy)  pip install google-genai
Model: settings.GEMINI_MODEL orqali o'zgartiriladi

O'zgarishlar (v2):
  - _parse_response: bloklangan/bo'sh javobda AttributeError bo'lmaydi (SAFETY fix)
  - safety_settings: BLOCK_ONLY_HIGH — "avariya", "shifoxona" kabi so'zlar bloklanmaydi
  - Retry mexanizmi: 429/500/502/503/504 uchun 2 marta qayta urinadi
  - _build_contents: tool_result ro'yxati Gemini function_response'ga to'g'ri o'giriladi
  - _convert_tools: enum va description to'liq yuboriladi
"""

from __future__ import annotations

import json
import logging
import time

from django.conf import settings

from .base import BaseAIProvider, AIMessage, AIResponse

logger = logging.getLogger(__name__)

# Vaqtinchalik (transient) xatolar — qayta urinish mumkin
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class GeminiProviderError(Exception):
    """Barqaror (retry qilib bo'lmaydigan) Gemini xatosi."""


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

    def chat(
        self,
        messages: list[AIMessage],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
        use_thinking: bool = False,
    ) -> AIResponse:
        """
        Gemini bilan suhbat.

        use_thinking=True: pro model uchun thinking_config yoqiladi.
        MUHIM: Gemini API'da thinking va tool-calling birgalikda
        ishlamaydi — thinking faqat tool=None holatida qo'llanadi.
        """
        from google.genai import types

        if max_tokens is None:
            max_tokens = getattr(settings, 'AI_MAX_TOKENS', 4096)

        gemini_contents = self._build_contents(messages, types)

        # Pro model uchun yuqori temperature — ijodiyroq, tabiiyroq javob
        temperature = getattr(settings, 'AI_TEMPERATURE', 0.3)
        if use_thinking:
            temperature = max(temperature, 0.5)

        config_kwargs: dict = {
            'max_output_tokens': max_tokens,
            'temperature': temperature,
            # Concierge-bot uchun me'yoriy xavfsizlik darajasi —
            # "avariya", "shifoxona", "og'riq", "страховка", "эвакуатор" kabi so'zlar
            # noto'g'ri bloklanmasin. BLOCK_ONLY_HIGH — faqat aniq zararli kontent bloklanadi.
            'safety_settings': [
                types.SafetySetting(
                    category=cat,
                    threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                )
                for cat in (
                    types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                )
            ],
        }

        if system:
            config_kwargs['system_instruction'] = system

        if tools:
            config_kwargs['tools'] = [self._convert_tools(tools, types)]
        elif use_thinking:
            # Thinking faqat tool yo'q holatlarda qo'llanadi (Gemini API cheklovi)
            thinking_budget = getattr(settings, 'AI_THINKING_BUDGET', 1024)
            if thinking_budget > 0:
                try:
                    config_kwargs['thinking_config'] = types.ThinkingConfig(
                        thinking_budget=thinking_budget,
                    )
                    logger.debug('Gemini thinking yoqildi: budget=%s', thinking_budget)
                except Exception:
                    # ThinkingConfig ushbu model versiyasida qo'llab-quvvatlanmasligi mumkin
                    logger.debug('Gemini ThinkingConfig mavjud emas, o\'tkazib yuborildi')

        config = types.GenerateContentConfig(**config_kwargs)

        response = self._call_with_retry(gemini_contents, config)
        return self._parse_response(response)

    # ── Chaqiruv + retry ──────────────────────────────────────────────────────

    def _call_with_retry(self, contents, config, max_attempts: int = 3):
        """
        Gemini API ga chaqiruv + eksponensial backoff.
        Transient xatolar (429, 5xx, timeout) uchun qayta urinadi.
        """
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                return self._client.models.generate_content(
                    model=self.model, contents=contents, config=config,
                )
            except Exception as e:
                status = getattr(e, 'status_code', None) or getattr(e, 'code', None)
                is_retryable = (
                    status in _RETRYABLE_STATUS
                    or 'timeout' in str(e).lower()
                    or 'rate' in str(e).lower()
                )
                logger.warning(
                    'Gemini chaqiruv xatosi (attempt %s/%s, retryable=%s, status=%s): %s',
                    attempt, max_attempts, is_retryable, status, e,
                )
                last_exc = e
                if not is_retryable or attempt == max_attempts:
                    break
                time.sleep(0.6 * attempt)  # backoff: 0.6s, 1.2s

        logger.exception('Gemini API — barcha urinishlar muvaffaqiyatsiz: %s', last_exc)
        raise GeminiProviderError(str(last_exc)) from last_exc

    # ── Javobni XAVFSIZ parse qilish ──────────────────────────────────────────

    def _parse_response(self, response) -> AIResponse:
        """
        Gemini javobini AIResponse'ga o'girish.

        MUHIM: candidate.content None bo'lishi mumkin —
        SAFETY / RECITATION / OTHER finish_reason holatida.
        Bu eski kodda AttributeError: 'NoneType' object has no attribute 'parts'
        xatosini berardi. Endi toza content='' qaytariladi.
        """
        text_content = ''
        tool_calls: list[dict] = []

        # candidates None yoki bo'sh bo'lishi mumkin
        candidates = getattr(response, 'candidates', None)
        candidate = candidates[0] if candidates else None

        if candidate is None:
            logger.warning(
                'Gemini: candidates bo\'sh qaytdi (prompt_feedback=%s)',
                getattr(response, 'prompt_feedback', None),
            )
            return AIResponse(
                content='', tool_calls=[], stop_reason='blocked', raw=response,
            )

        finish_reason = getattr(candidate, 'finish_reason', None)

        # ASOSIY FIX: content None bo'lsa (SAFETY/RECITATION) — portlamasdan qaytamiz
        if candidate.content is None or not getattr(candidate.content, 'parts', None):
            logger.warning(
                'Gemini: content bloklandi yoki bo\'sh (finish_reason=%s, '
                'safety_ratings=%s)',
                finish_reason,
                getattr(candidate, 'safety_ratings', None),
            )
            return AIResponse(
                content='',
                tool_calls=[],
                stop_reason=str(finish_reason),
                raw=response,
            )

        for part in candidate.content.parts:
            if getattr(part, 'text', None):
                text_content += part.text
            elif getattr(part, 'function_call', None):
                fc = part.function_call
                tool_calls.append({
                    'id':    f'gemini-{fc.name}',
                    'name':  fc.name,
                    'input': dict(fc.args) if fc.args else {},
                })

        try:
            tokens_used = (
                response.usage_metadata.prompt_token_count
                + response.usage_metadata.candidates_token_count
            )
        except Exception:
            tokens_used = 0

        return AIResponse(
            content=text_content,
            tool_calls=tool_calls,
            tokens_used=tokens_used,
            stop_reason=str(finish_reason or 'end_turn'),
            raw=response,
        )

    # ── Xabarlarni Gemini formatiga o'girish ─────────────────────────────────

    def _build_contents(self, messages: list[AIMessage], types):
        """
        AIMessage ro'yxatini Gemini Content ro'yxatiga o'girish.

        Claude-uslub tool_result ro'yxati endi Gemini'ning
        native function_response formatiga to'g'ri o'giriladi.
        Oldin bu str() bilan oddiy matnga aylantirilardi — Gemini buni tushunmasdi.
        """
        contents = []
        for msg in messages:
            if msg.role == 'system':
                continue  # system_instruction orqali beriladi

            # Claude-uslub tool_result ro'yxati — Gemini function_response'ga o'girish
            if isinstance(msg.content, list):
                parts = []
                for block in msg.content:
                    if isinstance(block, dict) and block.get('type') == 'tool_result':
                        raw = block.get('content')
                        try:
                            response_data = (
                                json.loads(raw) if isinstance(raw, str) else raw
                            )
                        except (TypeError, ValueError):
                            response_data = {'result': str(raw)}
                        parts.append(
                            types.Part.from_function_response(
                                name=block.get('tool_name', 'unknown_tool'),
                                response={'result': response_data},
                            )
                        )
                if parts:
                    contents.append(types.Content(role='user', parts=parts))
                    continue

            role    = 'user' if msg.role == 'user' else 'model'
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            contents.append(
                types.Content(role=role, parts=[types.Part(text=content)])
            )
        return contents

    # ── Tool sxemasini to'liq o'girish ───────────────────────────────────────

    @staticmethod
    def _convert_tools(tools: list[dict], types):
        """
        Claude tool format → Gemini Tool formatiga o'girish.

        O'zgarish: enum va description endi to'liq yuboriladi.
        Oldin faqat type va description yuborilardi — model
        seat_class, wagon_type kabi to'g'ri qiymatlarni bilmasdi.

        Claude format:
            {'name': '...', 'description': '...', 'input_schema': {...}}

        Gemini format:
            Tool(function_declarations=[FunctionDeclaration(...)])
        """
        declarations = []
        for tool in tools:
            schema = tool.get('input_schema', {})
            properties = {}

            for prop_name, prop_val in schema.get('properties', {}).items():
                kwargs: dict = {
                    'type':        _map_type(prop_val.get('type', 'string'), types),
                    'description': prop_val.get('description', ''),
                }
                # enum qiymatlarini ham yuboramiz — model aniq tanlashlari uchun
                if 'enum' in prop_val:
                    kwargs['enum'] = prop_val['enum']
                properties[prop_name] = types.Schema(**kwargs)

            parameters = types.Schema(
                type=types.Type.OBJECT,
                properties=properties,
                required=schema.get('required', []),
            )
            declarations.append(
                types.FunctionDeclaration(
                    name=tool['name'],
                    description=tool.get('description', ''),
                    parameters=parameters,
                )
            )

        return types.Tool(function_declarations=declarations)


def _map_type(json_type: str, types):
    """JSON Schema type → Gemini Type."""
    mapping = {
        'string':  types.Type.STRING,
        'integer': types.Type.INTEGER,
        'number':  types.Type.NUMBER,
        'boolean': types.Type.BOOLEAN,
        'array':   types.Type.ARRAY,
        'object':  types.Type.OBJECT,
    }
    return mapping.get(json_type, types.Type.STRING)
