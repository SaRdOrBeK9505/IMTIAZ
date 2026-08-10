"""
Bookhara adapter — yuqori darajali (high-level) API wrapper.

Bu modul BookharaClient (low-level HTTP client) ustiga qurilgan bolib,
Bookhara avia-provayderining barcha 19 ta endpointini domenga mos
metodlar sifatida taqdim etadi: qidiruv, narx tekshirish, bron qilish,
tolov, bekor qilish va qaytarish (refund) operatsiyalari.

Har bir tashqi chaqiruv ExternalProviderLog orqali loglanadi va hech
qachon istisno (exception) tashlamaydi — logging xatosi asosiy oqimni
buzmasligi kerak.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from .bookhara_client import BookharaClient
from .base import FlightOffer, BookingResult, FlightProviderAdapter
from ..models import ExternalProviderLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Xatolik klasslari
# ---------------------------------------------------------------------------

class BookharaError(Exception):
    """Bookhara provayderidan qaytgan umumiy xatolik uchun asosiy klass."""

    def __init__(self, message: str, error_code: str | None = None, raw: dict | None = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.raw = raw or {}


class BookingDuplicateError(BookharaError):
    """Bron allaqachon mavjud (error_code: 5231, 5232)."""


class BookingOfferExpiredError(BookharaError):
    """Taklif (offer) muddati tugagan yoki topilmadi (HTTP 404/410)."""


class BookharaPriceChangedError(BookharaError):
    """Narx ozgargan holatda tashlanadi."""

    def __init__(self, message: str, new_price: Decimal | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.new_price = new_price


class PaymentNotAllowedError(BookharaError):
    """Tolov ruxsati berilmagan (payment_allowed=False)."""


# ---------------------------------------------------------------------------
# Konstantalar
# ---------------------------------------------------------------------------

DUPLICATE_CODES = {'5231', '5232'}
EXPIRED_CODES = {'404', '410'}
PRICE_CHANGED_CODES = {'100500', '1030', '1031'}
REFUND_MISSING_CODE = '5233'

BOOKHARA_STATUS_MAP = {
    'booked': 'pending',
    'awaitpayment': 'pending',
    'paid': 'pending',
    'ticketed': 'confirmed',
    'partiallyticketed': 'confirmed',
    'refundauthorized': 'refunded',
    'partiallyrefunded': 'refunded',
    'refunded': 'refunded',
    'cancelled': 'cancelled',
}


class BookharaAdapter(FlightProviderAdapter):
    """Bookhara avia-provayderi uchun yuqori darajali adapter."""

    PROVIDER_NAME = 'bookhara'

    def __init__(self, client: BookharaClient | None = None):
        self.client = client or BookharaClient()

    # -------------------------------------------------------------------
    # 1. Balansni tekshirish
    # -------------------------------------------------------------------

    def check_balance(self) -> dict:
        """GET /api/v1/accounts/check-balance"""
        data = self._call('check_balance', lambda: self.client.get('/api/v1/accounts/check-balance'))
        return {
            'deposit': data.get('deposit'),
            'credit': data.get('credit'),
            'currency': data.get('currency', 'UZS'),
        }

    # -------------------------------------------------------------------
    # 2. Qidiruv
    # -------------------------------------------------------------------

    def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: int = 1,
        seat_class: str = 'economy',
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        """GET /api/v1/offers"""
        params: dict = {
            'origin': origin,
            'destination': destination,
            'departure_date': departure_date,
            'passengers': passengers,
            'seat_class': seat_class,
        }
        if return_date:
            params['return_date'] = return_date

        data = self._call('search', lambda: self.client.get('/api/v1/offers', params=params))
        offers_raw = data.get('offers') or data.get('data') or []
        offers: list[FlightOffer] = []
        for raw_offer in offers_raw:
            try:
                offers.append(self._parse_offer(raw_offer))
            except (KeyError, IndexError, InvalidOperation) as exc:
                logger.warning('Bookhara offer parse xatosi: %s | raw=%s', exc, raw_offer)
        return offers

    # -------------------------------------------------------------------
    # 3. Fare family
    # -------------------------------------------------------------------

    def get_fare_family(self, offer_id: str) -> list[dict]:
        """GET /api/v1/offers/{id}/fare-family"""
        data = self._call(
            'get_fare_family',
            lambda: self.client.get(f'/api/v1/offers/{offer_id}/fare-family'),
        )
        return data if isinstance(data, list) else data.get('data', [])

    # -------------------------------------------------------------------
    # 4. Narxni olish
    # -------------------------------------------------------------------

    def get_price(self, offer_id: str) -> Decimal:
        """GET /api/v1/offers/{id}"""
        data = self._call('get_price', lambda: self.client.get(f'/api/v1/offers/{offer_id}'))
        price = data.get('price') or data.get('total_price')
        if price is None and 'data' in data:
            price = data['data'].get('price')
        return Decimal(str(price))

    # -------------------------------------------------------------------
    # 5. Offer qoidalari
    # -------------------------------------------------------------------

    def get_offer_rules(self, offer_id: str) -> list[dict] | None:
        """GET /api/v1/offers/{id}/rules — 410 bolsa None qaytaradi."""
        try:
            data = self._call(
                'get_offer_rules',
                lambda: self.client.get(f'/api/v1/offers/{offer_id}/rules'),
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 410:
                return None
            raise
        return data if isinstance(data, list) else data.get('data', [])

    # -------------------------------------------------------------------
    # 6. Bron yaratish
    # -------------------------------------------------------------------

    def create_booking(self, offer_id: str, passengers: list[dict], **kwargs) -> BookingResult:
        """POST /api/v1/offers/{id}/booking"""
        body: dict = {'offer_id': offer_id, 'passengers': passengers, **kwargs}
        start = time.monotonic()
        try:
            data = self.client.post(f'/api/v1/offers/{offer_id}/booking', body)
        except httpx.HTTPStatusError as exc:
            error_code = self._extract_error_code(exc)
            error_message = self._extract_error_message(exc)
            self._log(
                'create_booking', body, self._safe_json(exc),
                exc.response.status_code, False, self._elapsed_ms(start),
            )
            if error_code in DUPLICATE_CODES:
                raise BookingDuplicateError(error_message, error_code=error_code) from exc
            if error_code in EXPIRED_CODES:
                raise BookingOfferExpiredError(error_message, error_code=error_code) from exc
            return BookingResult(
                success=False,
                external_booking_id=None,
                confirmation_code=None,
                error_message=error_message,
                error_code=error_code,
                raw=self._safe_json(exc),
            )
        self._log('create_booking', body, data, 200, True, self._elapsed_ms(start))
        return BookingResult(
            success=True,
            external_booking_id=data.get('id') or data.get('booking_id'),
            confirmation_code=data.get('pnr') or data.get('confirmation_code'),
            error_message='',
            error_code=None,
            raw=data,
        )

    # -------------------------------------------------------------------
    # 7. Bron malumotlarini olish
    # -------------------------------------------------------------------

    def get_booking(self, booking_id: str) -> dict:
        """GET /api/v1/booking/{id}"""
        return self._call(
            'get_booking',
            lambda: self.client.get(f'/api/v1/booking/{booking_id}'),
        )

    # -------------------------------------------------------------------
    # 8. Bron qoidalari
    # -------------------------------------------------------------------

    def get_booking_rules(self, booking_id: str) -> list[dict] | None:
        """GET /api/v1/booking/{id}/rules — 404/410 bolsa None."""
        try:
            data = self._call(
                'get_booking_rules',
                lambda: self.client.get(f'/api/v1/booking/{booking_id}/rules'),
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 410):
                return None
            raise
        return data if isinstance(data, list) else data.get('data', [])

    # -------------------------------------------------------------------
    # 9. Narx ozgarishini tekshirish
    # -------------------------------------------------------------------

    def check_price(self, booking_id: str) -> dict:
        """GET /api/v1/booking/{id}/check-price"""
        start = time.monotonic()
        try:
            data = self.client.get(f'/api/v1/booking/{booking_id}/check-price')
        except httpx.HTTPStatusError as exc:
            error_code = self._extract_error_code(exc)
            self._log(
                'check_price', {'booking_id': booking_id}, self._safe_json(exc),
                exc.response.status_code, False, self._elapsed_ms(start),
                booking_id=booking_id,
            )
            if error_code in PRICE_CHANGED_CODES:
                new_price_raw = self._safe_json(exc).get('new_price')
                raise BookharaPriceChangedError(
                    self._extract_error_message(exc),
                    new_price=Decimal(str(new_price_raw)) if new_price_raw is not None else None,
                    error_code=error_code,
                ) from exc
            raise
        self._log(
            'check_price', {'booking_id': booking_id}, data, 200, True,
            self._elapsed_ms(start), booking_id=booking_id,
        )
        is_changed = bool(data.get('is_price_changed'))
        new_price_raw = data.get('new_price')
        return {
            'is_price_changed': is_changed,
            'new_price': Decimal(str(new_price_raw)) if new_price_raw is not None else None,
        }

    # -------------------------------------------------------------------
    # 10. Tolov ruxsatini tekshirish
    # -------------------------------------------------------------------

    def check_payment_permission(self, booking_id: str) -> bool:
        """GET /api/v1/booking/{id}/payment-permission"""
        data = self._call(
            'check_payment_permission',
            lambda: self.client.get(f'/api/v1/booking/{booking_id}/payment-permission'),
            booking_id=booking_id,
        )
        return bool(data.get('payment_allowed') or data.get('allowed'))

    # -------------------------------------------------------------------
    # 11. Tolovni amalga oshirish
    # -------------------------------------------------------------------

    def pay_booking(self, booking_id: str) -> dict:
        """POST /api/v1/booking/{id}/payment

        Majburiy tartib:
          1. check_payment_permission() — False bolsa PaymentNotAllowedError
          2. check_price()              — narx ozgargan bolsa BookharaPriceChangedError
          3. Haqiqiy tolov sorovi
        """
        if not self.check_payment_permission(booking_id):
            raise PaymentNotAllowedError(
                "Bookhara: ushbu bron uchun tolovga ruxsat berilmagan",
                error_code=None,
            )
        price_check = self.check_price(booking_id)
        if price_check['is_price_changed']:
            raise BookharaPriceChangedError(
                "Bookhara: tolovdan oldin narx ozgargan",
                new_price=price_check['new_price'],
            )
        data = self._call(
            'pay_booking',
            lambda: self.client.post(f'/api/v1/booking/{booking_id}/payment', {}),
            booking_id=booking_id,
        )
        return {
            'status': data.get('status'),
            'fiscalization_v2': data.get('fiscalization_v2', {}),
        }

    # -------------------------------------------------------------------
    # 12. Fiskalizatsiya malumotlari
    # -------------------------------------------------------------------

    def get_fiscalization(self, booking_id: str) -> dict:
        """GET /api/v1/booking/{id}/fiscalization

        Faqat bron paid/ticketed holatida chaqirilishi kerak.
        """
        return self._call(
            'get_fiscalization',
            lambda: self.client.get(f'/api/v1/booking/{booking_id}/fiscalization'),
            booking_id=booking_id,
        )

    # -------------------------------------------------------------------
    # 13. Bronni bekor qilish (void)
    # -------------------------------------------------------------------

    def void_booking(self, booking_id: str) -> dict:
        """DELETE /api/v1/booking/{id}/void"""
        return self._call(
            'void_booking',
            lambda: self.client.delete(f'/api/v1/booking/{booking_id}/void'),
            booking_id=booking_id,
        )

    # -------------------------------------------------------------------
    # 14. Qaytarish summasini olish
    # -------------------------------------------------------------------

    def get_refund_amounts(self, booking_id: str) -> dict:
        """GET /api/v1/booking/{id}/get-refund-amounts

        422 + error_code 5233 bolsa exception emas, {'refund_available': False}.
        """
        start = time.monotonic()
        try:
            data = self.client.get(f'/api/v1/booking/{booking_id}/get-refund-amounts')
        except httpx.HTTPStatusError as exc:
            error_code = self._extract_error_code(exc)
            self._log(
                'get_refund_amounts', {'booking_id': booking_id}, self._safe_json(exc),
                exc.response.status_code, False, self._elapsed_ms(start),
                booking_id=booking_id,
            )
            if exc.response.status_code == 422 and error_code == REFUND_MISSING_CODE:
                return {'refund_available': False}
            raise
        self._log(
            'get_refund_amounts', {'booking_id': booking_id}, data, 200, True,
            self._elapsed_ms(start), booking_id=booking_id,
        )
        return {
            'refund_amount': data.get('refund_amount'),
            'penalty': data.get('penalty'),
            'currency': data.get('currency'),
            'refund_available': True,
        }

    # -------------------------------------------------------------------
    # 15. Avtomatik bekor qilish
    # -------------------------------------------------------------------

    def auto_cancel_booking(self, booking_id: str) -> dict:
        """DELETE /api/v1/booking/{id}/auto-cancel"""
        return self._call(
            'auto_cancel_booking',
            lambda: self.client.delete(f'/api/v1/booking/{booking_id}/auto-cancel'),
            booking_id=booking_id,
        )

    # -------------------------------------------------------------------
    # 16. Qolda qaytarish sorovi
    # -------------------------------------------------------------------

    def request_manual_refund(self, booking_id: str) -> dict:
        """DELETE /api/v1/booking/{id}/manual-refund"""
        return self._call(
            'request_manual_refund',
            lambda: self.client.delete(f'/api/v1/booking/{booking_id}/manual-refund'),
            booking_id=booking_id,
        )

    # -------------------------------------------------------------------
    # 17. cancel_booking — FlightProviderAdapter abstrakt metodi
    # -------------------------------------------------------------------

    def cancel_booking(self, external_booking_id: str) -> BookingResult:
        """Smart dispatch: qaysi cancel turi ishlashini ketma-ket sinaydi.

          1. void_booking()           — 410 kelsa keyingisiga otadi
          2. auto_cancel_booking()    — muvaffaqiyatsiz bolsa keyingisiga otadi
          3. request_manual_refund()  — oxirgi variant
        """
        try:
            data = self.void_booking(external_booking_id)
            return BookingResult(
                success=True, external_booking_id=external_booking_id,
                confirmation_code=None, error_message='', error_code=None, raw=data,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 410:
                logger.info(
                    'Bookhara void_booking muvaffaqiyatsiz, auto-cancel sinaladi: %s', exc,
                )

        try:
            data = self.auto_cancel_booking(external_booking_id)
            return BookingResult(
                success=True, external_booking_id=external_booking_id,
                confirmation_code=None, error_message='', error_code=None, raw=data,
            )
        except httpx.HTTPStatusError as exc:
            logger.info(
                'Bookhara auto_cancel muvaffaqiyatsiz, manual-refund sinaladi: %s', exc,
            )

        try:
            data = self.request_manual_refund(external_booking_id)
            return BookingResult(
                success=True, external_booking_id=external_booking_id,
                confirmation_code=None, error_message='', error_code=None, raw=data,
            )
        except httpx.HTTPStatusError as exc:
            return BookingResult(
                success=False, external_booking_id=external_booking_id,
                confirmation_code=None,
                error_message=self._extract_error_message(exc),
                error_code=self._extract_error_code(exc),
                raw=self._safe_json(exc),
            )

    # -------------------------------------------------------------------
    # 18. Loglash yordamchisi
    # -------------------------------------------------------------------

    def _log(
        self,
        method: str,
        payload: dict,
        response: Any,
        status_code: int,
        is_success: bool,
        elapsed_ms: int,
        booking_id: str | None = None,
    ) -> None:
        """ExternalProviderLog yozuvini yaratadi. Hech qachon exception
        tashlamaydi — loglash xatosi asosiy biznes-oqimni buzmasligi kerak.
        """
        try:
            ExternalProviderLog.objects.create(
                provider=self.PROVIDER_NAME,
                method=method,
                request_payload=payload,
                response_payload=(
                    response if isinstance(response, dict) else {'raw': str(response)}
                ),
                status_code=status_code,
                is_success=is_success,
                response_time_ms=elapsed_ms,
                error_message='' if is_success else str(response),
                booking_id=booking_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning('ExternalProviderLog yozib bolmadi: %s', exc)

    # -------------------------------------------------------------------
    # 19. Parvoz jadvali
    # -------------------------------------------------------------------

    def get_schedule(
        self,
        departure_from: str,
        departure_to: str,
        airport_from: str | None = None,
        airport_to: str | None = None,
        airlines: list[str] | None = None,
    ) -> list[dict]:
        """GET /api/v1/services/schedule"""
        params: dict = {
            'departure_from': departure_from,
            'departure_to': departure_to,
            'airport_from': airport_from,
            'airport_to': airport_to,
            'airlines': airlines,
        }
        params = {k: v for k, v in params.items() if v is not None}
        data = self._call(
            'get_schedule',
            lambda: self.client.get('/api/v1/services/schedule', params=params),
        )
        return data if isinstance(data, list) else data.get('data', [])

    # -------------------------------------------------------------------
    # Ichki yordamchi metodlar
    # -------------------------------------------------------------------

    def _call(self, method: str, func, booking_id: str | None = None) -> dict:
        """Umumiy chaqiruv wrapper'i: vaqtni olchaydi va muvaffaqiyatli
        natijani avtomatik loglaydi. Xato yuz bersa, uni yuqoriga
        (chaqiruvchi metodga) uzatadi — u yerda kerakli maxsus
        xatolik klassiga ogiriladi.
        """
        start = time.monotonic()
        try:
            data = func()
        except httpx.HTTPStatusError as exc:
            self._log(
                method, {}, self._safe_json(exc),
                exc.response.status_code, False, self._elapsed_ms(start),
                booking_id=booking_id,
            )
            raise
        self._log(method, {}, data, 200, True, self._elapsed_ms(start), booking_id=booking_id)
        return data

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        return int((time.monotonic() - start) * 1000)

    @staticmethod
    def _safe_json(exc: httpx.HTTPStatusError) -> dict:
        try:
            return exc.response.json()
        except ValueError:
            return {'raw_text': exc.response.text}

    @classmethod
    def _extract_error_code(cls, exc: httpx.HTTPStatusError) -> str:
        """Xatolik kodini javob tanasidan (error_code / code) yoki, agar
        topilmasa, HTTP status kodidan chiqarib oladi.
        """
        body = cls._safe_json(exc)
        code = body.get('error_code') or body.get('code')
        if code is not None:
            return str(code)
        return str(exc.response.status_code)

    @classmethod
    def _extract_error_message(cls, exc: httpx.HTTPStatusError) -> str:
        body = cls._safe_json(exc)
        return (
            body.get('message')
            or body.get('error_message')
            or body.get('error')
            or f'Bookhara xatoligi: HTTP {exc.response.status_code}'
        )

    @staticmethod
    def _parse_offer(raw: dict) -> FlightOffer:
        """Bookhara javobidagi bitta offer obyektini FlightOffer'ga ogiradi.

        Struktura: offer -> directions[0] -> segments[0].
        Faqat birinchi yonalishning birinchi segmenti asosiy FlightOffer
        maydonlarini toldirish uchun ishlatiladi; toliq struktura
        `raw` maydonida saqlanib qoladi.
        """
        directions = raw.get('directions') or []
        first_direction = directions[0] if directions else {}
        segments = first_direction.get('segments') or []
        first_segment = segments[0] if segments else {}

        baggage = first_segment.get('baggage')
        if isinstance(baggage, dict):
            baggage_included = bool(baggage.get('included', False))
        else:
            baggage_included = bool(baggage)

        return FlightOffer(
            offer_id=raw.get('id'),
            airline=first_segment.get('airline', ''),
            flight_number=first_segment.get('flight_number', ''),
            origin=first_segment.get('origin', ''),
            destination=first_segment.get('destination', ''),
            departure_at=first_segment.get('departure_at', ''),
            arrival_at=first_segment.get('arrival_at', ''),
            price=Decimal(str(raw.get('price', 0))),
            currency=raw.get('currency', 'UZS'),
            seat_class=raw.get('cabin_class', ''),
            available_seats=int(raw.get('available_seats', 0)),
            baggage_included=baggage_included,
            raw=raw,
        )
