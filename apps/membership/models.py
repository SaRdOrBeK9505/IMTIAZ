"""
Membership app — Waitlist va A'zolik tizimi.
IMTIAZ yopiq klub modeli: ariza → tasdiqlash → tier.
TZ 3.8 bo'limiga mos.
"""

from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from apps.users.models import AIAutonomyLevel


class MembershipTier(BaseModel):
    """
    A'zolik darajalari (Standard, Silver, Gold, Platinum ...).
    Har bir darajada AI avtonomiya limiti, chegirma va eksklyuziv kirish bor.
    """
    name        = models.CharField(max_length=50, unique=True)
    slug        = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    monthly_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    max_ai_autonomy_level = models.CharField(
        max_length=20,
        choices=AIAutonomyLevel.choices,
        default=AIAutonomyLevel.SEMI_AUTO,
    )
    commission_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Booking narxidan chegirma foizi (%)',
    )
    exclusive_events_access = models.BooleanField(
        default=False,
        help_text='Eksklyuziv tadbirlarga kirish',
    )
    priority_support = models.BooleanField(default=False)
    sort_order       = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = "A'zolik darajasi"
        verbose_name_plural = "A'zolik darajalari"
        ordering = ['sort_order']

    def __str__(self) -> str:
        return self.name


class UserMembership(BaseModel):
    """
    Foydalanuvchining joriy a'zolik darajasi.
    `user.membership_tier` reverse relation orqali murojaat qilinadi.
    Subscription to'lovi muvaffaqiyatli bo'lganda yaratiladi/yangilanadi.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='membership_tier',
    )
    tier = models.ForeignKey(
        MembershipTier,
        on_delete=models.PROTECT,
        related_name='members',
    )
    # Tezroq access uchun tier maydonlari cache sifatida
    max_ai_autonomy_level       = models.CharField(max_length=20, default='manual')
    exclusive_events_access     = models.BooleanField(default=False)
    commission_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        verbose_name        = "Foydalanuvchi a'zoligi"
        verbose_name_plural = "Foydalanuvchilar a'zoligi"

    def __str__(self) -> str:
        return f'{self.user} → {self.tier.name}'

    def sync_from_tier(self) -> None:
        """Tier o'zgarganda cache maydonlarni yangilaydi."""
        self.max_ai_autonomy_level       = self.tier.max_ai_autonomy_level
        self.exclusive_events_access     = self.tier.exclusive_events_access
        self.commission_discount_percent = self.tier.commission_discount_percent
        self.save(update_fields=[
            'max_ai_autonomy_level',
            'exclusive_events_access',
            'commission_discount_percent',
            'updated_at',
        ])


class WaitlistApplication(BaseModel):
    """
    Yangi foydalanuvchi ariza topshiradi.
    Admin yoki promo-kod orqali tasdiqlanadi.
    Tasdiq bo'lganda UserMembership yaratiladi.
    """

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Kutilmoqda'
        APPROVED = 'approved', 'Tasdiqlangan'
        REJECTED = 'rejected', 'Rad etilgan'

    user   = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='waitlist_application',
    )
    status     = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    promo_code = models.CharField(max_length=32, blank=True, null=True)
    notes      = models.TextField(blank=True, help_text='Foydalanuvchi izohi')
    admin_notes= models.TextField(blank=True, help_text='Admin izohi (ichki)')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_applications',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Waitlist arizasi'
        verbose_name_plural = 'Waitlist arizalari'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.user} — {self.status}'

    @property
    def is_approved(self) -> bool:
        return self.status == self.Status.APPROVED


class PromoCode(BaseModel):
    """Waitlist'ni avtomatik tasdiqlash uchun promo-kodlar."""

    code       = models.CharField(max_length=32, unique=True)
    tier       = models.ForeignKey(MembershipTier, on_delete=models.CASCADE, related_name='promo_codes')
    max_uses   = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)
    is_active  = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Promo-kod'
        verbose_name_plural = 'Promo-kodlar'

    def __str__(self) -> str:
        return f'{self.code} ({self.tier.name})'

    @property
    def is_valid(self) -> bool:
        from django.utils import timezone
        return (
            self.is_active
            and self.used_count < self.max_uses
            and (not self.expires_at or self.expires_at > timezone.now())
        )


class Subscription(BaseModel):
    """
    Foydalanuvchi oylik obunasi (recurring billing).
    To'lov muvaffaqiyatli bo'lganda UserMembership yaratiladi/yangilanadi.
    """

    class Status(models.TextChoices):
        ACTIVE    = 'active',    'Faol'
        PAST_DUE  = 'past_due',  "To'lov muddati o'tgan"
        CANCELLED = 'cancelled', 'Bekor qilingan'
        TRIAL     = 'trial',     'Sinov davri'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions',
    )
    tier = models.ForeignKey(
        MembershipTier,
        on_delete=models.PROTECT,
        related_name='subscriptions',
    )
    status         = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    card_token     = models.CharField(max_length=255, blank=True, null=True)
    card_last_four = models.CharField(max_length=4,   blank=True, null=True)

    started_at           = models.DateTimeField()
    current_period_start = models.DateTimeField()
    current_period_end   = models.DateTimeField()
    cancelled_at         = models.DateTimeField(null=True, blank=True)

    retry_count          = models.PositiveSmallIntegerField(default=0)
    last_payment_attempt = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Obuna'
        verbose_name_plural = 'Obunalar'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.user} — {self.tier.name} ({self.status})'
