"""Users app serializers — Telegram auth + SMS OTP auth."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from urllib.parse import unquote

from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, WalletTransaction, AIAutonomyLevel, OTPCode


# ─── Telegram Auth ────────────────────────────────────────────────────────────

class TelegramAuthSerializer(serializers.Serializer):
    """
    Telegram Mini App initData tekshiruvi.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    init_data = serializers.CharField(write_only=True)

    def validate_init_data(self, value: str) -> dict:
        parsed = dict(item.split('=', 1) for item in value.split('&'))
        received_hash = parsed.pop('hash', None)
        if not received_hash:
            raise serializers.ValidationError('hash maydoni topilmadi.')

        data_check_string = '\n'.join(
            f'{k}={unquote(v)}' for k, v in sorted(parsed.items())
        )
        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token:
            raise serializers.ValidationError('Telegram bot sozlanmagan.')

        secret_key = hmac.new(
            b'WebAppData', bot_token.encode(), hashlib.sha256
        ).digest()
        expected = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, received_hash):
            raise serializers.ValidationError('initData tekshiruvi muvaffaqiyatsiz.')

        auth_date = int(parsed.get('auth_date', 0))
        if time.time() - auth_date > 300:
            raise serializers.ValidationError("initData muddati o'tgan.")

        return json.loads(unquote(parsed.get('user', '{}')))

    def get_or_create_user(self) -> User:
        data = self.validated_data['init_data']
        user, _ = User.objects.get_or_create(
            telegram_id=data['id'],
            defaults={
                'telegram_username': data.get('username'),
                'first_name': data.get('first_name', ''),
                'last_name': data.get('last_name', ''),
                'language_code': data.get('language_code', 'ru'),
            },
        )
        # Ma'lumotlarni yangilab turish
        User.objects.filter(pk=user.pk).update(
            telegram_username=data.get('username') or user.telegram_username,
            first_name=data.get('first_name', user.first_name),
            last_name=data.get('last_name', user.last_name),
        )
        user.refresh_from_db()
        return user


# ─── SMS OTP Auth ─────────────────────────────────────────────────────────────

PHONE_RE = re.compile(r'^\+998\d{9}$')


class SMSSendSerializer(serializers.Serializer):
    """
    POST /api/auth/sms/send/
    Telefon raqamga OTP kod yuboradi.
    """
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value: str) -> str:
        phone = value.strip().replace(' ', '').replace('-', '')
        if not phone.startswith('+'):
            phone = '+' + phone
        if not PHONE_RE.match(phone):
            raise serializers.ValidationError(
                "Telefon raqam formati noto'g'ri. Masalan: +998901234567"
            )
        return phone


class SMSVerifySerializer(serializers.Serializer):
    """
    POST /api/auth/sms/verify/
    OTP kodni tekshiradi va JWT qaytaradi.
    """
    phone = serializers.CharField(max_length=20)
    code  = serializers.CharField(max_length=10)

    def validate_phone(self, value: str) -> str:
        phone = value.strip().replace(' ', '').replace('-', '')
        if not phone.startswith('+'):
            phone = '+' + phone
        return phone

    def validate(self, attrs: dict) -> dict:
        phone = attrs['phone']
        code  = attrs['code']

        otp = (
            OTPCode.objects
            .filter(phone=phone, is_used=False)
            .order_by('-created_at')
            .first()
        )
        if not otp:
            raise serializers.ValidationError({'code': "Faol OTP kod topilmadi. Qayta kod so'rang."})

        if not otp.is_valid:
            raise serializers.ValidationError({'code': "OTP muddati o'tgan. Qayta kod so'rang."})

        if otp.attempts >= 5:
            raise serializers.ValidationError({'code': "Urinishlar soni oshib ketdi. Qayta kod so'rang."})

        if not otp.verify(code):
            remaining = 5 - otp.attempts
            raise serializers.ValidationError(
                {'code': f"Noto'g'ri kod. {remaining} ta urinish qoldi."}
            )

        attrs['otp'] = otp
        return attrs

    def get_or_create_user(self) -> User:
        phone = self.validated_data['phone']
        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={'language_code': 'uz'},
        )
        return user


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
            'first_name', 'last_name', 'full_name',
            'phone', 'avatar_url', 'language_code',
            'ai_autonomy_level', 'ai_auto_price_limit',
            'balance', 'bonus_points',
            'membership_tier_name', 'waitlist_status',
            'effective_ai_autonomy',
            'created_at',
        ]
        read_only_fields = [
            'id', 'telegram_id', 'balance',
            'bonus_points', 'created_at',
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
        fields = [
            'id', 'transaction_type', 'amount',
            'balance_after', 'description', 'created_at',
        ]
        read_only_fields = fields
