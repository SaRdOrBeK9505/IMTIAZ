"""
Users app views.

Auth endpoint'lar:
    POST /api/auth/telegram/    — Telegram initData → JWT
    POST /api/auth/sms/send/    — Telefon → OTP SMS (Eskiz)
    POST /api/auth/sms/verify/  — OTP kod → JWT
    POST /api/auth/token/refresh/ — JWT refresh (simplejwt)

Profile endpoint'lar:
    GET  /api/users/me/
    PATCH /api/users/me/
    PATCH /api/users/me/ai-settings/
    GET  /api/wallet/
"""

from __future__ import annotations

import logging

from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, WalletTransaction, OTPCode
from .serializers import (
    TelegramAuthSerializer,
    SMSSendSerializer,
    SMSVerifySerializer,
    UserProfileSerializer,
    AISettingsSerializer,
    WalletTransactionSerializer,
)

logger = logging.getLogger(__name__)


def _jwt_response(user: User) -> dict:
    """Foydalanuvchi uchun JWT token va profil ma'lumotlarini qaytaradi."""
    refresh = RefreshToken.for_user(user)
    return {
        'success': True,
        'access':  str(refresh.access_token),
        'refresh': str(refresh),
        'user':    UserProfileSerializer(user).data,
    }


# ─── Auth ─────────────────────────────────────────────────────────────────────

class TelegramAuthView(APIView):
    """POST /api/auth/telegram/"""
    permission_classes = [AllowAny]

    @extend_schema(
        request=TelegramAuthSerializer,
        responses={200: OpenApiResponse(description='JWT + profil')},
        summary='Telegram Mini App orqali kirish',
        tags=['Auth'],
    )
    def post(self, request):
        serializer = TelegramAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.get_or_create_user()
        logger.info('Telegram auth: user=%s', user.id)
        return Response(_jwt_response(user))


class SMSSendView(APIView):
    """
    POST /api/auth/sms/send/
    Telefon raqamga OTP SMS yuboradi (Eskiz gateway).
    Rate limit: 1 SMS / 60 soniya (Redis orqali).
    """
    permission_classes = [AllowAny]

    @extend_schema(
        request=SMSSendSerializer,
        responses={
            200: OpenApiResponse(description='SMS yuborildi'),
            429: OpenApiResponse(description='Juda ko\'p so\'rov'),
        },
        summary='OTP SMS yuborish',
        tags=['Auth'],
    )
    def post(self, request):
        serializer = SMSSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']

        # Rate limit — 60 soniyada 1 ta so'rov
        from django.core.cache import cache
        rate_key = f'sms_rate:{phone}'
        if cache.get(rate_key):
            return Response(
                {'message': "Iltimos, 60 soniya kuting va qayta urinib ko'ring."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # OTP yaratish
        otp = OTPCode.create_for_phone(phone, purpose=OTPCode.Purpose.LOGIN)

        # SMS yuborish
        from .sms import send_otp_sms
        sent = send_otp_sms(phone, otp.code)

        if not sent:
            logger.error('SMS yuborilmadi: phone=%s', phone)
            return Response(
                {'message': 'SMS yuborishda xato. Qayta urinib ko\'ring.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Rate limit o'rnatish
        cache.set(rate_key, True, timeout=60)
        logger.info('OTP SMS yuborildi: phone=%s', phone)

        return Response({
            'success': True,
            'message': f"SMS yuborildi: {phone[:7]}***",
            'expires_in': 300,  # 5 daqiqa
        })


class SMSVerifyView(APIView):
    """
    POST /api/auth/sms/verify/
    OTP kodni tekshirib JWT qaytaradi.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        request=SMSVerifySerializer,
        responses={
            200: OpenApiResponse(description='JWT + profil'),
            400: OpenApiResponse(description="Noto'g'ri kod"),
        },
        summary='OTP kodni tasdiqlash va kirish',
        tags=['Auth'],
    )
    def post(self, request):
        serializer = SMSVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.get_or_create_user()
        logger.info('SMS OTP auth muvaffaqiyatli: user=%s, phone=%s', user.id, user.phone)
        return Response(_jwt_response(user))


# ─── Profile ──────────────────────────────────────────────────────────────────

class UserMeView(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/users/me/"""
    permission_classes  = [IsAuthenticated]
    serializer_class    = UserProfileSerializer
    http_method_names   = ['get', 'patch']

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class AISettingsView(generics.UpdateAPIView):
    """PATCH /api/users/me/ai-settings/"""
    permission_classes  = [IsAuthenticated]
    serializer_class    = AISettingsSerializer
    http_method_names   = ['patch']

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class WalletView(APIView):
    """GET /api/wallet/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OpenApiResponse(description='Hamyon holati')},
        summary='Hamyon balansi va oxirgi operatsiyalar',
        tags=['Users'],
    )
    def get(self, request):
        user   = request.user
        recent = WalletTransaction.objects.filter(user=user)[:10]
        return Response({
            'balance':             user.balance,
            'bonus_points':        user.bonus_points,
            'recent_transactions': WalletTransactionSerializer(recent, many=True).data,
        })
