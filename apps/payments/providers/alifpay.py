"""
AlifPay to'lov provayderi — checkout (invoice) modeli.

Hujjat: https://docs.alifpay.uz/ru

Muhim farqlar Bookhara'dan:
  - Autentifikatsiya: "Token <token>" header'i (Bearer emas)
  - Barcha metodlar POST
  - HTTP 200 har doim qaytariladi — xato body'dagi "error" maydonida
  - Summa TIYINDA (1 so'm = 100 tiyin): # AlifPay tiyin kutadi, shu yerda *100 qilinadi
  - Prod:    https://api.alifpay.uz/v2
  - Sandbox: https://api-sandbox.alifpay.uz/v2  (ALIFPAY_TEST_MODE=True)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from decimal import Decimal

import httpx
from django.conf import settings

from .base import BasePaymentProvider, PaymentIntent, PaymentCheckResult, RefundResult

logger = logging.getLogger(__name__)

PROD_BASE_URL    = 'https://api.alifpay.uz/v2'
SANDBOX_BASE_URL = 'https://api-sandbox.alifpay.uz/v2'
CHECKOUT_PROD    = 'https://checkout.alifpay.uz'
CHECKOUT_SANDBOX = 'https://checkout-dev.alifpay.uz'


# ---------------------------------------------------------------------------
# Xatolik klasslari
# ---------------------------------------------------------------------------

class AlifPayError(Exception):
    """AlifPay API umumiy xatoligi."""
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class AlifPayAuthError(AlifPayError):
    """1002 — Avtorizatsiya xatosi."""


class AlifPayNotFoundError(AlifPayError):
    """1004 — Topilmadi."""


class AlifPayRejectedError(AlifPayError):
    """1007 — Rad etildi."""


class CardError(AlifPayError):
    """1102 — Karta ma'lumotlari noto'g'ri."""


class CardExpiredError(AlifPayError):
    """1103 — Karta muddati tugagan."""


class CardBlockedError(AlifPayError):
    """1107 — Karta bloklangan."""


class InsufficientFundsError(AlifPayError):
    """1108 — Mablag' yetarli emas."""


ERROR_CLASS_MAP: dict[int, type[AlifPayError]] = {
    1002: AlifPayAuthError,
    1004: AlifPayNotFoundError,
    1007: AlifPayRejectedError,
    1102: CardError,
    1103: CardExpiredError,
    1107: CardBlockedError,
    1108: InsufficientFundsError,
}

ERROR_MESSAGES: dict[int, str] = {
    1001: "Noto'g'ri so'rov",
    1002: "Avtorizatsiya xatosi",
    1004: "Topilmadi",
    1005: "Noto'g'ri parametrlar",
    1007: "Rad etildi",
    1102: "Karta ma'lumotlari noto'g'ri",
    1103: "Karta muddati tugagan",
    1107: "Karta bloklangan",
    1108: "Mablag' yetarli emas",
}


def _raise_for_alifpay_error(body: dict) -> None:
    """AlifPay HTTP 200 javobida error maydonini tekshirib, mos exception ko'taradi."""
    error = body.get('error')
    if not error:
        return
    code    = error.get('code') if isinstance(error, dict) else None
    message = (
        error.get('message') if isinstance(error, dict)
        else str(error)
    )
    message = message or ERROR_MESSAGES.get(code, f'AlifPay xatosi: {code}')

    exc_class = ERROR_CLASS_MAP.get(code, AlifPayError)
    raise exc_class(message, code=code)


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class AlifPayProvider(BasePaymentProvider):
    """
    AlifPay provayderi — invoice yaratish, holat tekshirish, qaytarish.
    """

    def __init__(self, token: str | None = None, secret_key: str | None = None):
        self.token      = token      or settings.ALIFPAY_TOKEN
        self.secret_key = secret_key or settings.ALIFPAY_SECRET_KEY
        self.test_mode  = getattr(settings, 'ALIFPAY_TEST_MODE', True)
        self.base_url   = SANDBOX_BASE_URL if self.test_mode else PROD_BASE_URL
        self._checkout  = CHECKOUT_SANDBOX if self.test_mode else CHECKOUT_PROD
        self._http      = httpx.Client(timeout=30)

    def get_provider_name(self) -> str:
        return 'alifpay'

    # -------------------------------------------------------------------
    # To'lov yaratish
    # -------------------------------------------------------------------

    def create_payment(
        self,
        order_id: str,
        amount: Decimal,
        description: str,
        return_url: str | None = None,
        extra: dict | None = None,
    ) -> PaymentIntent:
        """
        POST /invoice — yangi to'lov invoice'i yaratadi.

        Muhim: AlifPay summani TIYINDA kutadi.
        # AlifPay tiyin kutadi, shu yerda *100 qilinadi
        """
        extra = extra or {}
        # AlifPay tiyin kutadi, shu yerda *100 qilinadi
        amount_tiyin = int(amount * 100)

        body: dict = {
            'items': [
                {
                    'name':   description or f'IMTIAZ #{order_id}',
                    'amount': 1,
                    'price':  amount_tiyin,  # tiyin
                }
            ],
            'redirectUrl': return_url or '',
            'cancelUrl':   extra.get('cancel_url') or return_url or '',
            'webhookUrl':  getattr(settings, 'ALIFPAY_WEBHOOK_URL', ''),
            'meta':        {'order_id': str(order_id)},
            'receipt':     True,
        }
        phone = extra.get('phone')
        if phone:
            body['phone'] = phone

        try:
            resp_body = self._post('/invoice', body)
        except AlifPayError as exc:
            logger.error('AlifPay invoice xatosi: order_id=%s, %s', order_id, exc)
            return PaymentIntent(success=False, error_message=str(exc))

        invoice_id  = resp_body.get('id') or resp_body.get('invoiceId')
        payment_url = f'{self._checkout}/?invoice={invoice_id}' if invoice_id else None

        return PaymentIntent(
            success=bool(invoice_id),
            external_transaction_id=str(invoice_id) if invoice_id else None,
            payment_url=payment_url,
            error_message='' if invoice_id else 'AlifPay invoice ID topilmadi',
            raw=resp_body,
        )

    # -------------------------------------------------------------------
    # Holat tekshirish
    # -------------------------------------------------------------------

    def check_status(self, external_transaction_id: str) -> PaymentCheckResult:
        """POST /getInvoice — invoice holati."""
        try:
            resp_body = self._post('/getInvoice', {'id': external_transaction_id})
        except AlifPayError as exc:
            logger.warning('AlifPay getInvoice xatosi: %s', exc)
            return PaymentCheckResult(is_paid=False, is_failed=True, error_message=str(exc))

        payment = resp_body.get('payment') or {}
        status  = payment.get('status', '')
        is_paid = status == 'SUCCEEDED'
        is_failed = status in ('FAILED', 'CANCELLED', 'EXPIRED')

        # Receipt URL — keyinroq FlightPayment'ga saqlanadi
        receipt_url = None
        results = (payment.get('receipt') or {}).get('results', [])
        if results and isinstance(results, list):
            receipt_url = results[0].get('url')

        raw = resp_body
        if receipt_url:
            raw = {**resp_body, '_receipt_url': receipt_url}

        return PaymentCheckResult(
            is_paid=is_paid,
            is_failed=is_failed,
            amount_paid=Decimal(str(payment.get('amount', 0))) / 100 if is_paid else None,
            raw=raw,
        )

    # -------------------------------------------------------------------
    # Qaytarish
    # -------------------------------------------------------------------

    def refund(
        self,
        external_transaction_id: str,
        amount: Decimal | None = None,
    ) -> RefundResult:
        """POST /refundInvoice — to'lovni qaytarish.

        AlifPay faqat to'liq qaytarishni qo'llaydi.
        Qisman qaytarish (amount != None) so'ralsa NotImplementedError ko'tariladi.
        """
        if amount is not None:
            raise NotImplementedError(
                'AlifPay qisman qaytarishni (partial refund) qo\'llab-quvvatlamaydi. '
                'Faqat to\'liq qaytarish mumkin (amount=None).'
            )
        try:
            resp_body = self._post('/refundInvoice', {'id': external_transaction_id})
        except AlifPayError as exc:
            logger.error('AlifPay refund xatosi: %s', exc)
            return RefundResult(success=False, error_message=str(exc))

        return RefundResult(success=True, raw=resp_body)

    # -------------------------------------------------------------------
    # Ichki yordamchi
    # -------------------------------------------------------------------

    def _post(self, path: str, body: dict) -> dict:
        """AlifPay API'ga POST yuboradi va javobni tekshiradi."""
        url = f'{self.base_url}{path}'
        resp = self._http.post(
            url,
            json=body,
            headers={
                'Token':        self.token,
                'Content-Type': 'application/json',
                'Accept':       'application/json',
            },
        )
        resp.raise_for_status()
        resp_body = resp.json()
        _raise_for_alifpay_error(resp_body)
        return resp_body


# ---------------------------------------------------------------------------
# Webhook signature tekshiruvi (views.py da ishlatiladi)
# ---------------------------------------------------------------------------

def verify_alifpay_signature(body: bytes, secret_key: str, received: str) -> bool:
    """
    AlifPay webhook imzosini tekshiradi.
    HMAC-SHA256(body, secret_key) → Base64 → received bilan taqqoslash.
    hmac.compare_digest — timing attack'dan himoya.
    """
    expected = base64.b64encode(
        hmac.new(secret_key.encode('utf-8'), body, hashlib.sha256).digest()
    ).decode('utf-8')
    return hmac.compare_digest(expected, received)
