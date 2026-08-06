"""
Booking app — Polymorphic bron modeli.
Parvoz, poyezd, restoran, tadbir — barchasi BaseBooking'dan meros oladi.
TZ 3.3 bo'limiga mos.
"""

from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class ServiceType(models.TextChoices):
    FLIGHT = 'flight', 'Parvoz'
    TRAIN = 'train', 'Poyezd'
    RESTAURANT = 'restaurant', 'Restoran'
    EVENT = 'event', 'Tadbir'
    HOTEL = 'hotel', 'Mehmonxona'  # kelajak uchun tayyor


class BookingStatus(models.TextChoices):
    PENDING = 'pending', 'Kutilmoqda'
    CONFIRMED = 'confirmed', 'Tasdiqlangan'
    CANCELLED = 'cancelled', 'Bekor qilingan'
    COMPLETED = 'completed', 'Bajarilgan'
    REFUNDED = 'refunded', 'Qaytarilgan'
    FAILED = 'failed', 'Amalga oshmadi'


class Booking(BaseModel):
    """
    Yagona Booking bazaviy modeli.
    Barcha xizmat turlari shu modelga bo'ysunadi —
    yagona bron tarixi, yagona to'lov oqimi, yagona AI interfeysi.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    service_type = models.CharField(max_length=20, choices=ServiceType.choices)
    status = models.CharField(
        max_length=20, choices=BookingStatus.choices, default=BookingStatus.PENDING
    )

    # Asosiy ma'lumotlar
    title = models.CharField(max_length=255, help_text='Bron nomi (masalan: MSQ→DXB, Nobu restoran)')
    description = models.TextField(blank=True)
    booking_date = models.DateTimeField(null=True, blank=True, help_text='Bron amalga oshiriladigan vaqt')

    # Narx
    base_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    final_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='UZS')

    # Tashqi bron ID (aviakassa yoki boshqa tizimdan)
    external_booking_id = models.CharField(max_length=128, blank=True, null=True)
    external_provider = models.CharField(max_length=64, blank=True, null=True)

    # AI orqali yaratilganmi
    created_by_ai = models.BooleanField(default=False)
    ai_action_log = models.ForeignKey(
        'ai_assistant.AIActionLog',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bookings'
    )

    # Bekor qilish
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Bron'
        verbose_name_plural = 'Bronlar'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['service_type', 'status']),
        ]

    def __str__(self):
        return f'{self.user} | {self.service_type} | {self.title} [{self.status}]'

    def calculate_final_price(self):
        """Chegirma hisoblab, final narxni qaytaradi."""
        self.final_price = max(self.base_price - self.discount_amount, 0)
        return self.final_price


class FlightBooking(BaseModel):
    """Parvoz broni — qo'shimcha ma'lumotlar."""
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='flight_detail')
    origin = models.CharField(max_length=3, help_text='IATA kodi, masalan TAS')
    destination = models.CharField(max_length=3, help_text='IATA kodi, masalan DXB')
    departure_at = models.DateTimeField()
    arrival_at = models.DateTimeField(null=True, blank=True)
    airline = models.CharField(max_length=64, blank=True)
    flight_number = models.CharField(max_length=20, blank=True)
    seat_class = models.CharField(
        max_length=20,
        choices=[('economy', 'Economy'), ('business', 'Business'), ('first', 'First')],
        default='economy'
    )
    passenger_count = models.PositiveSmallIntegerField(default=1)
    baggage_included = models.BooleanField(default=False)
    pnr_code = models.CharField(max_length=20, blank=True, null=True, help_text='Locator / PNR')

    # Bookhara (va boshqa provayderlar) uchun xom holat va javob
    provider_status   = models.CharField(
        max_length=30, blank=True,
        help_text='Provayderdan kelgan xom status (masalan: ticketed, awaitpayment)',
    )
    provider_response = models.JSONField(
        null=True, blank=True,
        help_text='Provayderdan kelgan to\'liq xom JSON javob',
    )

    class Meta:
        verbose_name = 'Parvoz broni'
        verbose_name_plural = 'Parvoz bronlari'

    def __str__(self):
        return f'{self.origin}→{self.destination} {self.departure_at}'


class TrainBooking(BaseModel):
    """Poyezd broni — qo'shimcha ma'lumotlar."""
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='train_detail')
    origin_station = models.CharField(max_length=100)
    destination_station = models.CharField(max_length=100)
    departure_at = models.DateTimeField()
    arrival_at = models.DateTimeField(null=True, blank=True)
    train_number = models.CharField(max_length=20, blank=True)
    wagon_type = models.CharField(
        max_length=20,
        choices=[('platzkart', 'Platzkart'), ('coupe', 'Kupe'), ('sv', 'SV'), ('sitting', 'O\'tirish')],
        default='coupe'
    )
    seat_number = models.CharField(max_length=10, blank=True, null=True)
    passenger_count = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = 'Poyezd broni'
        verbose_name_plural = 'Poyezd bronlari'


class RestaurantBooking(BaseModel):
    """Restoran stoli broni."""
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='restaurant_detail')
    branch = models.ForeignKey(
        'crm.Branch', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='restaurant_bookings'
    )
    reservation_at = models.DateTimeField()
    guest_count = models.PositiveSmallIntegerField(default=2)
    special_requests = models.TextField(blank=True)
    table_number = models.CharField(max_length=20, blank=True, null=True)
    confirmed_by_staff = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Restoran broni'
        verbose_name_plural = 'Restoran bronlari'


class EventBooking(BaseModel):
    """Tadbir chiptalari broni."""
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='event_detail')
    event = models.ForeignKey(
        'events.Event', on_delete=models.CASCADE,
        related_name='bookings'
    )
    ticket_count = models.PositiveSmallIntegerField(default=1)
    ticket_type = models.CharField(max_length=50, blank=True)
    seat_info = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = 'Tadbir broni'
        verbose_name_plural = 'Tadbir bronlari'
