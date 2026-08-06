"""
Bookhara GDS adapter — FlightProviderAdapter implementatsiyasi.

Bookhara statuslari → IMTIAZ BookingStatus mapping:
    booked, awaitpayment              → pending
    paid                              → pending  (to'lov qilingan, chipta hali yo'q)
    ticketed, partiallyticketed       → confirmed
    refundauthorized, partiallyrefunded, refunded → refunded
    cancelled                         → cancelled

FlightOffer'ga qo'shimcha kerak bo'lmagan maydonlar:
    - Bookhara directions[].segments[] ning barcha maydonlari FlightOffer'ga sig'adi
    - Faqat raw=<to'liq javob> orqali yo'qolmas ma'lumot saqlanadi
    - provider_status va provider_response FlightBooking modelida saqlanadi

Xato kodlari:
    5231, 5232 — duplicate booking
    404, 410   — offer expired/gone
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal

from django.conf import settings

from .base import FlightProviderAdapter, FlightOffer, BookingResult
from .bookhara_client import BookharaAPIClient
from apps.integrations.models import ExternalProviderLog

logger = logging.getLogger(__name__)

# Bookhara status → IMTIAZ BookingStatus
BOOKHARA_STATUS_MAP: dict[str, str] = {
    'booked':              'pending',
    'awaitpayment':        'pending',
    'paid':                'pending',
    'ticketed':            'confirmed',
    'partiallyticketed':   'confirmed',
    'refundauthorized':    'refunded',
    'partiallyrefunded':   'refunded',
    'refunded':            'refunded',
    'cancelled':           'cancelled',
}

# Duplicate / expired xato kodlari
DUPLICATE_CODES = {'5231', '5232'}
EXPIRED_CODES   = {'404', '410', '5100'}


class BookharaAdapter(FlightProviderAdapter):
    """
    Bookhara GDS REST API orqali parvoz qidirish va bron qilish.

    Barcha javoblar FlightOffer / BookingResult dataclass'iga o'giriladi —
    qolgan kod Bookhara'ni bilmaydi.
    Har bir API chaqiruvi ExternalProviderLog'ga yoziladi.
    """

    def __init__(self):
        self._client = BookharaAPIClient()

    # ── search ────────────────────────────────────────────────────────────────

    def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: int = 1,
        seat_class: str = 'economy',
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        """GET /api/v1/offers — parvoz taklif qidirish."""
        payload = {
            'origin':           origin,
            'destination':      destination,
            'departure_date':   departure_date,
            'passengers':       passengers,
            'cabin_class':      self._map_cabin(seat_class),
        }
        if return_date:
            payload['return_date'] = return_date

        start = time.monotonic()
        try:
            data     = self._client.get('/api/v1/offers', params=payload)
            elapsed  = int((time.monotonic() - start) * 1000)
            self._log('search', payload, data, 200, True, elapsed)
            return [
                self._parse_offer(item)
                for item in (data.get('offers') or data.get('data') or [])
            ]
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            self._log('search', payload, {'error': str(e)}, 0, False, elapsed)
            raise

    # ── get_price ─────────────────────────────────────────────────────────────

    def get_price(self, offer_id: str) -> Decimal:
        """GET /api/v1/offers/{id} — joriy narxni qaytaradi."""
        start = time.monotonic()
        try:
            data    = self._client.get(f'/api/v1/offers/{offer_id}')
            elapsed = int((time.monotonic() - start) * 1000)
            self._log('get_price', {'offer_id': offer_id}, data, 200, True, elapsed)
            price = (
                data.get('price')
                or data.get('total_price')
                or data.get('data', {}).get('price', 0)
            )
            return Decimal(str(price))
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            self._log('get_price', {'offer_id': offer_id}, {'error': str(e)}, 0, False, elapsed)
            raise

    # ── create_booking ────────────────────────────────────────────────────────

    def create_booking(
        self,
        offer_id: str,
        passengers: int,
        **kwargs,
    ) -> BookingResult:
        """POST /api/v1/offers/{id}/booking — bron yaratish."""
        body = {
            'offer_id':   offer_id,
            'passengers': passengers,
            **{k: v for k, v in kwargs.items() if v is not None},
        }
        start = time.monotonic()
        try:
            data    = self._client.post(f'/api/v1/offers/{offer_id}/booking', body=body)
            elapsed = int((time.monotonic() - start) * 1000)
            self._log('create_booking', body, data, 200, True, elapsed)

            booking_data = data.get('booking') or data.get('data') or data
            return BookingResult(
                success=True,
                external_booking_id=str(
                    booking_data.get('id')
                    or booking_data.get('booking_id')
                    or ''
                ),
                confirmation_code=booking_data.get('pnr') or booking_data.get('locator'),
                raw=data,
            )

        except Exception as e:
            elapsed   = int((time.monotonic() - start) * 1000)
            error_str = str(e)
            # HTTP xato javobidan error_code ajratib olish
            error_code = self._extract_error_code(e)
            self._log('create_booking', body, {'error': error_str}, 0, False, elapsed)

            if error_code in DUPLICATE_CODES:
                msg = f'Duplicate bron (kod {error_code}): bu taklif allaqachon bronlangan.'
            elif error_code in EXPIRED_CODES:
                msg = f'Taklif eskirgan (kod {error_code}): qaytadan qidiring.'
            else:
                msg = f'Bron yaratishda xato: {error_str}'

            logger.error('Bookhara create_booking xato: code=%s, msg=%s', error_code, msg)
            return BookingResult(
                success=False,
                error_message=msg,
                error_code=error_code,
            )

    # ── cancel_booking ────────────────────────────────────────────────────────

    def cancel_booking(self, external_booking_id: str) -> BookingResult:
        """
        DELETE /api/v1/bookings/{id} — bronni bekor qilish.
        Bookhara'da void/auto-cancel/manual-refund farqi bor —
        hozircha yagona endpoint chaqiriladi, kelajakda status'ga qarab ajratiladi.
        """
        start = time.monotonic()
        try:
            data    = self._client.delete(f'/api/v1/bookings/{external_booking_id}')
            elapsed = int((time.monotonic() - start) * 1000)
            self._log('cancel_booking', {'booking_id': external_booking_id}, data, 200, True, elapsed)
            return BookingResult(success=True, external_booking_id=external_booking_id, raw=data)

        except Exception as e:
            elapsed    = int((time.monotonic() - start) * 1000)
            error_code = self._extract_error_code(e)
            self._log(
                'cancel_booking',
                {'booking_id': external_booking_id},
                {'error': str(e)}, 0, False, elapsed,
            )
            return BookingResult(
                success=False,
                error_message=str(e),
                error_code=error_code,
            )

    # ── _parse_offer ──────────────────────────────────────────────────────────

    def _parse_offer(self, raw: dict) -> FlightOffer:
        """
        Bookhara directions[].segments[] → FlightOffer.

        Bookhara javob strukturasi:
            {
                "id": "offer-uuid",
                "price": 1500000,
                "currency": "UZS",
                "cabin_class": "economy",
                "available_seats": 9,
                "directions": [
                    {
                        "segments": [
                            {
                                "origin": "TAS", "destination": "DXB",
                                "departure_at": "2026-08-10T08:00:00",
                                "arrival_at":   "2026-08-10T10:30:00",
                                "airline":      "HY",
                                "flight_number":"HY401",
                                "baggage":      {"included": true}
                            }
                        ]
                    }
                ]
            }

        Birinchi direction'ning birinchi segmenti asosiy ma'lumot sifatida ishlatiladi.
        Ko'p segment bo'lsa (transit) — raw ichida to'liq saqlanadi.
        """
        directions = raw.get('directions') or []
        segment    = {}
        if directions:
            segs = directions[0].get('segments') or []
            if segs:
                segment = segs[0]

        # Baggage
        baggage_info = segment.get('baggage') or {}
        baggage_included = (
            baggage_info.get('included', False)
            if isinstance(baggage_info, dict)
            else bool(baggage_info)
        )

        return FlightOffer(
            offer_id        = str(raw.get('id', '')),
            airline         = segment.get('airline', ''),
            flight_number   = segment.get('flight_number', ''),
            origin          = segment.get('origin', ''),
            destination     = segment.get('destination', ''),
            departure_at    = segment.get('departure_at', ''),
            arrival_at      = segment.get('arrival_at', ''),
            price           = Decimal(str(raw.get('price', 0))),
            currency        = raw.get('currency', 'UZS'),
            seat_class      = self._reverse_map_cabin(raw.get('cabin_class', 'economy')),
            available_seats = int(raw.get('available_seats', 0)),
            baggage_included= baggage_included,
            raw             = raw,
        )

    # ── Yordamchilar ──────────────────────────────────────────────────────────

    @staticmethod
    def map_provider_status(provider_status: str) -> str:
        """Bookhara status → IMTIAZ BookingStatus."""
        return BOOKHARA_STATUS_MAP.get(provider_status.lower(), 'pending')

    @staticmethod
    def _map_cabin(seat_class: str) -> str:
        """IMTIAZ seat_class → Bookhara cabin_class."""
        return {
            'economy': 'economy',
            'business': 'business',
            'first': 'first',
        }.get(seat_class, 'economy')

    @staticmethod
    def _reverse_map_cabin(cabin: str) -> str:
        """Bookhara cabin_class → IMTIAZ seat_class."""
        return {
            'economy': 'economy',
            'business': 'business',
            'first': 'first',
        }.get(cabin, 'economy')

    @staticmethod
    def _extract_error_code(exc: Exception) -> str | None:
        """HTTP xato javobidan Bookhara error_code ni ajratib oladi."""
        try:
            if hasattr(exc, 'response'):
                body = exc.response.json()
                return str(
                    body.get('error_code')
                    or body.get('code')
                    or exc.response.status_code
                )
        except Exception:
            pass
        return None

    def _log(
        self,
        method: str,
        payload: dict,
        response: dict,
        status_code: int,
        is_success: bool,
        elapsed_ms: int,
        booking_id: str | None = None,
    ) -> None:
        """ExternalProviderLog'ga yozadi."""
        try:
            ExternalProviderLog.objects.create(
                provider         = 'bookhara',
                method           = method,
                request_payload  = payload,
                response_payload = response,
                status_code      = status_code,
                is_success       = is_success,
                response_time_ms = elapsed_ms,
                booking_id       = booking_id,
            )
        except Exception as e:
            logger.warning('ExternalProviderLog yozishda xato: %s', e)
