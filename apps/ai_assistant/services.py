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


def get_ai_provider() -> BaseAIProvider:
    name = getattr(settings, 'AI_PROVIDER', 'gemini').lower()
    if name == 'claude':
        from .providers.claude_provider import ClaudeProvider
        return ClaudeProvider()
    from .providers.gemini_provider import GeminiProvider
    return GeminiProvider()


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

    def chat(self, user, message: str, session_id: str | None = None) -> dict:
        session = self.get_or_create_session(user, session_id)
        lang    = resolve_language(user, message)

        ConversationMessage.objects.create(
            session=session, role='user', content=message,
        )

        history = self._load_history(session)
        user_profile_summary = self._build_user_profile_summary(user)
        session_summary = self._build_session_summary(session)
        system  = build_system_prompt(
            lang=lang,
            price_limit=f"{user.ai_auto_price_limit:,.0f}",
            autonomy_level=user.ai_autonomy_level,
            session_summary=session_summary,
            user_profile_summary=user_profile_summary,
        )
        tools = get_all_tools()

        # AI chaqiruvi (timing + optional streaming)
        import time
        from apps.ai_assistant.providers.base import AIResponse as ProviderAIResponse

        try:
            start_ts = time.time()
            if getattr(settings, 'AI_ENABLE_STREAMING', False) and hasattr(self.provider, 'chat_stream'):
                chunks = []
                tool_calls = []
                tokens_used = 0
                raw = None
                for part in self.provider.chat_stream(messages=history, tools=tools, system=system):
                    if isinstance(part, dict) and part.get('__final'):
                        tokens_used = part.get('tokens_used', 0)
                        tool_calls = part.get('tool_calls', []) or []
                        raw = part.get('raw')
                    else:
                        chunks.append(str(part))
                content = ''.join(chunks)
                ai_response = ProviderAIResponse(content=content, tool_calls=tool_calls, tokens_used=tokens_used, raw=raw)
            else:
                ai_response = self.provider.chat(messages=history, tools=tools, system=system)
            end_ts = time.time()
            latency_ms = int((end_ts - start_ts) * 1000)
            # Audit log for AI call latency/tokens
            try:
                AIActionLog.objects.create(
                    user=user,
                    session=session,
                    action_type=AIActionLog.ActionType.INFO_REQUEST,
                    payload={'message': message, 'tokens_used': getattr(ai_response, 'tokens_used', 0), 'latency_ms': latency_ms},
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
            )
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
            tool_results, pending_action_id, pending_summary = (
                self._execute_tool_calls(user, session, ai_response.tool_calls, lang=lang)
            )

            if pending_action_id:
                # Tasdiqlash kerak — foydalanuvchiga savol
                final_content = pending_summary
            elif should_use_local_reply(tool_results, message, lang):
                # Token tejash: oddiy holatda tool natijasidan javob yig'amiz.
                # Vaqt/batafsil savollar va bo'sh tur natijalari uchun LLM ishlatiladi.
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
                    final_resp = self.provider.chat(
                        messages=history + tool_msgs,
                        tools=tools, system=system,
                        max_tokens=getattr(settings, 'AI_FOLLOWUP_MAX_TOKENS', 512),
                    )
                    final_content = (
                        final_resp.content
                        or build_reply_from_tools(tool_results, lang=lang)
                    )
                except Exception as e:
                    logger.exception('Tool result qayta chaqiruvda xato: %s', e)
                    final_content = build_reply_from_tools(tool_results, lang=lang) or t(
                        'reply_format_error', lang
                    )

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

        self._refresh_user_ai_profile(user, session)

        return {
            'session_id':            str(session.id),
            'message_id':            str(msg.id),
            'content':               final_content,
            'tool_calls_count':      len(ai_response.tool_calls),
            'tokens_used':           ai_response.tokens_used,
            'requires_confirmation': bool(pending_action_id),
            'pending_action_id':     str(pending_action_id) if pending_action_id else None,
        }

    # ── Ichki metodlar ────────────────────────────────────────────────────────

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
    ) -> tuple[list[dict], str | None, str]:
        """
        Returns: (results, pending_action_id | None, pending_summary)
        pending_action_id != None → biror tool tasdiqlash so'radi,
        keyingi tool'lar bajarilmaydi.
        """
        results = []

        for call in tool_calls:
            tool_name  = call['name']
            tool_input = call['input']

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
                    summary = build_confirmation_summary(
                        tool_name, tool_input, amount, lang=lang
                    )
                    logger.info(
                        'Tool [%s] tasdiqlash kerak: action_id=%s, user=%s',
                        tool_name, log.id, user.id,
                    )
                    # Keyingi tool'larni BAJARMAY to'xtatamiz
                    return [], str(log.id), summary

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
                logger.info('Tool [%s] idempotency hit: session=%s', tool_name, session.id)
                results.append({
                    'tool_use_id': call['id'],
                    'tool_name':   tool_name,
                    'result':      cached_result,
                })
                continue

            # O'qish tool'lari yoki full_auto/semi_auto (tasdiqlash shart emas)
            log_entry = AIActionLog(
                user=user,
                session=session,
                action_type=self._tool_to_action_type(tool_name),
                service_type=self._tool_to_service_type(tool_name),
                payload=tool_input,
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
                logger.info('Tool [%s] OK: user=%s', tool_name, user.id)
            except Exception as e:
                logger.exception('Tool [%s] XATO: user=%s — %s', tool_name, user.id, e)
                from apps.integrations.errors import integration_error_dict
                service = 'flight' if tool_name == 'search_flights' else 'generic'
                result = integration_error_dict(e, service=service, lang=lang)
                log_entry.result = result
                log_entry.status = AIActionLog.ActionStatus.FAILED
                log_entry.error_message = str(e)

            log_entry.save()
            results.append({
                'tool_use_id': call['id'],
                'tool_name':   tool_name,
                'result':      result,
            })

        return results, None, ''

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
        state_key = f"ai_tool_state:{session.id}"
        state = cache.get(state_key) or {}

        if tool_name == 'search_flights':
            state['last_flight_search'] = {
                'origin': tool_input.get('origin'),
                'destination': tool_input.get('destination'),
                'departure_at': tool_input.get('departure_at'),
                'count': len(result.get('flights', [])) if isinstance(result, dict) else 0,
            }
        elif tool_name == 'search_restaurants':
            state['last_restaurant_search'] = {
                'query': tool_input.get('query'),
                'date': tool_input.get('date'),
                'count': len(result.get('restaurants', [])) if isinstance(result, dict) else 0,
            }
        elif tool_name == 'search_tour_packages':
            state['last_tour_search'] = {
                'destination': tool_input.get('destination'),
                'query': tool_input.get('query'),
                'count': len(result.get('packages', [])) if isinstance(result, dict) else 0,
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