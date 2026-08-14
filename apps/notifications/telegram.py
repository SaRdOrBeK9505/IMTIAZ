"""
Telegram Bot client — bildirishnomalar yuborish.
httpx async emas, sync — Celery task ichida ishlaydi.
"""

from __future__ import annotations

import logging
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = 'https://api.telegram.org/bot{token}'


class TelegramBotClient:
    """Telegram Bot API orqali xabar yuboradi."""

    def __init__(self):
        self.token  = settings.TELEGRAM_BOT_TOKEN
        self.base   = TELEGRAM_API.format(token=self.token)
        self.client = httpx.Client(timeout=15)

    def send_message(
        self,
        chat_id:    int,
        text:       str,
        parse_mode: str = 'HTML',
        reply_markup: dict | None = None,
    ) -> int | None:
        """
        Xabar yuboradi.
        Returns: telegram message_id yoki None (xato bo'lsa)
        """
        if not self.token:
            logger.warning('TELEGRAM_BOT_TOKEN sozlanmagan — xabar yuborilmadi')
            return None

        payload: dict = {
            'chat_id':    chat_id,
            'text':       text,
            'parse_mode': parse_mode,
        }
        if reply_markup:
            payload['reply_markup'] = reply_markup

        try:
            resp = self.client.post(f'{self.base}/sendMessage', json=payload)
            data = resp.json()

            if not data.get('ok'):
                error_code = data.get('error_code', 0)
                description = data.get('description', '')

                # Foydalanuvchi botni bloklagan
                if error_code in (403, 400) and 'blocked' in description.lower():
                    logger.warning('Foydalanuvchi botni bloklagan: chat_id=%s', chat_id)
                    return None

                logger.error(
                    'Telegram API xato: code=%s, desc=%s, chat_id=%s',
                    error_code, description, chat_id,
                )
                return None

            message_id = data['result']['message_id']
            logger.debug('Telegram xabar yuborildi: chat_id=%s, msg_id=%s', chat_id, message_id)
            return message_id

        except httpx.TimeoutException:
            logger.error('Telegram API timeout: chat_id=%s', chat_id)
            return None
        except Exception as e:
            logger.exception('Telegram xabar yuborishda kutilmagan xato: %s', e)
            return None

    def _api_post(self, method: str, payload: dict) -> dict | None:
        if not self.token:
            return None
        try:
            resp = self.client.post(f'{self.base}/{method}', json=payload)
            data = resp.json()
            if not data.get('ok'):
                logger.error(
                    'Telegram API xato [%s]: %s',
                    method, data.get('description', ''),
                )
                return None
            return data
        except Exception as e:
            logger.exception('Telegram API [%s] xato: %s', method, e)
            return None

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
    ) -> bool:
        payload: dict = {'callback_query_id': callback_query_id}
        if text:
            payload['text'] = text
        return self._api_post('answerCallbackQuery', payload) is not None

    def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str = 'HTML',
        reply_markup: dict | None = None,
    ) -> bool:
        payload: dict = {
            'chat_id':      chat_id,
            'message_id':   message_id,
            'text':         text,
            'parse_mode':   parse_mode,
        }
        if reply_markup:
            payload['reply_markup'] = reply_markup
        return self._api_post('editMessageText', payload) is not None

    def send_booking_confirmation(self, chat_id: int, booking) -> int | None:
        """Bron tasdiqlash xabarini yuboradi."""
        text = (
            f"✅ <b>Bron tasdiqlandi</b>\n\n"
            f"📋 <b>{booking.title}</b>\n"
            f"🆔 Bron ID: <code>{str(booking.id)[:8]}...</code>\n"
            f"💰 Narx: <b>{booking.final_price:,.0f} UZS</b>\n"
            f"📅 Sana: {booking.booking_date.strftime('%d.%m.%Y %H:%M') if booking.booking_date else '—'}\n\n"
            f"<i>IMTIAZ — premium lifestyle concierge</i>"
        )
        return self.send_message(chat_id, text)

    def send_booking_reminder(self, chat_id: int, booking, hours_before: int = 2) -> int | None:
        """Bron oldidan eslatma."""
        text = (
            f"⏰ <b>Eslatma: {hours_before} soatdan so'ng</b>\n\n"
            f"📋 <b>{booking.title}</b>\n"
            f"📅 {booking.booking_date.strftime('%d.%m.%Y %H:%M') if booking.booking_date else '—'}\n\n"
            f"Vaqtni unutmang! 🙏"
        )
        return self.send_message(chat_id, text)

    def send_payment_success(self, chat_id: int, amount, currency: str = 'UZS') -> int | None:
        """To'lov muvaffaqiyatli xabari."""
        text = (
            f"💳 <b>To'lov qabul qilindi</b>\n\n"
            f"💰 Summa: <b>{amount:,.0f} {currency}</b>\n\n"
            f"Rahmat! Xizmatdan bahramand bo'ling 🌟"
        )
        return self.send_message(chat_id, text)

    def send_waitlist_approved(self, chat_id: int, tier_name: str) -> int | None:
        """A'zolik tasdiqlangani haqida xabar."""
        text = (
            f"🎉 <b>Tabriklaymiz! A'zolikka qabul qilindingiz</b>\n\n"
            f"🏆 Daraja: <b>{tier_name}</b>\n\n"
            f"Endi barcha IMTIAZ xizmatlaridan to'liq foydalanishingiz mumkin!\n"
            f"AI assistant bilan suhbatni boshlang 👇"
        )
        return self.send_message(chat_id, text)


# Singleton
_bot_client: TelegramBotClient | None = None


def get_bot() -> TelegramBotClient:
    global _bot_client
    if _bot_client is None:
        _bot_client = TelegramBotClient()
    return _bot_client
