"""
QR Codes app — QR kod chegirma va analitika tizimi.

Modellar:
    QRCode           — QR kod konfiguratsiyasi
    QRCodeRedemption — har bir skanerlash va qo'llash qayd etiladi
    QRAnalyticsSummary — kunlik denormalized statistika (Celery)

Ishlash prinsipi:
    1. Tashkilot CRM da QR kod yaratadi (chegirma %, sum, bonus)
    2. QR PNG generatsiya qilinadi (qrcode library)
    3. Foydalanuvchi sayt/bot orqali skanerlaydi → GET /api/qr/<code>/
    4. Chegirmani qo'llash → POST /api/qr/<code>/redeem/
    5. Barcha qo'llashlar QRCodeRedemption da saqlanadi (analytics uchun)
"""

import secrets
import string
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator

from apps.core.models import BaseModel


# ─── QRCode ───────────────────────────────────────────────────────────────────

class QRCodeType(models.TextChoices):
    DISCOUNT_PERCENT = 'discount_percent', 'Foiz chegirma (%)'
    DISCOUNT_FIXED   = 'discount_fixed',   'Belgilangan chegirma (so\'m)'
    BONUS_POINTS     = 'bonus_points',     'Bonus ball'
    FREE_SERVICE     = 'free_service',     'Bepul xizmat'


class RedemptionStatus(models.TextChoices):
    SCANNED  = 'scanned',  'Skanerlandi'
    APPLIED  = 'applied',  'Qo\'llandi'
    REJECTED = 'rejected', 'Rad etildi'
    EXPIRED  = 'expired',  'Muddati o\'tgan'


def _generate_qr_code():
    """URL-safe, o'qilishi qulay 12 belgili kod."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(12))


class QRCode(BaseModel):
    """
    QR kod konfiguratsiyasi.
    Bitta kod ko'p marta skanerlansa ham, cheklovlar kuzatiladi.
    """
    # ── Tashkilot ─────────────────────────────────────────────────────────────
    organization = models.ForeignKey(
        'crm.Organization',
        on_delete=models.CASCADE,
        related_name='qr_codes',
        null=True, blank=True,
        help_text="Bo'sh bo'lsa — IMTIAZ platforma darajasidagi umumiy bonus (tashkilotga bog'lanmagan)",
    )
    branch = models.ForeignKey(
        'crm.Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qr_codes',
    )

    # ── E'lon shabloni va shaxsiylashtirish ──────────────────────────────────
    source_template = models.ForeignKey(
        'bonuses.BonusCategory',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qr_codes',
        help_text="Qaysi umumiy bonus e'lonidan (shablon) yaratilgani — ixtiyoriy",
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='personal_qr_codes',
        help_text="Bo'sh bo'lsa — OMMAVIY kampaniya (hamma skanerlay oladi). "
                  "To'ldirilgan bo'lsa — faqat shu foydalanuvchiga tegishli SHAXSIY vaucher.",
    )
    service_type = models.CharField(
        max_length=20,
        choices=[
            ('flight', 'Parvoz'), ('restaurant', 'Restoran'), ('event', 'Tadbir'),
            ('hotel', "Mehmonxona"), ('tour', 'Tur sayohat'), ('all', 'Barcha xizmatlar'),
        ],
        default='all',
        db_index=True,
        help_text="Qaysi xizmat turiga tegishli — mobil ilovada bo'lim bo'yicha filtrlash uchun",
    )

    # ── Identifikator ─────────────────────────────────────────────────────────
    code     = models.CharField(
        max_length=20, unique=True, default=_generate_qr_code,
        help_text='URL-safe noyob kod'
    )
    qr_image = models.ImageField(
        upload_to='qr_codes/images/', null=True, blank=True,
        help_text='Avtomatik generatsiya qilingan PNG'
    )

    # ── Chegirma konfiguratsiyasi ──────────────────────────────────────────────
    title           = models.CharField(max_length=255)
    description     = models.TextField(blank=True)
    qr_type         = models.CharField(max_length=25, choices=QRCodeType.choices)
    discount_value  = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='15.00 (foiz uchun 15%), 50000.00 (so\'m uchun)'
    )
    max_discount_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Foiz chegirma uchun maksimal sum chegarasi'
    )
    minimum_order_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text='Minimal buyurtma miqdori'
    )

    # ── Qo'llanish doirasi ────────────────────────────────────────────────────
    applicable_services = models.JSONField(
        default=list,
        help_text='["tour", "restaurant", "all"] — qaysi xizmatga tegishli'
    )

    # ── Cheklovlar ────────────────────────────────────────────────────────────
    max_total_uses    = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Jami necha marta qo\'llanishi mumkin (null = cheksiz)'
    )
    max_uses_per_user = models.PositiveSmallIntegerField(
        default=1,
        help_text='Bir foydalanuvchi necha marta ishlatishi mumkin'
    )
    total_used_count  = models.PositiveIntegerField(default=0)

    # ── Muddat ────────────────────────────────────────────────────────────────
    valid_from  = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)

    # ── Holat ─────────────────────────────────────────────────────────────────
    is_active  = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_qr_codes',
    )

    class Meta:
        verbose_name        = 'QR Kod'
        verbose_name_plural = 'QR Kodlar'
        ordering            = ['-created_at']
        indexes             = [
            models.Index(fields=['code']),
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['assigned_user', 'is_active']),
            models.Index(fields=['service_type', 'is_active']),
        ]

    def __str__(self):
        return f'{self.title} [{self.code}] — {self.get_qr_type_display()}'

    @property
    def is_valid(self) -> bool:
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_total_uses is not None and self.total_used_count >= self.max_total_uses:
            return False
        return True

    def calculate_discount(self, order_amount: float) -> float:
        """Buyurtma summasiga chegirmani hisoblaydi."""
        if self.qr_type == QRCodeType.DISCOUNT_PERCENT:
            discount = (float(order_amount) * float(self.discount_value)) / 100
            if self.max_discount_amount:
                discount = min(discount, float(self.max_discount_amount))
        elif self.qr_type == QRCodeType.DISCOUNT_FIXED:
            discount = min(float(self.discount_value), float(order_amount))
        elif self.qr_type == QRCodeType.BONUS_POINTS:
            # Bonus ball — chegirma sifatida qo'llanmaydi (ball user balansiga qo'shiladi)
            discount = 0.0
        elif self.qr_type == QRCodeType.FREE_SERVICE:
            discount = float(order_amount)
        else:
            discount = 0.0
        return round(discount, 2)


# ─── QRCodeRedemption ─────────────────────────────────────────────────────────

class QRCodeRedemption(BaseModel):
    """
    Har bir skanerlash va chegirmani qo'llash qayd etiladi.
    Analytics uchun asosiy manba.
    Ro'yxatdan o'tmagan foydalanuvchi ham skanerlashi mumkin (user=null).
    """
    qr_code      = models.ForeignKey(
        QRCode, on_delete=models.CASCADE, related_name='redemptions'
    )
    user         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qr_redemptions',
    )
    # Ro'yxatdan o'tmagan mijoz (CRM skaner)
    customer_name  = models.CharField(max_length=255, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    # Qayerda qo'llandi
    booking      = models.ForeignKey(
        'booking.Booking',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qr_redemptions',
    )
    service_type = models.CharField(
        max_length=20, blank=True,
        help_text='tour, restaurant, general'
    )

    # Moliyaviy ma'lumotlar
    order_amount    = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    discount_applied = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    final_amount    = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    # Texnik
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.CharField(max_length=500, blank=True)
    scanned_at  = models.DateTimeField(auto_now_add=True)

    # Holat
    status           = models.CharField(
        max_length=10, choices=RedemptionStatus.choices, default=RedemptionStatus.SCANNED
    )
    rejection_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name        = 'QR Qo\'llash'
        verbose_name_plural = 'QR Qo\'llashlar'
        ordering            = ['-scanned_at']
        indexes             = [
            models.Index(fields=['qr_code', 'user', 'scanned_at']),
            models.Index(fields=['status', 'scanned_at']),
        ]

    def __str__(self):
        return f'{self.qr_code.code} | {self.user or "anonim"} | {self.status}'


# ─── QRAnalyticsSummary ───────────────────────────────────────────────────────

class QRAnalyticsSummary(BaseModel):
    """
    Kunlik QR kod analitikasi (denormalized).
    Celery task kunlik 01:00 da hisoblaydi.
    Rahbar dashboard'ida grafik uchun ishlatiladi.
    """
    qr_code         = models.ForeignKey(
        QRCode, on_delete=models.CASCADE, related_name='analytics'
    )
    date            = models.DateField()
    scan_count      = models.PositiveIntegerField(default=0)
    apply_count     = models.PositiveIntegerField(default=0)
    reject_count    = models.PositiveIntegerField(default=0)
    total_discount_given    = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_revenue_generated = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    unique_users            = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = 'QR Analitika (kunlik)'
        verbose_name_plural = 'QR Analitikalar (kunlik)'
        unique_together     = ('qr_code', 'date')
        ordering            = ['-date']

    def __str__(self):
        return f'{self.qr_code.code} | {self.date} | {self.scan_count} skan'
