"""
Users app serializers.

Ro'yxatdan o'tish (4 qadam):
    1. RequestOTPSerializer          — full_name + phone_number → OTP SMS
    2. VerifyOTPSerializer           — phone_number + otp_code → verification_token
    3. CompleteRegistrationSerializer — verification_token + password
                                        + telegram_init_data (optional)
                                        → User yaratiladi + JWT (avtomatik login)
    4. (keyingi kirishlar)           → LoginSerializer: phone + password → JWT

Boshqa loginlar:
    CRMLoginSerializer   — phone + password, faqat owner/branch_staff
    AdminLoginSerializer — phone + password, faqat admin

Profile & Wallet:
    UserProfileSerializer, AISettingsSerializer, WalletTransactionSerializer
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from urllib.parse import parse_qsl

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AIAutonomyLevel, OTPCode, User, UserRole, WalletTransaction

# ─── Yordamchi ────────────────────────────────────────────────────────────────

PHONE_RE = re.compile(r'^\+998\d{9}$')
_signer  = TimestampSigner()   # Django SECRET_KEY bilan imzolaydi, vaqt bilan


def _normalize_phone(value: str) -> str:
    phone = value.strip().replace(' ', '').replace('-', '')
    if not phone.startswith('+'):
        phone = '+' + phone
    return phone


def _build_jwt_response(user: User) -> dict:
    """JWT yaratadi; token ichiga role va aud claim yoziladi."""
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['aud']  = user.jwt_audience
    return {
        'success': True,
        'access':  str(refresh.access_token),
        'refresh': str(refresh),
        'user':    UserProfileSerializer(user).data,
    }


def _verify_telegram_init_data(init_data: str) -> dict | None:
    """
    Telegram Mini App initData HMAC-SHA256 tekshiruvi.
    To'g'ri bo'lsa parse qilingan dict qaytaradi, xato bo'lsa None.
    auth_date 5 daqiqadan eski bo'lsa ham None.
    """
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not bot_token:
        return None

    parsed        = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop('hash', None)
    if not received_hash:
        return None

    data_check = '\n'.join(f'{k}={v}' for k, v in sorted(parsed.items()))
    secret_key  = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    computed    = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        return None

    if time.time() - int(parsed.get('auth_date', 0)) > 300:
        return None

    result = dict(parsed)
    if 'user' in result:
        result['user'] = json.loads(result['user'])
    return result


# ─── Qadam 1: OTP so'rash ─────────────────────────────────────────────────────

class RequestOTPSerializer(serializers.Serializer):
    """
    POST /api/auth/register/request-otp/

    full_name + phone_number → OTP SMS yuboriladi.
    full_name Redis'da 15 daqiqa saqlanadi (keyingi qadamda kerak).
    Allaqachon ro'yxatdan o'tgan raqam xato qaytaradi.
    """
    full_name    = serializers.CharField(max_length=128, min_length=2)
    phone_number = serializers.CharField(max_length=20)

    def validate_full_name(self, value: str) -> str:
        parts = value.strip().split()
        if len(parts) < 2:
            raise serializers.ValidationError(
                "Ism va familiyani to'liq kiriting (kamida 2 so'z)."
            )
        return value.strip()

    def validate_phone_number(self, value: str) -> str:
        phone = _normalize_phone(value)
        if not PHONE_RE.match(phone):
            raise serializers.ValidationError(
                "Telefon raqam formati noto'g'ri. Format: +998XXXXXXXXX"
            )
        if User.objects.filter(phone=phone, is_phone_verified=True).exists():
            raise serializers.ValidationError(
                "Bu raqam allaqachon ro'yxatdan o'tgan. Kirish sahifasiga o'ting."
            )
        return phone


# ─── Qadam 2: OTP tasdiqlash ──────────────────────────────────────────────────

class VerifyOTPSerializer(serializers.Serializer):
    """
    POST /api/auth/register/verify-otp/

    phone_number + otp_code → verification_token (15 daqiqa amal qiladi).
    Token CompleteRegistration'da ishlatiladi.
    """
    phone_number = serializers.CharField(max_length=20)
    otp_code     = serializers.CharField(max_length=6, min_length=6)

    def validate_phone_number(self, value: str) -> str:
        return _normalize_phone(value)

    def validate(self, attrs: dict) -> dict:
        phone    = attrs['phone_number']
        otp_code = attrs['otp_code']

        otp = (
            OTPCode.objects
            .filter(phone=phone, purpose=OTPCode.Purpose.REGISTER, is_used=False)
            .order_by('-created_at')
            .first()
        )

        if not otp:
            raise serializers.ValidationError(
                {'otp_code': "Faol OTP kod topilmadi. Qayta kod so'rang."}
            )
        if not otp.is_valid:
            raise serializers.ValidationError(
                {'otp_code': "OTP muddati o'tgan (5 daqiqa). Qayta kod so'rang."}
            )
        if otp.attempts >= 5:
            raise serializers.ValidationError(
                {'otp_code': "Urinishlar soni oshib ketdi. Qayta kod so'rang."}
            )
        if not otp.verify(otp_code):
            remaining = max(0, 5 - otp.attempts)
            raise serializers.ValidationError(
                {'otp_code': f"Noto'g'ri kod. {remaining} ta urinish qoldi."}
            )

        attrs['phone'] = phone
        return attrs

    def get_verification_token(self) -> str:
        """
        Django Signer bilan imzolangan token.
        Payload: tasdiqlangan telefon raqam.
        CompleteRegistration'da max_age=900 (15 daqiqa) bilan unsign qilinadi.
        """
        return _signer.sign(self.validated_data['phone'])


# ─── Qadam 3: Ro'yxatdan o'tishni yakunlash ──────────────────────────────────

class CompleteRegistrationSerializer(serializers.Serializer):
    """
    POST /api/auth/register/complete/

    Fields:
        verification_token  — VerifyOTP'dan kelgan imzolangan token (15 daqiqa)
        password            — yangi parol (Django password validators orqali)
        telegram_init_data  — ixtiyoriy, Telegram Mini App'dan (window.Telegram.WebApp.initData)
                              Kelsa: HMAC tekshiriladi, telegram_id bog'lanadi.
                              Kelmasa: faqat phone+password bilan user yaratiladi.

    Muvaffaqiyatli bo'lsa:
        - User yaratiladi (is_phone_verified=True)
        - Cache tozalanadi
        - JWT qaytariladi (avtomatik login — qadam 4)
    """
    verification_token = serializers.CharField()
    password           = serializers.CharField(write_only=True, min_length=8)
    telegram_init_data = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate_verification_token(self, value: str) -> str:
        """Token unsign qilinadi, natijasi — telefon raqam."""
        try:
            phone = _signer.unsign(value, max_age=900)
        except SignatureExpired:
            raise serializers.ValidationError(
                "Tasdiqlash muddati tugagan (15 daqiqa). Qaytadan OTP so'rang."
            )
        except BadSignature:
            raise serializers.ValidationError("Noto'g'ri tasdiqlash tokeni.")
        return phone   # validated_data['verification_token'] = phone raqami

    def validate(self, attrs: dict) -> dict:
        phone         = attrs['verification_token']   # unsign natijasi
        init_data_raw = attrs.get('telegram_init_data', '').strip()

        # Register ma'lumotlari (full_name) Redis'dan olinadi
        register_data = cache.get(f'register_data:{phone}')
        if not register_data:
            raise serializers.ValidationError(
                "Ro'yxatdan o'tish ma'lumotlari topilmadi. Iltimos qaytadan boshlang."
            )

        attrs['phone']         = phone
        attrs['register_data'] = register_data

        # Telegram initData tekshiruvi (ixtiyoriy)
        telegram_id = None
        tg_user     = {}
        if init_data_raw:
            parsed = _verify_telegram_init_data(init_data_raw)
            if parsed is None:
                raise serializers.ValidationError(
                    {'telegram_init_data': "Telegram ma'lumotlari tekshiruvdan o'tmadi."}
                )
            tg_user     = parsed.get('user', {})
            telegram_id = tg_user.get('id')

            if telegram_id and User.objects.filter(telegram_id=telegram_id).exists():
                raise serializers.ValidationError(
                    {'telegram_init_data': "Bu Telegram akkaunt boshqa foydalanuvchiga bog'langan."}
                )

        attrs['telegram_id'] = telegram_id
        attrs['tg_user']     = tg_user
        return attrs

    def create_user_and_respond(self) -> dict:
        """
        User DB ga yoziladi, cache tozalanadi, JWT qaytariladi.
        Bu qadam 4 — avtomatik login.
        """
        phone     = self.validated_data['phone']
        reg       = self.validated_data['register_data']
        tg_id     = self.validated_data['telegram_id']
        tg_user   = self.validated_data['tg_user']

        # full_name → first_name + last_name
        parts      = reg['full_name'].split(maxsplit=1)
        first_name = parts[0]
        last_name  = parts[1] if len(parts) > 1 else ''

        user = User.objects.create(
            phone             = phone,
            first_name        = first_name,
            last_name         = last_name,
            is_phone_verified = True,
            role              = UserRole.CUSTOMER,
            telegram_id       = tg_id or None,
            telegram_username = tg_user.get('username') if tg_user else None,
            language_code     = tg_user.get('language_code', 'uz') if tg_user else 'uz',
        )
        user.set_password(self.validated_data['password'])
        user.save(update_fields=['password'])

        cache.delete(f'register_data:{phone}')

        response = _build_jwt_response(user)
        response['is_new_user'] = True
        return response


# ─── Qadam 4 (keyingi kirish): Login ─────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    """
    POST /api/auth/login/   — faqat customer roli (mobile audience)

    phone + password → JWT.
    Rol tekshiruvi server tomonida amalga oshiriladi.
    Customer tokeni CRM/Admin panelga kira olmaydi (aud claim).
    """
    phone    = serializers.CharField()
    password = serializers.CharField(write_only=True)

    allowed_roles: list[str] = [UserRole.CUSTOMER]

    def validate_phone(self, value: str) -> str:
        return _normalize_phone(value)

    def validate(self, attrs: dict) -> dict:
        user = authenticate(
            request=self.context.get('request'),
            username=attrs['phone'],
            password=attrs['password'],
        )
        if not user:
            raise serializers.ValidationError(
                "Telefon raqam yoki parol noto'g'ri."
            )
        if not user.is_active:
            raise serializers.ValidationError(
                "Akkaunt faol emas. Administrator bilan bog'laning."
            )
        if user.role not in self.allowed_roles:
            raise serializers.ValidationError(
                "Bu panelga kirish huquqi yo'q."
            )
        attrs['user'] = user
        return attrs

    def get_jwt_response(self) -> dict:
        return _build_jwt_response(self.validated_data['user'])


class CRMLoginSerializer(LoginSerializer):
    """
    POST /api/crm/auth/login/   — faqat owner va branch_staff (crm audience)
    """
    allowed_roles = [UserRole.OWNER, UserRole.BRANCH_STAFF]


class AdminLoginSerializer(LoginSerializer):
    """
    POST /api/admin/auth/login/   — faqat admin roli (admin audience)
    """
    allowed_roles = [UserRole.ADMIN]


# ─── Profile ──────────────────────────────────────────────────────────────────

class UserProfileSerializer(serializers.ModelSerializer):
    full_name             = serializers.CharField(read_only=True)
    membership_tier_name  = serializers.SerializerMethodField()
    waitlist_status       = serializers.SerializerMethodField()
    effective_ai_autonomy = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'telegram_id', 'telegram_username',
            'phone', 'is_phone_verified', 'role',
            'first_name', 'last_name', 'full_name',
            'avatar_url', 'language_code',
            'ai_autonomy_level', 'ai_auto_price_limit',
            'balance', 'bonus_points',
            'membership_tier_name', 'waitlist_status',
            'effective_ai_autonomy',
            'created_at',
        ]
        read_only_fields = [
            'id', 'telegram_id', 'role',
            'balance', 'bonus_points',
            'is_phone_verified', 'created_at',
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_membership_tier_name(self, obj) -> str | None:
        try:
            return obj.membership_tier.name
        except Exception:
            return None

    @extend_schema_field(serializers.CharField())
    def get_waitlist_status(self, obj) -> str:
        try:
            return obj.waitlist_application.status
        except Exception:
            return 'not_applied'

    @extend_schema_field(serializers.CharField())
    def get_effective_ai_autonomy(self, obj) -> str:
        return obj.get_effective_ai_autonomy_level()


class AISettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['ai_autonomy_level', 'ai_auto_price_limit']

    def validate_ai_autonomy_level(self, value: str) -> str:
        if value not in AIAutonomyLevel.values:
            raise serializers.ValidationError("Noto'g'ri daraja.")
        return value


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WalletTransaction
        fields = ['id', 'transaction_type', 'amount', 'balance_after', 'description', 'created_at']
        read_only_fields = fields
