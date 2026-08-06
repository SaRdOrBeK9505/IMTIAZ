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

import json
import logging

from django.conf import settings

from .confirmation import create_pending_action, requires_confirmation
from .models import ConversationSession, ConversationMessage, AIActionLog
from .providers.base import BaseAIProvider, AIMessage
from .tools import get_all_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Sen IMTIAZ — premium lifestyle concierge platformasining AI assistantisan.

IMTIAZ — Yandex Go/Market kabi super-app: parvoz, poyezd, restoran, \
sport, salomatlik va eksklyuziv tadbirlar. Premium a\'zolar uchun.

SENIN VAZIFANG:
- Xizmatlarni topish, taqqoslash va bron qilishda yordam berish
- Eng yaqin, qulay va mos variantlarni taklif qilish
- Manzillarni tahlil qilish — eng yaqin va qulay variantni tanlash
- Foydalanuvchi ruxsatiga qarab bron qilish

MUHIM QOIDALAR:
1. FAQAT IMTIAZ mavzularida: sayohat, restoran, tadbirlar, xizmatlar
2. Boshqa mavzularda: "Men faqat IMTIAZ xizmatlari haqida yordam bera olaman."
3. Avtonomiya: {autonomy_level}
   - manual: har bir bron/bekor uchun tasdiqlash so\'ra
   - semi_auto: 300,000 UZS gacha mustaqil, undan yuqori — tasdiqlash
   - full_auto: {price_limit} UZS gacha mustaqil
4. Foydalanuvchi tilida javob ber
5. Professional va mehribon bo\'l

MAVZU CHEGARALARI:
Siyosat, din, umumiy yangiliklar, matematika, tarix, tibbiy/huquqiy maslahat
"""

# Yozish tool'lari — requires_confirmation() ga yuboriladi
WRITE_TOOL_TO_ACTION: dict[str, tuple[str, str]] = {
    'book_flight':      ('book',   'flight'),
    'book_restaurant':  ('book',   'restaurant'),
    'cancel_booking':   ('cancel', ''),
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

    def chat(self, user, message: str, session_id: str | None = None) -> dict:
        session = self.get_or_create_session(user, session_id)

        ConversationMessage.objects.create(
            session=session, role='user', content=message,
        )

        history = self._load_history(session)
        system  = SYSTEM_PROMPT.format(
            price_limit=f"{user.ai_auto_price_limit:,.0f}",
            autonomy_level=user.ai_autonomy_level,
        )
        tools = get_all_tools()

        # AI chaqiruvi
        try:
            ai_response = self.provider.chat(
                messages=history, tools=tools, system=system,
            )
        except Exception as e:
            logger.exception('AI provider xatosi: %s', e)
            err = "Kechirasiz, texnik muammo. Qayta urinib ko'ring."
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
                self._execute_tool_calls(user, session, ai_response.tool_calls)
            )

            if pending_action_id:
                # Tasdiqlash kerak — foydalanuvchiga savol
                final_content = pending_summary
            else:
                # Barcha tool'lar bajarildi — AI'ga natijalarni ber
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
                                'content':     json.dumps(r['result'], ensure_ascii=False),
                            }
                            for r in tool_results
                        ],
                    ),
                ]
                try:
                    final_resp    = self.provider.chat(
                        messages=history + tool_msgs,
                        tools=tools, system=system,
                    )
                    final_content = final_resp.content
                except Exception as e:
                    logger.exception('Tool result qayta chaqiruvda xato: %s', e)

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
        rows = (
            session.messages
            .order_by('created_at')
            .values('role', 'content')[:50]
        )
        return [AIMessage(role=r['role'], content=r['content']) for r in rows]

    def _execute_tool_calls(
        self,
        user,
        session: ConversationSession,
        tool_calls: list[dict],
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
                    summary = self._build_confirmation_summary(tool_name, tool_input, amount)
                    logger.info(
                        'Tool [%s] tasdiqlash kerak: action_id=%s, user=%s',
                        tool_name, log.id, user.id,
                    )
                    # Keyingi tool'larni BAJARMAY to'xtatamiz
                    return [], str(log.id), summary

            # O'qish tool'lari yoki full_auto/semi_auto (tasdiqlash shart emas)
            log_entry = AIActionLog(
                user=user,
                session=session,
                action_type=self._tool_to_action_type(tool_name),
                service_type=self._tool_to_service_type(tool_name),
                payload=tool_input,
            )
            try:
                result         = self._dispatch_tool(user, tool_name, tool_input)
                log_entry.result = result
                log_entry.status = AIActionLog.ActionStatus.SUCCESS
                logger.info('Tool [%s] OK: user=%s', tool_name, user.id)
            except Exception as e:
                logger.exception('Tool [%s] XATO: user=%s — %s', tool_name, user.id, e)
                result               = {'error': str(e)}
                log_entry.result     = result
                log_entry.status     = AIActionLog.ActionStatus.FAILED
                log_entry.error_message = str(e)

            log_entry.save()
            results.append({
                'tool_use_id': call['id'],
                'tool_name':   tool_name,
                'result':      result,
            })

        return results, None, ''

    @staticmethod
    def _dispatch_tool(user, tool_name: str, tool_input: dict) -> dict:
        from .tool_handlers import TOOL_DISPATCH
        handler = TOOL_DISPATCH.get(tool_name)
        if not handler:
            raise ValueError(f"Noma'lum tool: {tool_name!r}")
        return handler(user=user, **tool_input)

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
    def _build_confirmation_summary(
        tool_name: str, tool_input: dict, amount: 'Decimal | None'
    ) -> str:
        amount_str = f"\n💰 Taxminiy narx: {amount:,.0f} UZS" if amount else ''
        if tool_name == 'book_flight':
            return (
                f"✈️ Parvoz bron so'rovi:\n"
                f"📍 {tool_input.get('origin', '?')} → {tool_input.get('destination', '?')}\n"
                f"📅 {tool_input.get('departure_at', tool_input.get('departure_date', '?'))}\n"
                f"👥 {tool_input.get('passengers', 1)} yo'lovchi"
                f"{amount_str}\n\n"
                f"Tasdiqlash uchun ilovadagi «✅ Tasdiqlash» tugmasini bosing."
            )
        if tool_name == 'book_restaurant':
            return (
                f"🍽 Restoran bron so'rovi:\n"
                f"📅 {tool_input.get('date', '?')} {tool_input.get('time', '?')}\n"
                f"👥 {tool_input.get('guests', '?')} kishi"
                f"{amount_str}\n\n"
                f"Tasdiqlash uchun ilovadagi «✅ Tasdiqlash» tugmasini bosing."
            )
        if tool_name == 'cancel_booking':
            return (
                f"❌ Bronni bekor qilish so'rovi:\n"
                f"🆔 {tool_input.get('booking_id', '?')}\n\n"
                f"Tasdiqlash uchun ilovadagi «✅ Tasdiqlash» tugmasini bosing."
            )
        return f"Harakat: {tool_name}\n\nTasdiqlash uchun «✅ Tasdiqlash» tugmasini bosing."

    @staticmethod
    def _tool_to_action_type(name: str) -> str:
        return {
            'search_flights':       AIActionLog.ActionType.SEARCH,
            'search_trains':        AIActionLog.ActionType.SEARCH,
            'search_restaurants':   AIActionLog.ActionType.SEARCH,
            'search_events':        AIActionLog.ActionType.SEARCH,
            'get_nearby_places':    AIActionLog.ActionType.SEARCH,
            'get_user_bookings':    AIActionLog.ActionType.INFO_REQUEST,
            'get_user_preferences': AIActionLog.ActionType.INFO_REQUEST,
            'book_flight':          AIActionLog.ActionType.BOOK,
            'book_restaurant':      AIActionLog.ActionType.BOOK,
            'cancel_booking':       AIActionLog.ActionType.CANCEL,
        }.get(name, AIActionLog.ActionType.INFO_REQUEST)

    @staticmethod
    def _tool_to_service_type(name: str) -> str:
        return {
            'search_flights':    'flight',
            'book_flight':       'flight',
            'search_trains':     'train',
            'search_restaurants':'restaurant',
            'book_restaurant':   'restaurant',
            'search_events':     'event',
        }.get(name, '')
