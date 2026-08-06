"""
Tashqi provayder uchun abstract Adapter interfeysi.
TZ 3.4: ExternalProviderAdapter pattern.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class FlightOffer:
    """Standartlashtirilgan parvoz taklifi — provayderdan mustaqil."""
    offer_id: str
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_at: str
    arrival_at: str
    price: Decimal
    currency: str
    seat_class: str
    available_seats: int
    baggage_included: bool = False
    raw: dict = field(default_factory=dict)


@dataclass
class TrainOffer:
    """Standartlashtirilgan poyezd taklifi — provayderdan mustaqil."""
    offer_id: str
    train_number: str
    origin: str
    destination: str
    departure_at: str
    arrival_at: str
    price: Decimal
    currency: str
    wagon_type: str
    available_seats: int
    raw: dict = field(default_factory=dict)


@dataclass
class BookingResult:
    success: bool
    external_booking_id: str | None = None
    confirmation_code: str | None = None
    error_message: str = ''
    error_code: str | None = None   # provayder xato kodi (masalan '5231' duplicate)
    raw: dict = field(default_factory=dict)


class FlightProviderAdapter(ABC):
    """Aviakassa provayderlari uchun abstract interfeys."""

    @abstractmethod
    def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: int = 1,
        seat_class: str = 'economy',
        return_date: str | None = None,
    ) -> list[FlightOffer]:
        ...

    @abstractmethod
    def get_price(self, offer_id: str) -> Decimal:
        ...

    @abstractmethod
    def create_booking(self, offer_id: str, passengers: int, **kwargs) -> BookingResult:
        ...

    @abstractmethod
    def cancel_booking(self, external_booking_id: str) -> BookingResult:
        ...


class TrainProviderAdapter(ABC):
    """Temir yo'l provayderlari uchun abstract interfeys."""

    @abstractmethod
    def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: int = 1,
        wagon_type: str = 'coupe',
    ) -> list[TrainOffer]:
        ...

    @abstractmethod
    def create_booking(self, offer_id: str, passengers: int, **kwargs) -> BookingResult:
        ...

    @abstractmethod
    def cancel_booking(self, external_booking_id: str) -> BookingResult:
        ...
