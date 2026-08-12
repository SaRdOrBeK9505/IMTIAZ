"""
Users app views.

Ro'yxatdan o'tish (4 qadam):
    POST /api/auth/register/request-otp/   — full_name + phone → OTP SMS
    POST /api/auth/register/verify-otp/    — phone + otp_code → verification_token
    POST /api/auth/register/complete/      — token + password + [init_data] → JWT

Login:
    POST /api/auth/login/           — customer  (mobile aud)
    POST /api/crm/auth/login/       — owner/branch_staff (crm aud)
    POST /api/admin/auth/login/     — admin (admin aud)
    POST /api/auth/token/refresh/   — JWT refresh (simplejwt)
    POST /api/auth/logout/          — blacklist

Profile:
    GET  /api/users/me/
    PATCH /api/users/me/
    PATCH /api/users/me/ai-settings/
"""

from __future__ import annotations

import logging

from django.core.cache import cache
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPCode
from .serializers import (
    AdminLoginSerializer,
    AISettingsSerializer,
    CompleteRegistrationSerializer,
    CRMLoginSerializer,
    LoginSerializer,
    RequestOTPSerializer,
    UserProfileSerializer,
    VerifyOTPSerializer,
)
from .sms import send_otp_sms

logger = logging.getLogger(__name__)


# ─── Register: Qadam 1 ────────────────────────────────────────────────────────

class RequestOTPView(APIView):
    """
    POST /api/auth/register/request-otp/

    Kirish: { "full_name": "Asilbek Karimov", "phone_number": "+998901234567" }
    Chiqish: { "detail": "OTP yuborildi", "expires_in": 300 }

    - Allaqachon ro'yxatdan o'tgan raqam → 400
    - Rate limit: 60 soniyada 1 ta SMS
    - full_name Redis'da 15 daqiqa saqlanadi
    """
    permission_classes = [AllowAny]

    @extend_schema(
        request=RequestOTPSerializer,
        responses={
            200: OpenApiResponse(description='OTP SMS yuborildi'),
            400: OpenApiResponse(description='Validatsiya xatosi'),
            429: OpenApiResponse(description='Rate limit'),
            503: OpenApiResponse(description='SMS gateway xato'),
        },
        summary="Ro'yxatdan o'tish: OTP SMS yuborish (1-qadam)",
        tags=['Register'],
    )
    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone     = serializer.validated_data['phone_number']
        full_name = serializer.validated_data['full_name']

        # Rate limit — 60 soniyada 1 ta SMS
        rate_key = f'sms_rate:{phone}'
        if cache.get(rate_key):
            return Response(
                {'detail': "Iltimos, 60 soniya kuting va qayta urinib ko'ring."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # OTP yaratish (DB'ga yoziladi)
        otp = OTPCode.create_for_phone(phone, purpose=OTPCode.Purpose.REGISTER)

        # SMS yuborish
        sent = send_otp_sms(phone, otp.code)
        if not sent:
            logger.error('Register OTP SMS yuborilmadi: phone=%s', phone)
            return Response(
                {'detail': "SMS yuborishda xato. Qayta urinib ko'ring."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Rate limit va register ma'lumotlarini cache'ga yozish
        cache.set(rate_key, True, timeout=60)
        cache.set(f'register_data:{phone}', {'full_name': full_name}, timeout=900)

        logger.info("Register OTP SMS yuborildi: phone=%s", phone[:7])
        return Response({
            'detail':     'OTP yuborildi',
            'expires_in': 300,
        })


# ─── Register: Qadam 2 ────────────────────────────────────────────────────────

class VerifyOTPView(APIView):
    """
    POST /api/auth/register/verify-otp/

    Kirish: { "phone_number": "+998901234567", "otp_code": "123456" }
    Chiqish: { "verification_token": "...:..." }

    Token 15 daqiqa amal qiladi.
    Keyingi qadamda (CompleteRegistration) shu token ishlatiladi.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        request=VerifyOTPSerializer,
        responses={
            200: OpenApiResponse(description='verification_token qaytarildi'),
            400: OpenApiResponse(description="Noto'g'ri OTP"),
        },
        summary="Ro'yxatdan o'tish: OTP tasdiqlash (2-qadam)",
        tags=['Register'],
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.get_verification_token()
        logger.info(
            "OTP tasdiqlandi: phone=%s",
            serializer.validated_data['phone'][:7],
        )
        return Response({'verification_token': token})


# ─── Register: Qadam 3+4 ──────────────────────────────────────────────────────

class CompleteRegistrationView(APIView):
    """
    POST /api/auth/register/complete/

    Kirish:
    {
        "verification_token": "...",
        "password": "Qwerty123!",
        "telegram_init_data": "..."   // ixtiyoriy
    }

    Chiqish: JWT + user profili (avtomatik login, qadam 4)

    - telegram_init_data kelsa: HMAC tekshiriladi, telegram_id bog'lanadi
    - Kelmasayam ishlaydi (faqat phone+password)
    """
    permission_classes = [AllowAny]

    @extend_schema(
        request=CompleteRegistrationSerializer,
        responses={
            201: OpenApiResponse(description='User yaratildi, JWT qaytarildi'),
            400: OpenApiResponse(description='Validatsiya xatosi'),
        },
        summary="Ro'yxatdan o'tish: parol + Telegram bog'lash + JWT (3-4-qadam)",
        tags=['Register'],
    )
    def post(self, request):
        serializer = CompleteRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.create_user_and_respond()
        logger.info("Yangi user yaratildi: id=%s, phone=%s", data['user']['id'], data['user']['phone'][:7])
        return Response(data, status=status.HTTP_201_CREATED)


# ─── Login ────────────────────────────────────────────────────────────────────

class LoginView(APIView):
    """
    POST /api/auth/login/
    Customer uchun — phone + password → JWT (audience: mobile)
    """
    permission_classes = [AllowAny]
    serializer_class   = LoginSerializer

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(description='JWT + profil'),
            400: OpenApiResponse(description="Noto'g'ri ma'lumot"),
        },
        summary='Kirish: phone + password (customer)',
        tags=['Auth'],
    )
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.get_jwt_response()
        logger.info('Login: user=%s, role=%s', data['user']['id'], data['user']['role'])
        return Response(data)


class CRMLoginView(LoginView):
    """
    POST /api/crm/auth/login/
    owner / branch_staff — JWT (audience: crm)
    """
    serializer_class = CRMLoginSerializer

    @extend_schema(
        request=CRMLoginSerializer,
        responses={200: OpenApiResponse(description='JWT + profil')},
        summary='CRM kirish: phone + password (owner/branch_staff)',
        tags=['CRM Auth'],
    )
    def post(self, request):
        return super().post(request)


class AdminLoginView(LoginView):
    """
    POST /api/admin/auth/login/
    admin roli — JWT (audience: admin)
    """
    serializer_class = AdminLoginSerializer

    @extend_schema(
        request=AdminLoginSerializer,
        responses={200: OpenApiResponse(description='JWT + profil')},
        summary='Admin kirish: phone + password',
        tags=['Admin Auth'],
    )
    def post(self, request):
        return super().post(request)


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Refresh tokenni blacklist ga qo'shadi. Barcha kanallar uchun bir xil.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request={'application/json': {
            'type': 'object',
            'properties': {'refresh': {'type': 'string'}},
            'required': ['refresh'],
        }},
        responses={
            200: OpenApiResponse(description='Muvaffaqiyatli chiqildi'),
            400: OpenApiResponse(description="Noto'g'ri token"),
        },
        summary='Chiqish (refresh tokenni bekor qilish)',
        tags=['Auth'],
    )
    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': 'refresh maydoni majburiy.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            return Response(
                {'detail': "Token noto'g'ri yoki muddati o'tgan."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        logger.info('Logout: user=%s', request.user.id)
        return Response({'success': True, 'detail': 'Muvaffaqiyatli chiqildi.'})


# ─── Profile ──────────────────────────────────────────────────────────────────

class UserMeView(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/users/me/"""
    permission_classes = [IsAuthenticated]
    serializer_class   = UserProfileSerializer
    http_method_names  = ['get', 'patch']

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class AISettingsView(generics.UpdateAPIView):
    """PATCH /api/users/me/ai-settings/"""
    permission_classes = [IsAuthenticated]
    serializer_class   = AISettingsSerializer
    http_method_names  = ['patch']

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)
