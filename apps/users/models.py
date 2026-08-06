"""
Users app — foydalanuvchi modeli, AI sozlamalari, OTP autentifikatsiya.

Auth kanallar:
    1. Telegram initData (Mini App)
    2. Telefon + SMS OTP (Eskiz gateway)
"""

from __future__ import annotations

import random
import string
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class UserManager(BaseUserManager):
    def create_user(self, telegram_id=None, phone=None, **extra_fields):
        if not telegram_id and not phone:
            raise ValueError('Telegram ID yoki telefon raqam majburiy.')
        user = self.model(telegram_id=telegram_id, phone=phone, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, telegram_id, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        user = self.model(telegram_id=telegram_id, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user


class AIAutonomyLevel(models.TextChoices):
    MANUAL    = 'manual',    "Qo'lda tasdiqlash (har bir harakatda)"
    SEMI_AUTO = 'semi_auto', "Yarim avtomatik (yuqori summada tasdiqlash)"
    FULL_AUTO = 'full_auto', "To'liq avtomatik"


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """
    Asosiy foydalanuvchi modeli.
    Telegram initData yoki Telefon+OTP orqali yaratiladi.
    Parol ishlatilmaydi.
    """
    # ── Identifikatorlar ──────────────────────────────────────────────────────
    telegram_id       = models.BigIntegerField(unique=True, null=True, blank=True, db_index=True)
    telegram_username = models.CharField(max_length=64, blank=True, null=True)
    phone             = models.CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)

    # ── Shaxsiy ma'lumotlar ───────────────────────────────────────────────────
    first_name    = models.CharField(max_length=64, blank=True)
    last_name     = models.CharField(max_length=64, blank=True)
    avatar_url    = models.URLField(blank=True, null=True)
    language_code = models.CharField(max_length=10, default='ru')

    # ── AI sozlamalari ────────────────────────────────────────────────────────
    ai_autonomy_level = models.CharField(
        max_length=20,
        choices=AIAutonomyLevel.choices,
        default=AIAutonomyLevel.MANUAL,
    )
    ai_auto_price_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=500_000,
        help_text="full_auto uchun maksimal avtomatik bron summasi (UZS)",
    )

    # ── Hamyon ────────────────────────────────────────────────────────────────
    balance      = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    bonus_points = models.PositiveIntegerField(default=0)

    # ── Status ────────────────────────────────────────────────────────────────
    is_active = models.BooleanField(default=True)
    is_staff  = models.BooleanField(default=False)

    # ── Auth ──────────────────────────────────────────────────────────────────
    # telegram_id yoki phone bilan kirish
    USERNAME_FIELD  = 'telegram_id'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name        = 'Foydalanuvchi'
        verbose_name_plural = 'Foydalanuvchilar'
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['telegram_id']),
        ]

    def __str__(self) -> str:
        name = self.full_name or str(self.telegram_id or self.phone)
        return f'{name} (@{self.telegram_username or "-"})'

    @property
    def full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip()

    def get_effective_ai_autonomy_level(self) -> str:
        """
        Haqiqiy daraja = min(user tanlagan, tier maksimum).
        """
        try:
            tier = self.membership_tier
            order = {
                AIAutonomyLevel.MANUAL:    0,
                AIAutonomyLevel.SEMI_AUTO: 1,
                AIAutonomyLevel.FULL_AUTO: 2,
            }
            user_lvl = order.get(self.ai_autonomy_level, 0)
            tier_max = order.get(tier.max_ai_autonomy_level, 0)
            effective = min(user_lvl, tier_max)
            return list(order.keys())[effective]
        except Exception:
            return self.ai_autonomy_level


# ─── OTP ──────────────────────────────────────────────────────────────────────

OTP_EXPIRE_MINUTES = 5
OTP_LENGTH         = 6


class OTPCode(BaseModel):
    """
    SMS orqali yuboriladigan bir martalik kod.
    Eskiz SMS gateway ishlatiladi.

    Oqim:
        POST /api/auth/sms/send/    → kod yaratiladi, SMS yuboriladi
        POST /api/auth/sms/verify/  → kod tekshiriladi, JWT qaytariladi
    """

    class Purpose(models.TextChoices):
        LOGIN    = 'login',    'Kirish'
        REGISTER = 'register', "Ro'yxatdan o'tish"
        VERIFY   = 'verify',   'Telefon tasdiqlash'

    phone     = models.CharField(max_length=20, db_index=True)
    code      = models.CharField(max_length=10)
    purpose   = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.LOGIN)
    is_used   = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    # Brute-force himoya
    attempts  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = 'OTP Kod'
        verbose_name_plural = 'OTP Kodlar'
        ordering            = ['-created_at']
        indexes             = [models.Index(fields=['phone', 'is_used', 'expires_at'])]

    def __str__(self) -> str:
        return f'{self.phone} | {self.code} | {"used" if self.is_used else "active"}'

    @classmethod
    def create_for_phone(cls, phone: str, purpose: str = Purpose.LOGIN) -> 'OTPCode':
        """Yangi OTP kodni yaratadi (avvalgisini bekor qiladi)."""
        # Avvalgi faol kodlarni bekor qilish
        cls.objects.filter(phone=phone, is_used=False).update(is_used=True)

        code = ''.join(random.choices(string.digits, k=OTP_LENGTH))
        return cls.objects.create(
            phone=phone,
            code=code,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRE_MINUTES),
        )

    @property
    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() < self.expires_at

    def verify(self, code: str) -> bool:
        """Kodni tekshiradi. Muvaffaqiyatli bo'lsa is_used=True."""
        self.attempts += 1
        self.save(update_fields=['attempts'])

        if self.attempts > 5:
            return False  # brute-force

        if self.is_valid and self.code == code:
            self.is_used = True
            self.save(update_fields=['is_used'])
            return True
        return False


# ─── Hamyon ───────────────────────────────────────────────────────────────────

class WalletTransaction(BaseModel):
    """Hamyon operatsiyalari tarixi."""

    class TransactionType(models.TextChoices):
        TOPUP       = 'topup',       "To'ldirish"
        PAYMENT     = 'payment',     "To'lov"
        REFUND      = 'refund',      'Qaytarish'
        BONUS_EARN  = 'bonus_earn',  "Bonus yig'ish"
        BONUS_SPEND = 'bonus_spend', 'Bonus sarflash'

    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet_transactions')
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount           = models.DecimalField(max_digits=14, decimal_places=2)
    balance_after    = models.DecimalField(max_digits=14, decimal_places=2)
    description      = models.CharField(max_length=255, blank=True)
    reference_id     = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        verbose_name        = 'Hamyon operatsiyasi'
        verbose_name_plural = 'Hamyon operatsiyalari'
        ordering            = ['-created_at']

    def __str__(self) -> str:
        return f'{self.user} | {self.transaction_type} | {self.amount}'
