"""
DevSMS Gateway integratsiyasi.
https://devsms.uz

API:
    POST https://devsms.uz/api/send_sms.php
    Headers: Authorization: Bearer <token>
    Body:    {"phone": "998901234567", "message": "..."}

# ── Eskiz (o'chirildi) ────────────────────────────────────────────────────────
# Eskiz SMS Gateway avval ishlatilgan, hozir DevSMS ga o'tildi.
# Qayta yoqish uchun:
#   1. settings.py ga ESKIZ_EMAIL, ESKIZ_PASSWORD, ESKIZ_FROM qaytaring
#   2. shu faylning oxiridagi EskizSMSClient klassini uncomment qiling
#   3. send_otp_sms() ichida DevSmsSMSClient o'rniga EskizSMSClient ishlating
# ─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class DevSmsClient:
    """
    DevSMS SMS Gateway client.
    Bearer token to'g'ridan-to'g'ri settings'dan olinadi —
    Eskiz'dan farqli, har safar login kerak emas.
    """

    def __init__(self):
        self.token    = settings.DEVSMS_TOKEN
        self.base_url = settings.DEVSMS_BASE_URL
        self.client   = httpx.Client(timeout=10)

    def send(self, phone: str, message: str) -> bool:
        """
        SMS yuboradi.

        Args:
            phone:   '998901234567' yoki '+998901234567' — har ikkalasi qabul qilinadi
            message: SMS matni

        Returns:
            True — muvaffaqiyatli, False — xato
        """
        # + belgini olib tashlash
        phone = phone.strip().lstrip('+').replace(' ', '').replace('-', '')

        try:
            resp = self.client.post(
                self.base_url,
                headers={
                    'Authorization': f'Bearer {self.token}',
                    'Content-Type':  'application/json',
                },
                json={
                    'phone':   phone,
                    'message': message,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info('DevSMS yuborildi → %s | javob: %s', phone, data)
            # DevSMS muvaffaqiyatli javob: {"status": "success"} yoki {"id": ...}
            # Javob strukturasi aniqlanguncha har qanday 2xx — muvaffaqiyatli
            return True

        except httpx.HTTPStatusError as e:
            logger.error('DevSMS HTTP xato [%s]: %s — %s', phone, e.response.status_code, e.response.text)
            return False
        except Exception as e:
            logger.exception('DevSMS yuborishda xato [%s]: %s', phone, e)
            return False


def send_otp_sms(phone: str, code: str) -> bool:
    """OTP SMS yuborish — asosiy funksiya."""
    message = f'IMTIAZ: tasdiqlash kodi {code}. Amal qilish muddati 5 daqiqa. Hech kimga bermang.'
    client = DevSmsClient()
    return client.send(phone, message)


# ── Eskiz (comment qilingan) ──────────────────────────────────────────────────
#
# ESKIZ_BASE_URL  = 'https://notify.eskiz.uz/api'
# TOKEN_CACHE_KEY = 'eskiz_api_token'
# TOKEN_CACHE_TTL = 60 * 60 * 23  # 23 soat
#
# class EskizSMSClient:
#     def __init__(self):
#         self.email    = settings.ESKIZ_EMAIL
#         self.password = settings.ESKIZ_PASSWORD
#         self.nick     = settings.ESKIZ_FROM
#         self.client   = httpx.Client(base_url=ESKIZ_BASE_URL, timeout=15)
#
#     def _get_token(self) -> str:
#         from django.core.cache import cache
#         token = cache.get(TOKEN_CACHE_KEY)
#         return token if token else self._refresh_token()
#
#     def _refresh_token(self) -> str:
#         from django.core.cache import cache
#         resp = self.client.post('/auth/login',
#                                 data={'email': self.email, 'password': self.password})
#         resp.raise_for_status()
#         token = resp.json()['data']['token']
#         cache.set(TOKEN_CACHE_KEY, token, TOKEN_CACHE_TTL)
#         return token
#
#     def send(self, phone: str, message: str) -> bool:
#         phone = phone.strip().replace(' ', '').replace('-', '')
#         if not phone.startswith('+'): phone = '+' + phone
#         token = self._get_token()
#         try:
#             resp = self.client.post('/message/sms/send',
#                 data={'mobile_phone': phone, 'message': message,
#                       'from': self.nick, 'callback_url': ''},
#                 headers={'Authorization': f'Bearer {token}'})
#             if resp.status_code == 401:
#                 from django.core.cache import cache
#                 cache.delete(TOKEN_CACHE_KEY)
#                 return self.send(phone, message)
#             resp.raise_for_status()
#             return resp.json().get('status') == 'waiting'
#         except Exception as e:
#             logger.exception('Eskiz SMS xato [%s]: %s', phone, e)
#             return False
