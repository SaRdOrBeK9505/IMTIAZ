"""
Booking app — Polymorphic bron modeli.
Parvoz, poyezd, restoran, tadbir — barchasi BaseBooking'dan meros oladi.
TZ 3.3 bo'limiga mos.
"""

from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from apps.booking.settlement import SettlementStatus, TransactionStep


class ServiceType(models.TextChoices):
    FLIGHT = 'flight', 'Parvoz'
    TRAIN = 'train', 'Poyezd'
    RESTAURANT = 'restaurant', 'Restoran'
    EVENT = 'event', 'Tadbir'
    HOTEL = 'hotel', 'Mehmonxona'  # kelajak uchun tayyor
    TOUR = 'tour', 'Tur sayohat'


class BookingStatus(models.TextChoices):
    PENDING = 'pending', 'Kutilmoqda'
    IN_PROGRESS = 'in_progress', 'Jarayonda'
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
    duration_minutes = models.PositiveSmallIntegerField(
        default=120,
        help_text='Bron davomiyligi (daqiqa)',
    )
    special_requests = models.TextField(blank=True)
    table_number = models.CharField(max_length=20, blank=True, null=True)
    confirmed_by_staff = models.BooleanField(default=False)
    
    # Prompt #1 enhancements
    restaurant_type = models.CharField(
        max_length=20,
        choices=[
            ('casual', 'Casual'),
            ('fine_dining', 'Fine Dining'),
            ('fast_food', 'Fast Food'),
            ('delivery', 'Delivery'),
        ],
        default='casual',
        help_text='Restoran turi'
    )
    preferred_time = models.TimeField(
        null=True, blank=True,
        help_text='Tanlangan vaqt (HH:MM)'
    )
    is_ai_generated = models.BooleanField(
        default=False,
        help_text='AI orqali yaratlganmi'
    )

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


class FlightPayment(BaseModel):
    """
    Bookhara fiscalization_v2 bloki — soliq/fiskal ma'lumotlar.

    pay_booking() muvaffaqiyatli bo'lgach, javobdagi fiscalization_v2
    dict'i shu modelga saqlanadi. AlifPay OFD chek URL ham shu yerda.

    MUHIM: amount maydonlari doim so'mda saqlanadi.
    AlifPay'ga yuborishda tiyinga o'tkazish (x100) faqat
    AlifPayProvider.create_payment() ichida amalga oshiriladi.
    """
    flight_booking     = models.ForeignKey(
        FlightBooking, on_delete=models.CASCADE, related_name='payments',
    )
    receipt_type       = models.IntegerField(default=0)
    ikpu_provider_1    = models.CharField(max_length=32, blank=True)
    package_code_prov1 = models.CharField(max_length=32, blank=True)
    id_provider_1      = models.CharField(max_length=32, blank=True)
    amount             = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    nds_provider_1     = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    ikpu_bookhara      = models.CharField(max_length=32, blank=True)
    package_code_bkh   = models.CharField(max_length=32, blank=True)
    service_fee_bkh    = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    nds_bookhara       = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    profit             = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount           = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount       = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # AlifPay OFD chek havolasi — webhook kelganda saqlanadi
    receipt_url        = models.URLField(blank=True)

    class Meta:
        verbose_name        = "Parvoz to'lovi (fiskal)"
        verbose_name_plural = "Parvoz to'lovlari (fiskal)"
        ordering = ['-created_at']

    def __str__(self):
        return f'FlightPayment #{self.id} | {self.total_amount} UZS'


class TourBooking(BaseModel):
    """
    Tur sayohat broni — Booking modelining kengaytmasi.
    Operator tasdiqlagach TourVoucher yaratiladi.
    """

    class HotelPreference(models.TextChoices):
        STANDARD = 'standard', 'Standart'
        DELUXE   = 'deluxe',   'Deluxe'
        SUITE    = 'suite',    'Suite'
        ANY      = 'any',      'Farq qilmaydi'

    booking = models.OneToOneField(
        Booking, on_delete=models.CASCADE, related_name='tour_detail'
    )
    package = models.ForeignKey(
        'tours.TourPackage',
        on_delete=models.PROTECT,
        related_name='tour_bookings',
    )
    availability = models.ForeignKey(
        'tours.TourAvailability',
        on_delete=models.PROTECT,
        related_name='tour_bookings',
    )

    # ── Sayohatchilar ────────────────────────────────────────────────
    tourist_count    = models.PositiveSmallIntegerField(default=1)
    tourists_info    = models.JSONField(
        default=list,
        help_text='[{"name": "Ism Familiya", "passport": "AC123456", '
                  '"dob": "1990-01-01", "nationality": "UZ"}]'
    )
    special_requests = models.TextField(blank=True)
    hotel_preference = models.CharField(
        max_length=20,
        choices=HotelPreference.choices,
        default=HotelPreference.ANY,
    )

    # ── CRM operator tomonidan to'ldiriladi ─────────────────────────
    confirmed_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='confirmed_tour_bookings',
    )
    confirmed_at     = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    operator_notes   = models.TextField(blank=True)

    # ── AI tahlil (CRM arizalar sahifasi) ───────────────────────────
    ai_analysis      = models.TextField(
        blank=True,
        help_text='AI tomonidan shakllangan mijoz/tur tahlili matni',
    )
    ai_reprocessed   = models.BooleanField(
        default=False,
        help_text='AI qayta ishlagan ariza belgisi',
    )

    # ── Voaucher ─────────────────────────────────────────────────────
    voucher_generated    = models.BooleanField(default=False)
    voucher_generated_at = models.DateTimeField(null=True, blank=True)
    voucher_generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='generated_tour_vouchers',
    )

    class Meta:
        verbose_name        = 'Tur broni'
        verbose_name_plural = 'Tur bronlari'
        indexes = [
            models.Index(fields=['package', 'availability']),
            models.Index(fields=['voucher_generated']),
        ]

    def __str__(self):
        return f'TurBron: {self.booking.user} → {self.package} [{self.booking.status}]'


class BookingSettlement(BaseModel):
    """
    Parvoz bronlari uchun Bookhara settlement saga holati.

    Har bir flight booking uchun bitta yozuv (OneToOne).
    Idempotency: pay_booking so'rovlarida idempotency_key ishlatiladi.
    """
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='settlement',
    )
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settlements',
    )
    status = models.CharField(
        max_length=32,
        choices=SettlementStatus.CHOICES,
        default=SettlementStatus.PENDING,
        db_index=True,
    )
    idempotency_key = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text='Bookhara pay_booking uchun noyob kalit',
    )
    locked_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Pre-flight da qulflangan Bookhara narxi (UZS)',
    )
    bookhara_deposit_at_preflight = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Pre-flight vaqtidagi depozit balansi',
    )
    last_error_code = models.CharField(max_length=64, blank=True)
    last_error_message = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    refund_attempts = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Bron settlement (saga)'
        verbose_name_plural = 'Bron settlementlar (saga)'
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self) -> str:
        return f'Settlement {self.booking_id} [{self.status}]'

    def transition_to(self, new_status: str) -> None:
        from apps.booking.settlement import SETTLEMENT_TRANSITIONS

        allowed = SETTLEMENT_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Settlement '{self.status}' dan '{new_status}' ga o'tish "
                f"ruxsat etilmagan. Ruxsat: {allowed}"
            )
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])


class BookingTransactionLog(BaseModel):
    """Settlement saga har bir bosqichining audit jurnali."""

    settlement = models.ForeignKey(
        BookingSettlement,
        on_delete=models.CASCADE,
        related_name='transaction_logs',
    )
    step = models.CharField(max_length=64, choices=TransactionStep.CHOICES, db_index=True)
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32, blank=True)
    success = models.BooleanField(default=True)
    message = models.TextField(blank=True)
    provider_response = models.JSONField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True)

    class Meta:
        verbose_name = 'Bron transaction log'
        verbose_name_plural = 'Bron transaction loglari'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['settlement', 'step']),
        ]

    def __str__(self) -> str:
        mark = 'OK' if self.success else 'FAIL'
        return f'{self.settlement_id} | {self.step} [{mark}]'

