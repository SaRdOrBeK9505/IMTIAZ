"""
AI Assistant Service — asosiy biznes logika.

Tasdiqlash oqimi:
    1. AI yozish tool'ini chaqiradi (book_flight va h.k.)
    2. requires_confirmation() → True bo'lsa:
       → create_pending_action() → AIActionLog(needs_confirmation) yaratiladi
       → Booking YARATILMAYDI
       → frontend'ga action_id qaytariladi
    3. Foydalanuvchi frontend tugmasini bosadi:
       → POST /api/ai/actions/{id}/confirm
       → confirm_pending_action() → haqiqiy Booking yaratiladi
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid

from django.conf import settings
from django.core.cache import cache

from .confirmation import create_pending_action, requires_confirmation
from .i18n import build_confirmation_summary, build_system_prompt, resolve_language, t
from .models import ConversationSession, ConversationMessage, AIActionLog, UserAIProfile
from .providers.base import BaseAIProvider, AIMessage
from .response_builder import (
    build_reply_from_tools,
    should_use_local_reply,
    trim_tool_result_for_ai,
)
from .tools import get_all_tools

logger = logging.getLogger(__name__)
# Faqat timing/latency metrikasi uchun — logs/analyze.log ga yoziladi
analyze_logger = logging.getLogger('apps.ai_assistant.analyze')


class StepTimer:
    """
    Bitta so'rov (chat() chaqiruvi) ichidagi har bir qadamni
    ('history_load', 'provider_call', 'tool:search_flights', ...)
    millisekundlarda o'lchab, tartib bilan saqlaydi.

    Foydalanish:
        timer = StepTimer(request_id)
        with timer.measure('history_load'):
            ...

    Oxirida `timer.summary()` — barcha qadamlar va umumiy vaqtni
    tartiblangan dict qilib qaytaradi, `timer.log()` esa buni bitta
    struktura log qatori sifatida chiqaradi (request_id bilan bog'langan
    holda, RequestLoggingMiddleware dagi request_id bilan mos qilib
    ishlatish mumkin).
    """

    def __init__(self, request_id: str = ''):
        self.request_id = request_id or str(uuid.uuid4())[:8]
        self.steps: list[dict] = []
        self._t0 = time.monotonic()

    class _Ctx:
        def __init__(self, timer: 'StepTimer', name: str):
            self.timer = timer
            self.name = name
            self.start = 0.0

        def __enter__(self):
            self.start = time.monotonic()
            return self

        def __exit__(self, exc_type, exc, tb):
            duration_ms = int((time.monotonic() - self.start) * 1000)
            self.timer.steps.append({
                'step': self.name,
                'duration_ms': duration_ms,
                'ok': exc_type is None,
            })
            return False  # xatoni yutib qolmaymiz

    def measure(self, name: str) -> '_Ctx':
        return StepTimer._Ctx(self, name)

    def add(self, name: str, duration_ms: int, ok: bool = True) -> None:
        """Tashqarida (masalan tool loop ichida) o'lchangan vaqtni qo'shish."""
        self.steps.append({'step': name, 'duration_ms': duration_ms, 'ok': ok})

    def total_ms(self) -> int:
        return int((time.monotonic() - self._t0) * 1000)

    def summary(self) -> dict:
        return {
            'request_id': self.request_id,
            'total_ms': self.total_ms(),
            'steps': self.steps,
        }

    def log(
        self,
        logger_: logging.Logger,
        message: str = 'AI chat timing',
        analyze_logger_: logging.Logger | None = None,
    ) -> None:
        """
        Asosiy logga va (ixtiyoriy) analyze logga bitta structured JSON qator yozadi.
        analyze_logger_ berilsa, logs/analyze.log ga alohida yoziladi —
        analyze_latency management command shu fayl bilan ishlaydi.
        """
        summary = self.summary()
        logger_.info(message, extra={'data': summary})
        if analyze_logger_ is not None:
            analyze_logger_.info(message, extra={'data': summary})

# Yozish tool'lari — requires_confirmation() ga yuboriladi
WRITE_TOOL_TO_ACTION: dict[str, tuple[str, str]] = {
    'book_flight':      ('book',   'flight'),
    'book_restaurant':  ('book',   'restaurant'),
    'cancel_booking':   ('cancel', ''),
}

CACHEABLE_TOOLS = {
    'search_flights',
    'search_restaurants',
    'search_events',
    'search_tour_packages',
}


def _create_provider_by_name(name: str) -> BaseAIProvider:
    if name == 'claude':
        from .providers.claude_provider import ClaudeProvider
        return ClaudeProvider()
    if name == 'openai':
        from .providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    from .providers.gemini_provider import GeminiProvider
    return GeminiProvider()


def get_ai_provider() -> BaseAIProvider:
    primary_name = getattr(settings, 'AI_PROVIDER', 'gemini').lower()
    primary = _create_provider_by_name(primary_name)

    fallback_enabled = getattr(settings, 'AI_FALLBACK_ENABLED', True)
    if fallback_enabled:
        fallback_name = getattr(settings, 'AI_FALLBACK_PROVIDER', 'openai').lower()
        if fallback_name != primary_name:
            fallback = _create_provider_by_name(fallback_name)
            from .providers.fallback_provider import FallbackProvider
            return FallbackProvider(primary, fallback)

    return primary


def get_pro_provider() -> BaseAIProvider:
    """
    Followup / umumiy savol uchun chuqur fikrlovchi model.
    GEMINI_MODEL_PRO sozlangan bo'lsa → gemini-2.5-pro (yoki boshqa pro model).
    Sozlanmagan bo'lsa → oddiy provider qaytariladi (fallback sifatida).
    """
    primary_name = getattr(settings, 'AI_PROVIDER', 'gemini').lower()
    pro_model = getattr(settings, 'GEMINI_MODEL_PRO', '')

    if primary_name == 'gemini' and pro_model:
        from .providers.gemini_provider import GeminiProvider
        logger.debug("Pro model ishlatilmoqda: %s", pro_model)
        return GeminiProvider(model=pro_model)

    # Pro model sozlanmagan — oddiy provayderdan foydalaniladi
    return get_ai_provider()


class AIAssistantService:

    def __init__(self, provider: BaseAIProvider | None = None):
        self.provider = provider or get_ai_provider()

    def get_or_create_session(
        self, user, session_id: str | None = None
    ) -> ConversationSession:
        if session_id:
            try:
                return ConversationSession.objects.get(
                    id=session_id, user=user, is_active=True
                )
            except ConversationSession.DoesNotExist:
                pass
        return ConversationSession.objects.create(user=user)

    def bootstrap_session(self, user, session_id: str | None = None) -> dict:
        """
        Yangi AI suhbatni salom xabari bilan boshlaydi.
        Mini App /ai?welcome=1 ochilganda chaqiriladi.
        """
        session = self.get_or_create_session(user, session_id)
        lang = resolve_language(user)

        if session.messages.exists():
            last = session.messages.order_by('-created_at').first()
            return {
                'session_id':            str(session.id),
                'message_id':            str(last.id) if last else None,
                'content':               last.content if last and last.role == 'assistant' else '',
                'already_started':       True,
                'requires_confirmation': False,
            }

        welcome = t('ai_welcome', lang)
        quick_replies = t('quick_replies', lang)
        if not isinstance(quick_replies, list):
            quick_replies = ["✈️ Chipta izlash", "🍽️ Stol band qilish", "❓ Boshqa savol"]

        msg = ConversationMessage.objects.create(
            session=session,
            role='assistant',
            content=welcome,
        )
        if not session.title:
            session.title = 'IMTIAZ AI'
            session.save(update_fields=['title', 'updated_at'])

        return {
            'session_id':            str(session.id),
            'message_id':            str(msg.id),
            'content':               welcome,
            'quick_replies':         quick_replies,
            'already_started':       False,
            'requires_confirmation': False,
        }

    def chat(
        self, user, message: str, session_id: str | None = None,
        request_id: str = '',
    ) -> dict:
        """
        `request_id` — HTTP request_id (RequestLoggingMiddleware dan).
        Berilmasa, StepTimer o'zi qisqa UUID yaratadi. Bu ID orqali
        logdagi "AI chat timing" yozuvini va Nginx/Gunicorn access
        logdagi request_id'ni bitta so'rovga bog'lash mumkin.
        """
        timer = StepTimer(request_id)

        with timer.measure('get_or_create_session'):
            session = self.get_or_create_session(user, session_id)
        lang = resolve_language(user, message)

        ConversationMessage.objects.create(
            session=session, role='user', content=message,
        )

        with timer.measure('history_load'):
            history = self._load_history(session)
        with timer.measure('user_profile_summary'):
            user_profile_summary = self._build_user_profile_summary(user)
        with timer.measure('session_summary'):
            session_summary = self._build_session_summary(session)
        with timer.measure('system_prompt_build'):
            system = build_system_prompt(
                lang=lang,
                price_limit=f"{user.ai_auto_price_limit:,.0f}",
                autonomy_level=user.ai_autonomy_level,
                session_summary=session_summary,
                user_profile_summary=user_profile_summary,
            )
        tools = get_all_tools()

        from apps.ai_assistant.providers.base import AIResponse as ProviderAIResponse

        # Provider xatoliklar uchun context (user/session identifikatsiya)
        log_ctx = {
            'user_id':    str(getattr(user, 'id', '?')),
            'session_id': str(session.id),
            'request_id': timer.request_id,
        }

        try:
            with timer.measure('provider_call'):
                if getattr(settings, 'AI_ENABLE_STREAMING', False) and hasattr(self.provider, 'chat_stream'):
                    chunks = []
                    tool_calls = []
                    tokens_used = 0
                    raw = None
                    for part in self.provider.chat_stream(
                        messages=history, tools=tools, system=system,
                        log_context=log_ctx,
                    ):
                        if isinstance(part, dict) and part.get('__final'):
                            tokens_used = part.get('tokens_used', 0)
                            tool_calls = part.get('tool_calls', []) or []
                            raw = part.get('raw')
                        else:
                            chunks.append(str(part))
                    content = ''.join(chunks)
                    ai_response = ProviderAIResponse(content=content, tool_calls=tool_calls, tokens_used=tokens_used, raw=raw)
                else:
                    ai_response = self.provider.chat(
                        messages=history, tools=tools, system=system,
                        log_context=log_ctx,
                    )
            latency_ms = timer.steps[-1]['duration_ms']  # 'provider_call' — hozirgina yozildi

            # Audit log for AI call latency/tokens
            try:
                AIActionLog.objects.create(
                    user=user,
                    session=session,
                    action_type=AIActionLog.ActionType.INFO_REQUEST,
                    payload={'message': message, 'tokens_used': getattr(ai_response, 'tokens_used', 0), 'latency_ms': latency_ms},
                    duration_ms=latency_ms,
                    request_id=timer.request_id,
                )
            except Exception:
                logger.exception('AIActionLog yaratishda xato')
        except Exception as e:
            logger.exception('AI provider xatosi: %s', e)
            err = t('ai_provider_error', lang)
            ConversationMessage.objects.create(
                session=session, role='assistant', content=err,
            )
            AIActionLog.objects.create(
                user=user, session=session,
                action_type=AIActionLog.ActionType.INFO_REQUEST,
                payload={'message': message},
                status=AIActionLog.ActionStatus.FAILED,
                error_message=str(e),
                duration_ms=timer.total_ms(),
                request_id=timer.request_id,
            )
            timer.log(logger, message='AI chat timing (provider xatosi)', analyze_logger_=analyze_logger)
            return {
                'session_id': str(session.id),
                'content': err,
                'tool_calls_count': 0,
                'requires_confirmation': False,
            }

        # Tool-calling
        final_content        = ai_response.content
        tool_results         = []
        pending_action_id    = None
        pending_summary      = ''

        if ai_response.tool_calls:
            with timer.measure('tools_total'):
                tool_results, pending_action_id, pending_summary = (
                    self._execute_tool_calls(
                        user, session, ai_response.tool_calls,
                        lang=lang, timer=timer,
                    )
                )

            if pending_action_id:
                # Tasdiqlash kerak — foydalanuvchiga savol
                final_content = pending_summary
            elif should_use_local_reply(tool_results, message, lang):
                # Token tejash: oddiy holatda tool natijasidan javob yig'amiz.
                # Vaqt/batafsil savollar va bo'sh tur natijalari uchun LLM ishlatiladi.
                with timer.measure('local_reply_build'):
                    final_content = build_reply_from_tools(tool_results, lang=lang)
            else:
                # Murakkab holat — AI ga qisqartirilgan natija yuboriladi
                tool_msgs = [
                    AIMessage(
                        role='assistant',
                        content=(
                            ai_response.raw.content
                            if hasattr(ai_response.raw, 'content')
                            else final_content
                        ),
                    ),
                    AIMessage(
                        role='user',
                        content=[
                            {
                                'type':        'tool_result',
                                'tool_use_id': r['tool_use_id'],
                                'content':     json.dumps(
                                    trim_tool_result_for_ai(r['result']),
                                    ensure_ascii=False,
                                ),
                            }
                            for r in tool_results
                        ],
                    ),
                ]
                try:
                    with timer.measure('followup_provider_call'):
                        final_resp = self.provider.chat(
                            messages=history + tool_msgs,
                            tools=tools, system=system,
                            max_tokens=getattr(settings, 'AI_FOLLOWUP_MAX_TOKENS', 512),
                        )
                    final_content = (
                        final_resp.content
                        or build_reply_from_tools(tool_results, lang=lang)
                    )
                    followup_ms = timer.steps[-1]['duration_ms']
                    AIActionLog.objects.create(
                        user=user, session=session,
                        action_type=AIActionLog.ActionType.INFO_REQUEST,
                        payload={'message': '(followup)', 'tokens_used': getattr(final_resp, 'tokens_used', 0)},
                        duration_ms=followup_ms,
                        request_id=timer.request_id,
                    )
                except Exception as e:
                    logger.exception('Tool result qayta chaqiruvda xato: %s', e)
                    final_content = build_reply_from_tools(tool_results, lang=lang) or t(
                        'reply_format_error', lang
                    )

        with timer.measure('save_message'):
            msg = ConversationMessage.objects.create(
                session=session,
                role='assistant',
                content=final_content,
                tool_calls=ai_response.tool_calls or None,
                tool_results=tool_results or None,
                tokens_used=ai_response.tokens_used,
            )

        if not session.title:
            session.title = message[:80]
            session.save(update_fields=['title', 'updated_at'])

        with timer.measure('refresh_user_ai_profile'):
            self._refresh_user_ai_profile(user, session)

        # Bitta so'rov ichidagi barcha qadamlarni bitta log qatoriga yozamiz —
        # request_id orqali logging_middleware yozuvi bilan bog'lanadi.
        # Masalan: {"request_id": "e8b64981", "total_ms": 842, "steps": [
        #   {"step": "history_load", "duration_ms": 3, "ok": true},
        #   {"step": "provider_call", "duration_ms": 610, "ok": true},
        #   {"step": "tools_total", "duration_ms": 180, "ok": true},
        #   {"step": "tool:search_flights", "duration_ms": 175, "ok": true},
        #   ...
        # ]}
        timer.log(logger, analyze_logger_=analyze_logger)

        return {
            'session_id':            str(session.id),
            'message_id':            str(msg.id),
            'content':               final_content,
            'tool_calls_count':      len(ai_response.tool_calls),
            'tokens_used':           ai_response.tokens_used,
            'requires_confirmation': bool(pending_action_id),
            'pending_action_id':     str(pending_action_id) if pending_action_id else None,
            'timing':                timer.summary(),
        }

    # ── Ichki metodlar ────────────────────────────────────────────────────────
    def chat_stream(
            self, user, message: str, session_id: str | None = None,
            request_id: str = '',
    ):
        """
        SSE (Server-Sent Events) uchun generator.
        Faqat TOOL-CALL bo'lmagan (oddiy matn) javoblarda haqiqiy
        streaming beradi — chunki tool-call oqimi baribir ikkinchi
        AI chaqiruvini talab qiladi va uni oqim sifatida uzatish
        foydasiz murakkablik qo'shadi.

        Yield qilinadigan har bir element — dict:
            {'type': 'chunk', 'text': '...'}           — matn bo'lagi
            {'type': 'done', 'content': '...', ...}     — yakuniy natija
            {'type': 'error', 'message': '...'}          — xato
        """
        timer = StepTimer(request_id)

        with timer.measure('get_or_create_session'):
            session = self.get_or_create_session(user, session_id)
        lang = resolve_language(user, message)

        ConversationMessage.objects.create(
            session=session, role='user', content=message,
        )

        with timer.measure('history_load'):
            history = self._load_history(session)
        with timer.measure('user_profile_summary'):
            user_profile_summary = self._build_user_profile_summary(user)
        with timer.measure('session_summary'):
            session_summary = self._build_session_summary(session)
        with timer.measure('system_prompt_build'):
            system = build_system_prompt(
                lang=lang,
                price_limit=f"{user.ai_auto_price_limit:,.0f}",
                autonomy_level=user.ai_autonomy_level,
                session_summary=session_summary,
                user_profile_summary=user_profile_summary,
            )
        tools = get_all_tools()

        if not hasattr(self.provider, 'chat_stream'):
            # Provider streamni qo'llab-quvvatlamasa — oddiy chat() ga tushamiz
            result = self.chat(user, message, session_id, request_id)
            yield {'type': 'done', **result}
            return

        # Provider xatoliklar uchun context (user/session identifikatsiya)
        log_ctx = {
            'user_id':    str(getattr(user, 'id', '?')),
            'session_id': str(session.id),
            'request_id': timer.request_id,
        }

        text_so_far = ''
        tool_calls = []
        tokens_used = 0

        try:
            with timer.measure('provider_call'):
                for part in self.provider.chat_stream(
                    messages=history, tools=tools, system=system,
                    log_context=log_ctx,
                ):
                    if isinstance(part, dict) and part.get('__final'):
                        tokens_used = part.get('tokens_used', 0)
                        tool_calls = part.get('tool_calls', []) or []
                    else:
                        text_so_far += str(part)
                        yield {'type': 'chunk', 'text': str(part)}
            latency_ms = timer.steps[-1]['duration_ms']

            try:
                AIActionLog.objects.create(
                    user=user, session=session,
                    action_type=AIActionLog.ActionType.INFO_REQUEST,
                    payload={'message': message, 'tokens_used': tokens_used, 'latency_ms': latency_ms},
                    duration_ms=latency_ms,
                    request_id=timer.request_id,
                )
            except Exception:
                logger.exception('AIActionLog yaratishda xato')

        except Exception as e:
            logger.exception('AI provider xatosi (stream): %s', e)
            err = t('ai_provider_error', lang)
            ConversationMessage.objects.create(
                session=session, role='assistant', content=err,
            )
            AIActionLog.objects.create(
                user=user, session=session,
                action_type=AIActionLog.ActionType.INFO_REQUEST,
                payload={'message': message},
                status=AIActionLog.ActionStatus.FAILED,
                error_message=str(e),
                duration_ms=timer.total_ms(),
                request_id=timer.request_id,
            )
            yield {'type': 'error', 'message': err}
            return

        final_content = text_so_far
        tool_results = []
        pending_action_id = None
        pending_summary = ''

        if tool_calls:
            # Tool bor — bu yerda streaming to'xtaydi, qolgan qism
            # oddiy chat() bilan bir xil ishlaydi (tool bajarish +
            # kerak bo'lsa ikkinchi AI chaqiruvi). Frontendga alohida
            # 'tool_processing' eventi yuboriladi, keyin yakuniy javob.
            yield {
                'type': 'tool_processing',
                'tool_calls': [{'name': tc['name'], 'input': tc['input']} for tc in tool_calls]
            }

            with timer.measure('tools_total'):
                for event in self._execute_tool_calls_generator(
                    user, session, tool_calls, lang=lang, timer=timer,
                ):
                    if event['type'] == 'tool_start':
                        yield {
                            'type': 'tool_start',
                            'tool_name': event['tool_name'],
                            'input': event['input']
                        }
                    elif event['type'] == 'tool_end':
                        yield {
                            'type': 'tool_end',
                            'tool_name': event['tool_name'],
                            'status': event['status']
                        }
                    elif event['type'] == 'final':
                        tool_results = event['results']
                        pending_action_id = event['pending_action_id']
                        pending_summary = event['pending_summary']

            if pending_action_id:
                final_content = pending_summary
            elif should_use_local_reply(tool_results, message, lang):
                with timer.measure('local_reply_build'):
                    final_content = build_reply_from_tools(tool_results, lang=lang)
            else:
                tool_msgs = [
                    AIMessage(role='assistant', content=text_so_far),
                    AIMessage(
                        role='user',
                        content=[
                            {
                                'type': 'tool_result',
                                'tool_use_id': r['tool_use_id'],
                                'content': json.dumps(
                                    trim_tool_result_for_ai(r['result']),
                                    ensure_ascii=False,
                                ),
                            }
                            for r in tool_results
                        ],
                    ),
                ]
                try:
                    with timer.measure('followup_provider_call'):
                        final_resp = self.provider.chat(
                            messages=history + tool_msgs,
                            tools=tools, system=system,
                            max_tokens=getattr(settings, 'AI_FOLLOWUP_MAX_TOKENS', 512),
                        )
                    final_content = (
                            final_resp.content
                            or build_reply_from_tools(tool_results, lang=lang)
                    )
                    # Follow-up javobni ham chunk sifatida yuboramiz —
                    # frontend buni xuddi streamdek ko'rsatadi
                    yield {'type': 'chunk', 'text': final_content}
                except Exception as e:
                    logger.exception('Tool result qayta chaqiruvda xato: %s', e)
                    final_content = build_reply_from_tools(tool_results, lang=lang) or t(
                        'reply_format_error', lang
                    )
                    yield {'type': 'chunk', 'text': final_content}

        with timer.measure('save_message'):
            msg = ConversationMessage.objects.create(
                session=session,
                role='assistant',
                content=final_content,
                tool_calls=tool_calls or None,
                tool_results=tool_results or None,
                tokens_used=tokens_used,
            )

        if not session.title:
            session.title = message[:80]
            session.save(update_fields=['title', 'updated_at'])

        with timer.measure('refresh_user_ai_profile'):
            self._refresh_user_ai_profile(user, session)

        timer.log(logger, message='AI chat timing (stream)', analyze_logger_=analyze_logger)

        yield {
            'type': 'done',
            'session_id': str(session.id),
            'message_id': str(msg.id),
            'content': final_content,
            'tool_calls_count': len(tool_calls),
            'tokens_used': tokens_used,
            'requires_confirmation': bool(pending_action_id),
            'pending_action_id': str(pending_action_id) if pending_action_id else None,
        }

    def _load_history(self, session: ConversationSession) -> list[AIMessage]:
        limit = getattr(settings, 'AI_HISTORY_LIMIT', 8)
        rows = (
            session.messages
            .order_by('-created_at')
            .values('role', 'content')[:limit]
        )
        # Eski tartibda qaytarish
        return [
            AIMessage(role=r['role'], content=r['content'])
            for r in reversed(list(rows))
        ]

    def _build_user_profile_summary(self, user) -> str:
        profile, _ = UserAIProfile.objects.get_or_create(user=user)
        return (profile.summary_text or '').strip()

    def _refresh_user_ai_profile(self, user, session: ConversationSession) -> None:
        profile, _ = UserAIProfile.objects.get_or_create(user=user)

        recent_logs = list(
            AIActionLog.objects.filter(user=user).order_by('-created_at')[:25]
        )
        list_of_destinations: list[str] = []
        preferred_seat_class = profile.preferred_seat_class
        preferred_cuisine = profile.preferred_cuisine

        for log in recent_logs:
            payload = log.payload or {}
            seat_class = payload.get('seat_class') or payload.get('class')
            if seat_class and not preferred_seat_class:
                preferred_seat_class = str(seat_class).lower()

            cuisine = payload.get('cuisine') or payload.get('meal_type')
            if cuisine and not preferred_cuisine:
                preferred_cuisine = str(cuisine)

            for key in ('destination', 'city', 'origin', 'query'):
                value = payload.get(key)
                if value:
                    cleaned = str(value).strip()
                    if cleaned:
                        list_of_destinations.append(cleaned)

        destinations = []
        seen = set()
        for value in list_of_destinations:
            normalized = value.replace('_', ' ').strip()
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                destinations.append(normalized)

        if profile.preferred_seat_class != preferred_seat_class:
            profile.preferred_seat_class = preferred_seat_class or profile.preferred_seat_class
        if profile.preferred_cuisine != preferred_cuisine:
            profile.preferred_cuisine = preferred_cuisine or profile.preferred_cuisine
        if profile.frequent_destinations != destinations[:5]:
            profile.frequent_destinations = destinations[:5]

        parts = []
        if profile.preferred_seat_class:
            parts.append(f"Foydalanuvchi odatda {profile.preferred_seat_class} klassini tanlaydi.")
        if profile.preferred_cuisine:
            parts.append(f"U {profile.preferred_cuisine} taomlaridan ko'proq foydalangan.")
        if profile.frequent_destinations:
            parts.append(
                "Ko'pincha " + ', '.join(profile.frequent_destinations[:3]) + " yo'nalishlariga qiziqadi."
            )

        profile.summary_text = ' '.join(parts)
        profile.save(update_fields=['preferred_seat_class', 'preferred_cuisine', 'frequent_destinations', 'summary_text', 'updated_at'])

    def _execute_tool_calls(
        self,
        user,
        session: ConversationSession,
        tool_calls: list[dict],
        lang: str = 'uz',
        timer: 'StepTimer | None' = None,
    ) -> tuple[list[dict], str | None, str]:
        """
        Backward-compatible wrapper to run tool calls synchronously and return results.
        Uses _execute_tool_calls_generator under the hood.
        """
        generator = self._execute_tool_calls_generator(
            user=user, session=session, tool_calls=tool_calls, lang=lang, timer=timer
        )
        results = []
        pending_action_id = None
        pending_summary = ''
        for event in generator:
            if event['type'] == 'final':
                results = event['results']
                pending_action_id = event['pending_action_id']
                pending_summary = event['pending_summary']
        return results, pending_action_id, pending_summary

    def _execute_tool_calls_generator(
        self,
        user,
        session: ConversationSession,
        tool_calls: list[dict],
        lang: str = 'uz',
        timer: 'StepTimer | None' = None,
    ):
        """
        Yields progress events during tool execution:
          - {'type': 'tool_start', 'tool_name': ..., 'input': ...}
          - {'type': 'tool_end', 'tool_name': ..., 'status': 'success' | 'failed' | 'needs_confirmation'}
          - {'type': 'final', 'results': ..., 'pending_action_id': ..., 'pending_summary': ...}
        """
        results = []

        for call in tool_calls:
            tool_name  = call['name']
            tool_input = call['input']
            tool_started_at = time.monotonic()

            yield {
                'type': 'tool_start',
                'tool_name': tool_name,
                'input': tool_input,
            }

            # Yozish tool'imi?
            if tool_name in WRITE_TOOL_TO_ACTION:
                action_type, service_type = WRITE_TOOL_TO_ACTION[tool_name]
                amount = self._extract_amount(tool_input)

                if requires_confirmation(user, action_type, amount):
                    # DB'ga pending_action yoziladi, Booking YARATILMAYDI
                    log = create_pending_action(
                        user=user,
                        session=session,
                        action_type=action_type,
                        service_type=service_type,
                        payload=tool_input,
                        amount=amount,
                    )
                    if timer:
                        timer.add(
                            f'tool:{tool_name} [needs_confirmation]',
                            int((time.monotonic() - tool_started_at) * 1000),
                        )
                    summary = build_confirmation_summary(
                        tool_name, tool_input, amount, lang=lang
                    )
                    logger.info(
                        'Tool [%s] tasdiqlash kerak: action_id=%s, user=%s',
                        tool_name, log.id, user.id,
                    )
                    yield {
                        'type': 'tool_end',
                        'tool_name': tool_name,
                        'status': 'needs_confirmation',
                    }
                    yield {
                        'type': 'final',
                        'results': [],
                        'pending_action_id': str(log.id),
                        'pending_summary': summary,
                    }
                    return

            # Idempotency tekshiruvi: faqat cacheable external tool'lar uchun ishlaydi.
            cached_result = None
            idempotency_key = None
            if tool_name in CACHEABLE_TOOLS:
                input_hash = hashlib.md5(
                    json.dumps(tool_input, sort_keys=True).encode('utf-8')
                ).hexdigest()
                idempotency_key = f"ai_tool_idempotency:{session.id}:{tool_name}:{input_hash}"
                cached_result = cache.get(idempotency_key)

            if cached_result is not None:
                duration_ms = int((time.monotonic() - tool_started_at) * 1000)
                logger.info(
                    'Tool [%s] idempotency hit: session=%s (%dms)',
                    tool_name, session.id, duration_ms,
                )
                if timer:
                    timer.add(f'tool:{tool_name} [cache_hit]', duration_ms)
                AIActionLog.objects.create(
                    user=user, session=session,
                    action_type=self._tool_to_action_type(tool_name),
                    service_type=self._tool_to_service_type(tool_name),
                    payload={**tool_input, '_cache_hit': True},
                    result=cached_result,
                    status=AIActionLog.ActionStatus.SUCCESS,
                    duration_ms=duration_ms,
                    request_id=timer.request_id if timer else '',
                )
                results.append({
                    'tool_use_id': call['id'],
                    'tool_name':   tool_name,
                    'result':      cached_result,
                })
                yield {
                    'type': 'tool_end',
                    'tool_name': tool_name,
                    'status': 'success',
                }
                continue

            # O'qish tool'lari yoki full_auto/semi_auto (tasdiqlash shart emas)
            log_entry = AIActionLog(
                user=user,
                session=session,
                action_type=self._tool_to_action_type(tool_name),
                service_type=self._tool_to_service_type(tool_name),
                payload=tool_input,
                request_id=timer.request_id if timer else '',
            )
            try:
                result         = self._dispatch_tool(
                    user, tool_name, tool_input, lang=lang, session=session,
                )
                log_entry.result = result
                log_entry.status = AIActionLog.ActionStatus.SUCCESS
                if idempotency_key:
                    cache.set(idempotency_key, result, timeout=120)
                self._update_session_entity_state(session, tool_name, tool_input, result)
                duration_ms = int((time.monotonic() - tool_started_at) * 1000)
                logger.info('Tool [%s] OK: user=%s (%dms)', tool_name, user.id, duration_ms)
                status_str = 'success'
            except Exception as e:
                duration_ms = int((time.monotonic() - tool_started_at) * 1000)
                logger.exception(
                    'Tool [%s] XATO: user=%s — %s (%dms)',
                    tool_name, user.id, e, duration_ms,
                )
                from apps.integrations.errors import integration_error_dict
                service = 'flight' if tool_name == 'search_flights' else 'generic'
                result = integration_error_dict(e, service=service, lang=lang)
                log_entry.result = result
                log_entry.status = AIActionLog.ActionStatus.FAILED
                log_entry.error_message = str(e)
                status_str = 'failed'

            log_entry.duration_ms = duration_ms
            log_entry.save()
            if timer:
                timer.add(f'tool:{tool_name}', duration_ms, ok=(log_entry.status == AIActionLog.ActionStatus.SUCCESS))
            results.append({
                'tool_use_id': call['id'],
                'tool_name':   tool_name,
                'result':      result,
            })
            yield {
                'type': 'tool_end',
                'tool_name': tool_name,
                'status': status_str,
            }

        yield {
            'type': 'final',
            'results': results,
            'pending_action_id': None,
            'pending_summary': '',
        }

    def _build_session_summary(self, session: ConversationSession) -> str:
        parts = []

        # Oxirgi 5 ta bajarilgan harakat (AIActionLog)
        recent_logs = AIActionLog.objects.filter(session=session).order_by('-created_at')[:5]
        if recent_logs:
            log_lines = []
            for l in reversed(list(recent_logs)):
                payload_str = ", ".join(f"{k}={v}" for k, v in (l.payload or {}).items() if v)
                status_str = "SUCCESS" if l.status == AIActionLog.ActionStatus.SUCCESS else "FAILED"
                log_lines.append(f"- {l.action_type}({payload_str}) => {status_str}")
            parts.append("Harakatlar tarixi:\n" + "\n".join(log_lines))

        # Redis'dagi saqlangan session entity state
        state_key = f"ai_tool_state:{session.id}"
        state_data = cache.get(state_key)
        if state_data and isinstance(state_data, dict):
            state_lines = [f"- {k}: {v}" for k, v in state_data.items()]
            parts.append("Saqlangan ob'ektlar state:\n" + "\n".join(state_lines))

        user_profile_summary = self._build_user_profile_summary(session.user)
        if user_profile_summary:
            parts.append("Doimiy foydalanuvchi profili:\n" + user_profile_summary)

        return "\n\n".join(parts)

    def _update_session_entity_state(
        self, session: ConversationSession, tool_name: str, tool_input: dict, result: dict
    ):
        """
        Oxirgi qidiruv natijalarini Redis'ga saqlaydi (1 soat).
        `_build_session_summary()` orqali bu state keyingi AI chaqiruviga
        system prompt ichida ko'rsatiladi.

        MUHIM: bu yerda saqlanadigan `offer_id` / `branch_id` / `package_id`
        larsiz AI foydalanuvchi "2" yoki "ikkinchisini oling" deganda
        qaysi variantni nazarda tutayotganini bila olmaydi — natijada
        qayta search_flights chaqirib, xuddi shu ro'yxatni takror
        qaytaradi (bir xil javob muammosi shu yerdan kelib chiqadi).
        """
        if not isinstance(result, dict):
            return
        state_key = f"ai_tool_state:{session.id}"
        state = cache.get(state_key) or {}

        if tool_name == 'search_flights':
            # DIQQAT: handle_search_flights natijasi 'offers' deb qaytaradi,
            # 'flights' emas — avvalgi versiyada shu sabab count doim 0 edi.
            offers = result.get('offers') or []
            state['last_flight_search'] = {
                'origin': tool_input.get('origin'),
                'destination': tool_input.get('destination'),
                'departure_at': tool_input.get('departure_at'),
                'count': len(offers),
                # Foydalanuvchi raqam bilan tanlaganda AI shu ro'yxatdan
                # to'g'ridan-to'g'ri offer_id topib book_flight chaqiradi.
                'offers': [
                    {
                        'index':    i + 1,
                        'offer_id': o.get('offer_id'),
                        'airline':  o.get('airline'),
                        'flight_number': o.get('flight_number'),
                        'price':    o.get('price'),
                        'currency': o.get('currency'),
                    }
                    for i, o in enumerate(offers[:10])
                ],
            }
        elif tool_name == 'search_restaurants':
            # handle_search_restaurants natijasi 'results' deb qaytaradi.
            branches = result.get('results') or []
            state['last_restaurant_search'] = {
                'city': tool_input.get('city'),
                'date': tool_input.get('date'),
                'count': len(branches),
                'branches': [
                    {
                        'index':     i + 1,
                        'branch_id': b.get('branch_id'),
                        'name':      b.get('name'),
                    }
                    for i, b in enumerate(branches[:10])
                ],
            }
        elif tool_name == 'search_tour_packages':
            # handle_search_tour_packages natijasi ham 'results' deb qaytaradi.
            packages = result.get('results') or []
            state['last_tour_search'] = {
                'destination': tool_input.get('destination'),
                'query': tool_input.get('query'),
                'count': len(packages),
                'packages': [
                    {'index': i + 1, 'package_id': p.get('package_id') or p.get('id')}
                    for i, p in enumerate(packages[:10])
                ],
            }
        elif tool_name in WRITE_TOOL_TO_ACTION:
            state['last_write_action'] = {
                'tool': tool_name,
                'input': tool_input,
            }

        cache.set(state_key, state, timeout=3600)

    @staticmethod
    def _dispatch_tool(user, tool_name: str, tool_input: dict, lang: str = 'uz', session=None) -> dict:
        from .tool_handlers import TOOL_DISPATCH
        handler = TOOL_DISPATCH.get(tool_name)
        if not handler:
            raise ValueError(f"Noma'lum tool: {tool_name!r}")
        return handler(user=user, lang=lang, session=session, **tool_input)

    @staticmethod
    def _extract_amount(tool_input: dict) -> Decimal | None:
        from decimal import Decimal
        for key in ('price', 'amount', 'total_price', 'final_price'):
            val = tool_input.get(key)
            if val:
                try:
                    return Decimal(str(val))
                except Exception:
                    pass
        return None

    @staticmethod
    def _tool_to_action_type(name: str) -> str:
        return {
            'search_flights':       AIActionLog.ActionType.SEARCH,
            'search_restaurants':   AIActionLog.ActionType.SEARCH,
            'search_events':        AIActionLog.ActionType.SEARCH,
            'search_tour_packages': AIActionLog.ActionType.SEARCH,
            'get_nearby_places':    AIActionLog.ActionType.SEARCH,
            'get_user_bookings':    AIActionLog.ActionType.INFO_REQUEST,
            'get_user_preferences': AIActionLog.ActionType.INFO_REQUEST,
            'submit_tour_lead':     AIActionLog.ActionType.BOOK,
            'book_flight':          AIActionLog.ActionType.BOOK,
            'book_restaurant':      AIActionLog.ActionType.BOOK,
            'cancel_booking':       AIActionLog.ActionType.CANCEL,
        }.get(name, AIActionLog.ActionType.INFO_REQUEST)

    @staticmethod
    def _tool_to_service_type(name: str) -> str:
        return {
            'search_flights':    'flight',
            'book_flight':       'flight',
            'search_restaurants':'restaurant',
            'book_restaurant':   'restaurant',
            'search_events':     'event',
            'search_tour_packages': 'tour',
            'submit_tour_lead':  'tour',
        }.get(name, '')