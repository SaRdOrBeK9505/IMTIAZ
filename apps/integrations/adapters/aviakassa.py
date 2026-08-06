"""
Aviakassa API adapteri.
TZ eslatmasi: API hujjatlari hali aniqlanmagan — bu stub implementatsiya.
Haqiqiy API tayyor bo'lganda faqat shu fayl o'zgaradi.
"""

import logging
import time
from decimal import Decimal
from django.conf import settings
import httpx

from .base import FlightProviderAdapter, FlightOffer, BookingResult
from apps.integrations.models import ExternalProviderLog

logger = logging.getLogger(__name__)


class AviakassaAdapter(FlightProviderAdapter):
    """
    Aviakassa tashqi API adapteri.
    Barcha javoblar ichki FlightOffer dataclass formatiga o'giriladi.
    """

    def __init__(self):
        self.api_key = settings.AVIAKASSA_API_KEY
        self.base_url = settings.AVIAKASSA_BASE_URL
        self.client = httpx.Client(
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=30,
        )

    def _log_request(self, method: str, payload: dict, response: dict,
                     status_code: int, is_success: bool, elapsed_ms: int, booking_id=None):
        ExternalProviderLog.objects.create(
            provider='aviakassa',
            method=method,
            request_payload=payload,
            response_payload=response,
            status_code=status_code,
            is_success=is_success,
            response_time_ms=elapsed_ms,
            booking_id=booking_id,
        )

    def search(self, origin: str, destination: str, departure_date: str,
               passengers: int = 1, seat_class: str = 'economy',
               return_date: str | None = None) -> list[FlightOffer]:
        """
        Parvoz qidiradi.
        TODO: Haqiqiy Aviakassa API endpoint'ga ulanish.
        """
        if not self.base_url or not self.api_key:
            logger.warning('Aviakassa API sozlanmagan — mock natija qaytarilmoqda')
            return self._mock_search(origin, destination, departure_date, seat_class)

        payload = {
            'origin': origin,
            'destination': destination,
            'departure_date': departure_date,
            'passengers': passengers,
            'class': seat_class,
        }
        start = time.time()
        try:
            resp = self.client.post(f'{self.base_url}/flights/search', json=payload)
            elapsed = int((time.time() - start) * 1000)
            resp.raise_for_status()
            data = resp.json()
            self._log_request('search', payload, data, resp.status_code, True, elapsed)
            return [self._parse_offer(item) for item in data.get('offers', [])]
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            self._log_request('search', payload, {'error': str(e)}, 0, False, elapsed)
            raise

    def get_price(self, offer_id: str) -> Decimal:
        # TODO: API tayyor bo'lganda implement qilish
        return Decimal('0')

    def create_booking(self, offer_id: str, passengers: int, **kwargs) -> BookingResult:
        # TODO: API tayyor bo'lganda implement qilish
        return BookingResult(
            success=False,
            error_message='Aviakassa API hali sozlanmagan'
        )

    def cancel_booking(self, external_booking_id: str) -> BookingResult:
        # TODO: API tayyor bo'lganda implement qilish
        return BookingResult(
            success=False,
            error_message='Aviakassa API hali sozlanmagan'
        )

    @staticmethod
    def _parse_offer(raw: dict) -> FlightOffer:
        """Tashqi API javobini ichki FlightOffer formatiga o'giradi."""
        return FlightOffer(
            offer_id=raw.get('id', ''),
            airline=raw.get('airline', ''),
            flight_number=raw.get('flight_number', ''),
            origin=raw.get('origin', ''),
            destination=raw.get('destination', ''),
            departure_at=raw.get('departure_at', ''),
            arrival_at=raw.get('arrival_at', ''),
            price=Decimal(str(raw.get('price', 0))),
            currency=raw.get('currency', 'UZS'),
            seat_class=raw.get('class', 'economy'),
            available_seats=raw.get('available_seats', 0),
            raw=raw,
        )

    @staticmethod
    def _mock_search(origin: str, destination: str, departure_date: str,
                     seat_class: str) -> list[FlightOffer]:
        """API tayyor bo'lmagan holatda mock natija."""
        return [
            FlightOffer(
                offer_id='mock-001',
                airline='Uzbekistan Airways',
                flight_number='HY401',
                origin=origin,
                destination=destination,
                departure_at=f'{departure_date}T08:00:00',
                arrival_at=f'{departure_date}T10:30:00',
                price=Decimal('1500000'),
                currency='UZS',
                seat_class=seat_class,
                available_seats=15,
            )
        ]
