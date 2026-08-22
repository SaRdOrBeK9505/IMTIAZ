"""
OpenAI AI Provider implementatsiyasi.
SDK: openai>=1.0  (pip install openai)
Model: gpt-4o-mini (settings.OPENAI_MODEL orqali o'zgartiriladi)

Gemini Flash'da 503 (high demand) muammosi bo'lganda zaxira provider sifatida
yoki mustaqil asosiy provider sifatida ishlatiladi.

Qo'llab-quvvatlaydi:
  - chat()        — to'liq javob (tool-calling bilan)
  - chat_stream() — SSE streaming (tool-calling bilan)
  - log_context   — xatolarda user_id/session_id/request_id logi

GPT-4o-mini vs Gemini 3.1 Flash-Lite taqqoslash:
  - GPT-4o-mini: ~100–150 token/s, tool-calling ishonchli
  - Gemini 3.1 Flash-Lite: ~381 token/s — tezroq, lekin 503 muammosi bor
  - GPT-4o-mini — zaxira/fallback uchun ideal
"""

from __future__ import annotations

import logging
import time
from django.conf import settings

from .base import BaseAIProvider, AIMessage, AIResponse

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503}

def _max_attempts() -> int:
    return getattr(settings, 'AI_MAX_ATTEMPTS', 2)

def _retry_delay() -> float:
    return getattr(settings, 'AI_RETRY_DELAY', 0.5)


def _openai_client(api_key: str):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(
            "openai paketi o'rnatilmagan. `pip install openai` bajaring."
        ) from exc
    return OpenAI(api_key=api_key)


def _extract_status(exc: Exception) -> int | None:
    """openai.APIStatusError yoki boshqa exception dan status code olish."""
    return (
        getattr(exc, 'status_code', None)
        or getattr(exc, 'code', None)
    )


def _log_final_error(method: str, attempt: int, status_code, exc: Exception, ctx: dict) -> None:
    """Barcha retry tugaganda aniq ERROR yozuv — user/session bilan."""
    logger.error(
        'OpenAI %s: barcha %d urinish MUVAFFAQIYATSIZ. '
        'status=%s | user_id=%s | session_id=%s | request_id=%s | xato: %s',
        method, _max_attempts(),
        status_code,
        ctx.get('user_id', '?'),
        ctx.get('session_id', '?'),
        ctx.get('request_id', '?'),
        exc,
        exc_info=True,
    )


def _convert_tools(tools: list[dict]) -> list[dict]:
    """
    Claude/Gemini tool format → OpenAI function-calling formatiga o'girish.

    Kirish (Claude format):
        {'name': '...', 'description': '...', 'input_schema': {'type': 'object', 'properties': {...}}}

    Chiqish (OpenAI format):
        {'type': 'function', 'function': {'name': '...', 'description': '...', 'parameters': {...}}}
    """
    result = []
    for tool in tools:
        result.append({
            'type': 'function',
            'function': {
                'name':        tool['name'],
                'description': tool.get('description', ''),
                'parameters':  tool.get('input_schema', {'type': 'object', 'properties': {}}),
            },
        })
    return result


def _parse_tool_calls(raw_tool_calls) -> list[dict]:
    """OpenAI tool_calls → ichki format."""
    import json as _json
    result = []
    for tc in (raw_tool_calls or []):
        try:
            args = _json.loads(tc.function.arguments or '{}')
        except Exception:
            args = {}
        result.append({
            'id':    tc.id,
            'name':  tc.function.name,
            'input': args,
        })
    return result


class OpenAIProvider(BaseAIProvider):
    """
    OpenAI API provider.
    Claude/Gemini bilan bir xil interfeys — services.py o'zgarmaydi.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', '') or 'dummy-key-for-testing'
        self.model   = model  or getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = _openai_client(self.api_key)
        return self._client

    def get_model_name(self) -> str:
        return self.model

    @staticmethod
    def _format_message_content(content) -> str:
        """
        AIMessage.content string yoki Claude-uslubidagi tool_result bloklari
        ro'yxati bo'lishi mumkin. Avval bu yerda str(list) qilinar edi —
        model xom Python ro'yxatini ko'rar edi. Endi o'qiladigan matn beriladi.
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

    def _build_messages(self, messages: list[AIMessage], system: str | None) -> list[dict]:
        """AIMessage ro'yxatini OpenAI messages formatiga o'girish."""
        result = []
        if system:
            result.append({'role': 'system', 'content': system})
        for msg in messages:
            if msg.role == 'system':
                continue  # system allaqachon qo'shildi
            content = self._format_message_content(msg.content)
            result.append({'role': msg.role, 'content': content})
        return result

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
        429/500/503 xato bo'lganda bu ma'lumotlar ERROR logga yoziladi.
        """
        ctx = log_context or {}
        if max_tokens is None:
            max_tokens = getattr(settings, 'AI_MAX_OUTPUT_TOKENS', 400)

        oai_messages = self._build_messages(messages, system)
        oai_tools = _convert_tools(tools) if tools else None

        last_exc = None
        last_status = None

        max_attempts = _max_attempts()
        for attempt in range(1, max_attempts + 1):
            try:
                kwargs: dict = {
                    'model':      self.model,
                    'messages':   oai_messages,
                    'max_tokens': max_tokens,
                    'temperature': getattr(settings, 'AI_TEMPERATURE', 0.2),
                }
                if oai_tools:
                    kwargs['tools'] = oai_tools

                response = self.client.chat.completions.create(**kwargs)
                break

            except Exception as e:
                last_exc = e
                last_status = _extract_status(e)
                retryable = last_status in RETRYABLE_STATUS_CODES

                if retryable and attempt < max_attempts:
                    wait_s = _retry_delay() * 1.5 * attempt  # OpenAI rate limit uchun biroz ko'proq kutamiz
                    logger.warning(
                        'OpenAI chat xatosi (attempt %d/%d, status=%s): %s — %.1fs kutib qayta uriniladi',
                        attempt, max_attempts, last_status, e, wait_s,
                    )
                    time.sleep(wait_s)
                    continue

                _log_final_error('chat', attempt, last_status, e, ctx)
                raise

        # Javobni parse qilish
        choice = response.choices[0] if response.choices else None
        text_content = ''
        tool_calls: list[dict] = []

        if choice:
            msg = choice.message
            text_content = msg.content or ''
            if msg.tool_calls:
                tool_calls = _parse_tool_calls(msg.tool_calls)

        tokens_used = 0
        if response.usage:
            tokens_used = response.usage.total_tokens

        return AIResponse(
            content     = text_content,
            tool_calls  = tool_calls,
            tokens_used = tokens_used,
            stop_reason = (choice.finish_reason if choice else 'end_turn') or 'end_turn',
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
        OpenAI SSE streaming.

        log_context = {'user_id': ..., 'session_id': ..., 'request_id': ...}

        Tool-call bo'lganda: OpenAI tool_calls'ni delta bo'laklari sifatida
        yuboradi — biz ularni yig'ib oxirgi '__final' eventda qaytaramiz.
        """
        ctx = log_context or {}
        if max_tokens is None:
            max_tokens = getattr(settings, 'AI_MAX_OUTPUT_TOKENS', 400)

        oai_messages = self._build_messages(messages, system)
        oai_tools = _convert_tools(tools) if tools else None

        last_exc = None
        last_status = None

        max_attempts = _max_attempts()
        for attempt in range(1, max_attempts + 1):
            try:
                kwargs: dict = {
                    'model':      self.model,
                    'messages':   oai_messages,
                    'max_tokens': max_tokens,
                    'temperature': getattr(settings, 'AI_TEMPERATURE', 0.2),
                    'stream':     True,
                    'stream_options': {'include_usage': True},
                }
                if oai_tools:
                    kwargs['tools'] = oai_tools

                text_content = ''
                # Tool call delta yig'ish
                tool_call_chunks: dict[int, dict] = {}  # index → {id, name, args_so_far}
                tokens_used = 0

                with self.client.chat.completions.create(**kwargs) as stream:
                    for chunk in stream:
                        # Usage (oxirgi chunk'da keladi)
                        if chunk.usage:
                            tokens_used = chunk.usage.total_tokens or 0

                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta

                        # Matn bo'lagi
                        if delta.content:
                            text_content += delta.content
                            yield delta.content  # ← darhol frontendga

                        # Tool call delta yig'ish
                        if delta.tool_calls:
                            for tc_delta in delta.tool_calls:
                                idx = tc_delta.index
                                if idx not in tool_call_chunks:
                                    tool_call_chunks[idx] = {
                                        'id':   tc_delta.id or '',
                                        'name': (tc_delta.function.name if tc_delta.function else '') or '',
                                        'args': '',
                                    }
                                if tc_delta.function and tc_delta.function.arguments:
                                    tool_call_chunks[idx]['args'] += tc_delta.function.arguments
                                if tc_delta.id:
                                    tool_call_chunks[idx]['id'] = tc_delta.id
                                if tc_delta.function and tc_delta.function.name:
                                    tool_call_chunks[idx]['name'] = tc_delta.function.name

                # Tool calls yig'ilgandan keyin parse qilish
                import json as _json
                tool_calls: list[dict] = []
                for idx in sorted(tool_call_chunks):
                    tc = tool_call_chunks[idx]
                    try:
                        args = _json.loads(tc['args'] or '{}')
                    except Exception:
                        args = {}
                    tool_calls.append({
                        'id':    tc['id'],
                        'name':  tc['name'],
                        'input': args,
                    })

                yield {
                    '__final':    True,
                    'tokens_used': tokens_used,
                    'tool_calls': tool_calls,
                    'raw':        None,
                }
                return

            except Exception as e:
                last_exc = e
                last_status = _extract_status(e)
                retryable = last_status in RETRYABLE_STATUS_CODES

                if retryable and attempt < max_attempts:
                    wait_s = _retry_delay() * 1.5 * attempt
                    logger.warning(
                        'OpenAI stream xatosi (attempt %d/%d, status=%s): %s — %.1fs kutib qayta uriniladi',
                        attempt, max_attempts, last_status, e, wait_s,
                    )
                    time.sleep(wait_s)
                    continue

                _log_final_error('stream', attempt, last_status, e, ctx)
                raise