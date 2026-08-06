"""
Payments app views.

Endpoint'lar:
    GET  /api/payments/                      — to'lovlar tarixi
    POST /api/payments/initiate/             — tashqi provayder orqali to'lov
    POST /api/payments/wallet/               — hamyon orqali to'lov
    POST /api/payments/{id}/confirm/         — to'lov holatini tekshirish (polling)
    POST /api/payments/webhook/{provider}/   — provayder callback
"""

from __future__ import annotations

import logging

from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import HasApprovedMembership
from .models import Payment
from .services import PaymentService
from .serializers import (
    PaymentSerializer,
    PaymentInitiateSerializer,
    WalletPaymentSerializer,
)

logger = logging.getLogger(__name__)


class PaymentListView(generics.ListAPIView):
    """GET /api/payments/ — foydalanuvchining to'lovlar tarixi"""
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentSerializer
    queryset = Payment.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Payment.objects.none()
        return (
            Payment.objects
            .filter(user=self.request.user)
            .prefetch_related('logs')
            .order_by('-created_at')
        )


class PaymentInitiateView(APIView):
    """POST /api/payments/initiate/ — tashqi provayder orqali to'lov boshlash"""
    permission_classes = [IsAuthenticated, HasApprovedMembership]

    @extend_schema(
        request=PaymentInitiateSerializer,
        responses={
            200: OpenApiResponse(description='Payment URL va ID'),
            404: OpenApiResponse(description='Bron topilmadi'),
        },
        summary='To\'lov boshlash (tashqi provayder)',
        description=(
            'Hozir barcha provayderlar stub rejimida ishlaydi — '
            'haqiqiy provayder tanlanganida avtomatik ulangan bo\'ladi.'
        ),
        tags=['Payments'],
    )
    def post(self, request):
        serializer = PaymentInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.booking.models import Booking
        try:
            booking = Booking.objects.get(
                id=serializer.validated_data['booking_id'],
                user=request.user,
            )
        except Booking.DoesNotExist:
            return Response(
                {'message': 'Bron topilmadi'},
                status=status.HTTP_404_NOT_FOUND,
            )

        result = PaymentService.initiate_payment(
            booking=booking,
            provider_name=serializer.validated_data['provider'],
            amount=booking.final_price,
            user=request.user,
            return_url=request.META.get('HTTP_ORIGIN'),
        )
        return Response(result)


class WalletPaymentView(APIView):
    """POST /api/payments/wallet/ — IMTIAZ hamyon orqali to'lov"""
    permission_classes = [IsAuthenticated, HasApprovedMembership]

    @extend_schema(
        request=WalletPaymentSerializer,
        responses={
            200: OpenApiResponse(description='To\'lov muvaffaqiyatli'),
            400: OpenApiResponse(description='Balans yetarli emas'),
            404: OpenApiResponse(description='Bron topilmadi'),
        },
        summary='Hamyon orqali to\'lov',
        tags=['Payments'],
    )
    def post(self, request):
        serializer = WalletPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.booking.models import Booking
        try:
            booking = Booking.objects.get(
                id=serializer.validated_data['booking_id'],
                user=request.user,
            )
        except Booking.DoesNotExist:
            return Response(
                {'message': 'Bron topilmadi'},
                status=status.HTTP_404_NOT_FOUND,
            )

        result = PaymentService.process_wallet_payment(
            booking=booking,
            amount=booking.final_price,
            user=request.user,
        )

        http_status = (
            status.HTTP_200_OK if result['success']
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=http_status)


class PaymentConfirmView(APIView):
    """POST /api/payments/{payment_id}/confirm/ — holatni provayderd tekshirish"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description='Joriy to\'lov holati')},
        summary='To\'lovni tasdiqlash (polling)',
        tags=['Payments'],
    )
    def post(self, request, payment_id):
        # Faqat o'z to'lovini tekshira oladi
        if not Payment.objects.filter(id=payment_id, user=request.user).exists():
            return Response(
                {'message': 'To\'lov topilmadi'},
                status=status.HTTP_404_NOT_FOUND,
            )
        result = PaymentService.confirm_payment(str(payment_id))
        return Response(result)


class PaymentWebhookView(APIView):
    """
    POST /api/payments/webhook/{provider}/
    Provayder callback — AllowAny (signature ichki tekshiriladi).
    """
    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description='OK')},
        summary='Provayder webhook callback',
        description=(
            'Har bir provayder o\'zining signature tekshiruvi bilan qo\'shiladi. '
            'Hozir faqat log qiladi.'
        ),
        tags=['Payments'],
    )
    def post(self, request, provider: str):
        logger.info(
            'Webhook [%s]: %s',
            provider,
            request.data,
        )
        # TODO: provider'ga qarab signature tekshiruvi + PaymentService.confirm_payment()
        return Response({'status': 'received'})
