"""
Tours app — Tur sayohat tizimining asosi.

Modellar:
    TourCategory       — kategoriyalar (adventure, madaniy, ziyorat, ...)
    TourDestination    — sayohat yo'nalishlari
    TourPackage        — asosiy tur paketi (tur kompaniyasi tomonidan)
    TourItineraryDay   — kun-kun dastur
    TourAvailability   — har bir jo'nash sanasi + joy soni
    TourVoucher        — operator tasdiqlagach beriladigan voaucher
    TourReview         — mijoz sharhlari (faqat haqiqiy bronchilar)

Microservice-ready:
    Barcha cross-app FK'lar string ('booking.TourBooking') ko'rinishida.
    Kelajakda bu app alohida service ga ko'chishi mumkin.
"""

from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import BaseModel


# ─── TourCategory ─────────────────────────────────────────────────────────────

class TourCategory(BaseModel):
    """
    Tur kategoriyasi.
    Misol: Deniz ta'tillari, Tog' sayrlar, Ziyorat, Safari, ...
    """
    name        = models.CharField(max_length=100, unique=True)
    slug        = models.SlugField(max_length=120, unique=True, blank=True)
    icon        = models.CharField(max_length=50, blank=True, help_text='Emoji yoki icon nomi')
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='tours/categories/', null=True, blank=True)
    is_active   = models.BooleanField(default=True)
    sort_order  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = 'Tur kategoriyasi'
        verbose_name_plural = 'Tur kategoriyalari'
        ordering            = ['sort_order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ─── TourDestination ──────────────────────────────────────────────────────────

class TourDestination(BaseModel):
    """
    Sayohat yo'nalishi (davlat yoki shahar darajasida).
    Tur kompaniyasi CRM orqali o'z yo'nalishlarini yaratadi.
    """
    organization = models.ForeignKey(
        'crm.Organization',
        on_delete=models.CASCADE,
        related_name='tour_destinations',
        null=True,
        blank=True,
        help_text='Tur kompaniyasi — CRM orqali yaratilgan yo\'nalishlar',
    )
    name        = models.CharField(max_length=150)
    slug        = models.SlugField(max_length=170, blank=True)
    country     = models.CharField(max_length=100)
    country_code = models.CharField(max_length=3, blank=True, help_text='ISO 3166-1 alpha-2')
    city        = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='tours/destinations/', null=True, blank=True)
    climate_info = models.TextField(blank=True, help_text='Iqlim haqida qisqacha')
    visa_info   = models.TextField(blank=True, help_text='Viza talablari')
    best_months = models.JSONField(
        default=list,
        help_text='["June", "July", "August"] — eng yaxshi oylar'
    )
    is_active   = models.BooleanField(default=True)
    is_popular  = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Sayohat yo\'nalishi'
        verbose_name_plural = 'Sayohat yo\'nalishlari'
        ordering            = ['-is_popular', 'name']
        constraints         = [
            models.UniqueConstraint(
                fields=['organization', 'country', 'city'],
                name='unique_org_destination_location',
                condition=models.Q(organization__isnull=False),
            ),
            models.UniqueConstraint(
                fields=['country', 'city'],
                name='unique_global_destination_location',
                condition=models.Q(organization__isnull=True),
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.country})'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = f'{self.country}-{self.city or self.name}'
            if self.organization_id:
                base = f'{self.organization_id}-{base}'
            self.slug = slugify(base)[:170]
        super().save(*args, **kwargs)


class TourDestinationImage(BaseModel):
    """Yo'nalish galereyasi — bir nechta rasm."""
    destination = models.ForeignKey(
        TourDestination,
        on_delete=models.CASCADE,
        related_name='images',
    )
    image = models.ImageField(upload_to='tours/destinations/gallery/')
    caption = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_cover = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Yo\'nalish rasmi'
        verbose_name_plural = 'Yo\'nalish rasmlari'
        ordering            = ['sort_order', 'created_at']

    def __str__(self):
        return f'{self.destination.name} — rasm #{self.sort_order}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_cover:
            TourDestinationImage.objects.filter(
                destination_id=self.destination_id,
            ).exclude(pk=self.pk).update(is_cover=False)
            if self.image and not self.destination.cover_image:
                self.destination.cover_image = self.image
                self.destination.save(update_fields=['cover_image', 'updated_at'])


# ─── TourPackage ──────────────────────────────────────────────────────────────

class DifficultyLevel(models.TextChoices):
    EASY     = 'easy',     'Oson'
    MODERATE = 'moderate', "O'rta"
    HARD     = 'hard',     'Qiyin'
    EXTREME  = 'extreme',  'Ekstremal'


class PricePer(models.TextChoices):
    PERSON = 'person', 'Kishi boshiga'
    GROUP  = 'group',  'Guruh uchun'


class TourPackage(BaseModel):
    """
    Asosiy tur paketi — tur kompaniyasi tomonidan CRM orqali yaratiladi.

    Tuzilma:
        Organization → Branch (ixtiyoriy) → TourPackage
        TourPackage  → TourItineraryDay (kun-kun dastur)
        TourPackage  → TourAvailability (jo'nash sanalari)
        TourPackage  → TourReview       (mijoz sharhlari)
    """
    # ── Tashkilot ─────────────────────────────────────────────────────────────
    organization = models.ForeignKey(
        'crm.Organization',
        on_delete=models.PROTECT,
        related_name='tour_packages',
        limit_choices_to={'org_type': 'tour_company'},
    )
    branch = models.ForeignKey(
        'crm.Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tour_packages',
    )

    # ── Asosiy ma'lumotlar ────────────────────────────────────────────────────
    title       = models.CharField(max_length=255)
    slug        = models.SlugField(max_length=280, unique=True, blank=True)
    category    = models.ForeignKey(
        TourCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='packages'
    )
    destination = models.ForeignKey(
        TourDestination, on_delete=models.PROTECT, related_name='packages'
    )
    short_description = models.CharField(max_length=500, blank=True)
    description       = models.TextField()

    # ── Media ─────────────────────────────────────────────────────────────────
    cover_image = models.ImageField(upload_to='tours/packages/', null=True, blank=True)
    gallery     = models.JSONField(
        default=list,
        help_text='["https://...", "https://..."] — qo\'shimcha rasm URL lari'
    )

    # ── Davomiylik ────────────────────────────────────────────────────────────
    duration_days   = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    duration_nights = models.PositiveSmallIntegerField(default=0)

    # ── Narx ──────────────────────────────────────────────────────────────────
    base_price      = models.DecimalField(max_digits=16, decimal_places=2)
    currency        = models.CharField(max_length=3, default='UZS')
    price_per       = models.CharField(max_length=10, choices=PricePer.choices, default=PricePer.PERSON)
    max_group_size  = models.PositiveSmallIntegerField(default=20)
    min_group_size  = models.PositiveSmallIntegerField(default=1)

    # ── Holat ─────────────────────────────────────────────────────────────────
    is_active   = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text='Bosh sahifada chiqarish')
    is_exclusive = models.BooleanField(default=False, help_text='Faqat a\'zolar uchun')
    exclusive_tier = models.ForeignKey(
        'membership.MembershipTier',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='exclusive_tours',
        help_text='Faqat shu tier va undan yuqori a\'zolar ko\'radi'
    )

    # ── Mazmun ────────────────────────────────────────────────────────────────
    inclusions    = models.JSONField(
        default=list,
        help_text='["Aviachipta", "Transfer", "Mehmonxona (2 kishilik)", "Nonushta"]'
    )
    exclusions    = models.JSONField(
        default=list,
        help_text='["Viza xarajatlari", "Sug\'urta", "Shaxsiy xarajatlar"]'
    )
    requirements  = models.JSONField(
        default=list,
        help_text='["Pasport (6 oy amal qilishi kerak)", "Tibbiy ko\'rik"]'
    )

    # ── Tavsif ────────────────────────────────────────────────────────────────
    difficulty_level = models.CharField(
        max_length=10, choices=DifficultyLevel.choices, default=DifficultyLevel.EASY
    )
    tags = models.JSONField(
        default=list,
        help_text='["beach", "family", "adventure", "budget"]'
    )
    languages_offered = models.JSONField(
        default=list,
        help_text='["uz", "ru", "en"] — gid tillari'
    )

    # ── Denormalized statistika (tez query) ───────────────────────────────────
    total_bookings = models.PositiveIntegerField(default=0)
    avg_rating     = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    review_count   = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = 'Tur paketi'
        verbose_name_plural = 'Tur paketlari'
        ordering            = ['-is_featured', '-created_at']
        indexes             = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['destination', 'is_active']),
            models.Index(fields=['is_featured', 'is_active']),
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self):
        return f'{self.title} ({self.destination.country})'

    def save(self, *args, **kwargs):
        if not self.slug:
            country_name = self.destination.country if self.destination else ''
            base_slug = slugify(f'{self.title}-{country_name}') or 'tour-package'
            slug = base_slug
            counter = 1
            while TourPackage.objects.filter(slug=slug).exclude(id=self.id).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


# ─── TourItineraryDay ─────────────────────────────────────────────────────────

class TourItineraryDay(BaseModel):
    """
    Tur kunlik dasturi.
    Har bir kun o'z faoliyatlari, joylanish va ovqatlanish rejasiga ega.
    """
    package    = models.ForeignKey(
        TourPackage, on_delete=models.CASCADE, related_name='itinerary_days'
    )
    day_number  = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    title       = models.CharField(max_length=255, help_text='1-kun: Toshkent → Dubai')
    description = models.TextField(blank=True)
    activities  = models.JSONField(
        default=list,
        help_text='[{"time": "09:00", "activity": "Burj Khalifa ziyorati", "location": "Dubai"}]'
    )
    accommodation = models.CharField(max_length=255, blank=True, help_text='Mehmonxona nomi')
    meals         = models.JSONField(
        default=dict,
        help_text='{"breakfast": true, "lunch": false, "dinner": true}'
    )
    image = models.ImageField(upload_to='tours/itinerary/', null=True, blank=True)

    class Meta:
        verbose_name        = 'Kun dasturi'
        verbose_name_plural = 'Kun dasturlari'
        ordering            = ['package', 'day_number']
        unique_together     = ('package', 'day_number')

    def __str__(self):
        return f'{self.package.title} — {self.day_number}-kun'


# ─── TourAvailability ─────────────────────────────────────────────────────────

class AvailabilityStatus(models.TextChoices):
    OPEN      = 'open',      'Bron uchun ochiq'
    CLOSED    = 'closed',    'Yopilgan'
    WAITLIST  = 'waitlist',  'Kutish ro\'yxati'
    CANCELLED = 'cancelled', 'Bekor qilingan'


class TourAvailability(BaseModel):
    """
    Jo'nash sanasi va mavjud joylar.
    Bir paket uchun bir necha jo'nash sanasi bo'lishi mumkin.
    Narx override — mavsumiy narx o'zgarishi uchun.
    """
    package        = models.ForeignKey(
        TourPackage, on_delete=models.CASCADE, related_name='availabilities'
    )
    departure_date = models.DateField()
    return_date    = models.DateField(null=True, blank=True)
    total_seats    = models.PositiveSmallIntegerField()
    booked_seats   = models.PositiveSmallIntegerField(default=0)
    price_override = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True,
        help_text='Asosiy narxdan farq qilsa shu maydon to\'ldiriladi'
    )
    status = models.CharField(
        max_length=15, choices=AvailabilityStatus.choices, default=AvailabilityStatus.OPEN
    )
    notes = models.CharField(max_length=500, blank=True)
    guide_name = models.CharField(max_length=150, blank=True, help_text='Guruh gidi ismi')

    class Meta:
        verbose_name        = 'Tur mavjudligi'
        verbose_name_plural = 'Tur mavjudliklari'
        ordering            = ['departure_date']
        indexes             = [
            models.Index(fields=['package', 'departure_date', 'status']),
        ]

    def __str__(self):
        return f'{self.package.title} | {self.departure_date} ({self.available_seats} o\'rin)'

    @property
    def available_seats(self) -> int:
        return max(self.total_seats - self.booked_seats, 0)

    @property
    def effective_price(self):
        """Haqiqiy narx: override bo'lsa shuni, bo'lmasa paket narxini."""
        return self.price_override if self.price_override is not None else self.package.base_price

    @property
    def occupancy_percent(self) -> float:
        if self.total_seats == 0:
            return 100.0
        return round((self.booked_seats / self.total_seats) * 100, 1)


# ─── TourVoucher ──────────────────────────────────────────────────────────────

class VoucherStatus(models.TextChoices):
    ACTIVE  = 'active',  'Faol'
    USED    = 'used',    'Ishlatilgan'
    EXPIRED = 'expired', 'Muddati o\'tgan'
    REVOKED = 'revoked', 'Bekor qilingan'


class TourVoucher(BaseModel):
    """
    Operator tasdiqlagach va voaucher yaratgach, mijoz bu faylni yuklab oladi.
    Muhim: voaucher yaratilganda paket va sayohatchi ma'lumotlari snapshot qilinadi —
    keyinchalik o'zgarsa ham voaucherdagi ma'lumotlar o'zgarmaydi.
    """
    tour_booking   = models.OneToOneField(
        'booking.TourBooking',
        on_delete=models.PROTECT,
        related_name='voucher',
    )
    voucher_number = models.CharField(
        max_length=30, unique=True,
        help_text='TUR-2026-00001 ko\'rinishida avtomatik yaratiladi'
    )
    issued_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='issued_vouchers',
    )
    issued_at      = models.DateTimeField(auto_now_add=True)
    valid_from     = models.DateField()
    valid_until    = models.DateField()
    status         = models.CharField(
        max_length=10, choices=VoucherStatus.choices, default=VoucherStatus.ACTIVE
    )

    # Snapshot — bron paytidagi ma'lumotlar (o'zgarmaslik uchun)
    package_snapshot  = models.JSONField(
        default=dict,
        help_text='Paket ma\'lumotlari snapshot: nomi, yo\'nalishi, narxi, ...'
    )
    tourist_snapshot  = models.JSONField(
        default=list,
        help_text='Sayohatchilar ro\'yxati snapshot'
    )
    booking_snapshot  = models.JSONField(
        default=dict,
        help_text='Bron ma\'lumotlari: narx, sana, mehmonxona afzalligi, ...'
    )

    # PDF fayl (kelajakda)
    pdf_file      = models.FileField(
        upload_to='tours/vouchers/', null=True, blank=True
    )
    download_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = 'Tur voaucheri'
        verbose_name_plural = 'Tur voaucherlari'
        ordering            = ['-issued_at']

    def __str__(self):
        return f'{self.voucher_number} | {self.tour_booking.booking.user}'

    def save(self, *args, **kwargs):
        if not self.voucher_number:
            from django.utils import timezone
            year  = timezone.now().year
            count = TourVoucher.objects.filter(
                issued_at__year=year
            ).count() + 1
            self.voucher_number = f'TUR-{year}-{count:05d}'
        super().save(*args, **kwargs)


# ─── TourReview ───────────────────────────────────────────────────────────────

class TourReview(BaseModel):
    """
    Mijoz sharhlari — faqat haqiqiy bronchilar yozishi mumkin (is_verified).
    Admin publish qiladi (is_published).
    """
    package      = models.ForeignKey(
        TourPackage, on_delete=models.CASCADE, related_name='reviews'
    )
    user         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='tour_reviews',
    )
    tour_booking = models.ForeignKey(
        'booking.TourBooking',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviews',
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title   = models.CharField(max_length=255, blank=True)
    comment = models.TextField()
    photos  = models.JSONField(
        default=list,
        help_text='["https://...", ...] — sharh rasmlar URL lari'
    )
    # Moderatsiya
    is_verified  = models.BooleanField(
        default=False,
        help_text='Haqiqiy bron asosida — avtomatik tekshiriladi'
    )
    is_published = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Tur sharhi'
        verbose_name_plural = 'Tur sharhlari'
        ordering            = ['-created_at']
        unique_together     = ('package', 'user')
        indexes             = [
            models.Index(fields=['package', 'is_published', 'rating']),
        ]

    def __str__(self):
        return f'{self.user} → {self.package.title} [{self.rating}★]'
