"""
Users app modellari.

Auth oqimi:
    Ro'yxatdan o'tish (4 qadam, Telegram Mini App):
        1. full_name + phone   → OTP SMS yuboriladi
        2. phone + otp_code    → verification_token qaytariladi
        3. token + password + telegram_init_data → User yaratiladi + JWT
        4. (keyingi kirish)    → phone + password → JWT

Rollar:
    customer          — Telegram Mini App / Mobile App foydalanuvchisi
    owner_restaurant  — Restoran kompaniyasi egasi (CRM)
    restaurant_staff  — Restoran filial xodimi (CRM)
    owner_tour        — Tur kompaniyasi egasi (CRM)
    tour_staff        — Tur kompaniyasi xodimi (CRM)
    admin             — ichki xodim (Django admin + Admin panel)

JWT audience:
    customer / boshqa → 'mobile'
    CRM rollar        → 'crm'
    admin               → 'admin'
"""

from __future__ import annotations

import random
import string
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


# ─── Choices ──────────────────────────────────────────────────────────────────

class UserRole(models.TextChoices):
    CUSTOMER          = 'customer',          'Mijoz'
    OWNER_RESTAURANT  = 'owner_restaurant',  'Restoran egasi'
    RESTAURANT_STAFF  = 'restaurant_staff',  'Restoran xodimi'
    OWNER_TOUR        = 'owner_tour',        'Tur kompaniyasi egasi'
    TOUR_STAFF        = 'tour_staff',        'Tur kompaniyasi xodimi'
    ADMIN             = 'admin',             'Admin'

    # Deprecated — migratsiya uchun saqlanadi, yangi foydalanuvchilarda ishlatilmaydi
    OWNER        = 'owner',        'Tashkilot egasi (eski)'
    BRANCH_STAFF = 'branch_staff', 'Filial xodimi (eski)'


class AIAutonomyLevel(models.TextChoices):
    MANUAL    = 'manual',    "Qo'lda tasdiqlash (har bir harakatda)"
    SEMI_AUTO = 'semi_auto', "Yarim avtomatik (yuqori summada tasdiqlash)"
    FULL_AUTO = 'full_auto', "To'liq avtomatik"


# ─── Manager ──────────────────────────────────────────────────────────────────

class UserManager(BaseUserManager):
    def create_user(self, phone: str, password: str | None = None, **extra_fields):
        if not phone:
            raise ValueError('Telefon raqam majburiy.')
        extra_fields.setdefault('role', UserRole.CUSTOMER)
        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone: str, password: str, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.ADMIN)
        extra_fields.setdefault('is_phone_verified', True)
        if not extra_fields.get('is_staff'):
            raise ValueError("Superuser is_staff=True bo'lishi shart.")
        return self.create_user(phone, password, **extra_fields)


# ─── User ─────────────────────────────────────────────────────────────────────

class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """
    Yagona foydalanuvchi modeli — barcha kanallar uchun.

    USERNAME_FIELD = 'phone' — Django admin va PhoneBackend uchun.
    Parol majburiy — register oqimining 3-qadamida o'rnatiladi.
    telegram_id — ixtiyoriy, CompleteRegistration vaqtida bog'lanadi.
    """

    # ── Identifikatorlar ──────────────────────────────────────────────────────
    phone             = models.CharField(max_length=20, unique=True, db_index=True)
    telegram_id       = models.BigIntegerField(unique=True, null=True, blank=True, db_index=True)
    telegram_username = models.CharField(max_length=64, blank=True, null=True)

    # ── Rol ───────────────────────────────────────────────────────────────────
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        db_index=True,
    )

    # ── Shaxsiy ──────────────────────────────────────────────────────────────
    first_name    = models.CharField(max_length=64, blank=True)
    last_name     = models.CharField(max_length=64, blank=True)
    email         = models.EmailField(blank=True, default='')
    avatar_url    = models.URLField(blank=True, null=True)
    language_code = models.CharField(max_length=10, default='uz')

    # ── Tasdiqlash ────────────────────────────────────────────────────────────
    is_phone_verified = models.BooleanField(
        default=False,
        help_text='SMS OTP orqali tasdiqlangan (register 2-qadamida True bo\'ladi)',
    )

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

    # ── Django ────────────────────────────────────────────────────────────────
    is_active = models.BooleanField(default=True)
    is_staff  = models.BooleanField(default=False)

    USERNAME_FIELD  = 'phone'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name        = 'Foydalanuvchi'
        verbose_name_plural = 'Foydalanuvchilar'
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['telegram_id']),
            models.Index(fields=['role']),
        ]

    def __str__(self) -> str:
        return f'{self.full_name or self.phone} [{self.role}]'

    @property
    def full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def jwt_audience(self) -> str:
        """JWT tokenga yoziladigan audience."""
        from apps.users.crm_roles import is_crm_role

        if self.role == UserRole.ADMIN:
            return 'admin'
        if is_crm_role(self.role):
            return 'crm'
        return 'mobile'

    @property
    def organization(self):
        """Foydalanuvchi roliga qarab tegishli Organization'ni qaytaradi."""
        from apps.users.crm_roles import (
            LEGACY_OWNER_ROLES,
            is_restaurant_owner,
            is_tour_owner,
        )

        if (
            is_restaurant_owner(self.role)
            or is_tour_owner(self.role)
            or self.role in LEGACY_OWNER_ROLES
        ):
            return getattr(self, 'owned_organization', None)
        if self.role in (UserRole.RESTAURANT_STAFF, UserRole.TOUR_STAFF, UserRole.BRANCH_STAFF):
            profile = getattr(self, 'branch_staff_profile', None)
            return profile.branch.organization if profile else None
        return None

    @property
    def is_restaurant_crm(self) -> bool:
        from apps.users.crm_roles import RESTAURANT_CRM_ROLES
        return self.role in RESTAURANT_CRM_ROLES

    @property
    def is_tour_crm(self) -> bool:
        from apps.users.crm_roles import TOUR_CRM_ROLES
        return self.role in TOUR_CRM_ROLES

    def get_effective_ai_autonomy_level(self) -> str:
        """Haqiqiy daraja = min(user tanlagan, tier maksimum)."""
        try:
            tier = self.membership_tier
            order = {
                AIAutonomyLevel.MANUAL:    0,
                AIAutonomyLevel.SEMI_AUTO: 1,
                AIAutonomyLevel.FULL_AUTO: 2,
            }
            effective = min(
                order.get(self.ai_autonomy_level, 0),
                order.get(tier.max_ai_autonomy_level, 0),
            )
            return list(order.keys())[effective]
        except Exception:
            return self.ai_autonomy_level


# ─── OTP ──────────────────────────────────────────────────────────────────────

OTP_EXPIRE_MINUTES = 5
OTP_LENGTH         = 6
OTP_MAX_ATTEMPTS   = 5


class OTPCode(BaseModel):
    """
    SMS orqali yuboriladigan bir martalik kod (DevSMS gateway).

    Purpose.REGISTER     — ro'yxatdan o'tish oqimida (1-qadam)
    Purpose.PASSWORD_RESET — parolni tiklash oqimida
    """

    class Purpose(models.TextChoices):
        REGISTER       = 'register',       "Ro'yxatdan o'tish"
        PASSWORD_RESET = 'password_reset', 'Parolni tiklash'

    phone      = models.CharField(max_length=20, db_index=True)
    code       = models.CharField(max_length=10)
    purpose    = models.CharField(
        max_length=20,
        choices=Purpose.choices,
        default=Purpose.REGISTER,
    )
    is_used    = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    attempts   = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = 'OTP Kod'
        verbose_name_plural = 'OTP Kodlar'
        ordering            = ['-created_at']
        indexes             = [models.Index(fields=['phone', 'purpose', 'is_used', 'expires_at'])]

    def __str__(self) -> str:
        return f'{self.phone} | {self.purpose} | {"used" if self.is_used else "active"}'

    @classmethod
    def create_for_phone(cls, phone: str, purpose: str = Purpose.REGISTER) -> 'OTPCode':
        """Yangi OTP yaratadi; bir xil purpose'dagi avvalgi faollar bekor qilinadi."""
        cls.objects.filter(phone=phone, purpose=purpose, is_used=False).update(is_used=True)
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
        """
        Kodni tekshiradi. Muvaffaqiyatli → is_used=True.
        OTP_MAX_ATTEMPTS dan ortiq urinishda False (brute-force himoya).
        """
        if self.attempts >= OTP_MAX_ATTEMPTS:
            return False
        self.attempts += 1
        self.save(update_fields=['attempts'])
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


# ─── UserDevice ───────────────────────────────────────────────────────────────

class UserDevice(BaseModel):
    """
    Foydalanuvchi qurilmalari va sessiya tracking.

    Maqsadlar:
        - "Barcha qurilmalardan chiqish" — barcha JTI ni blacklist qilish
        - Push notification (FCM token)
        - Xavfsizlik audit
    """

    class DeviceType(models.TextChoices):
        MOBILE    = 'mobile',    'Mobile (Flutter)'
        TELEGRAM  = 'telegram',  'Telegram Mini App'
        WEB_CRM   = 'web_crm',   'Web CRM'
        WEB_ADMIN = 'web_admin', 'Web Admin'

    user              = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    device_type       = models.CharField(max_length=20, choices=DeviceType.choices)
    refresh_token_jti = models.CharField(
        max_length=255, unique=True,
        help_text='JWT refresh tokenning JTI claim qiymati',
    )
    fcm_token   = models.CharField(max_length=255, null=True, blank=True)
    device_name = models.CharField(max_length=100, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    last_active = models.DateTimeField(auto_now=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Foydalanuvchi qurilmasi'
        verbose_name_plural = 'Foydalanuvchi qurilmalari'
        ordering            = ['-last_active']
        indexes             = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['refresh_token_jti']),
        ]

    def __str__(self) -> str:
        return f'{self.user} | {self.device_type} | {self.device_name or self.ip_address}'
