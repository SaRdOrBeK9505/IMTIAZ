"""
Payments app views.

Endpoint'lar:
    GET  /api/payments/                      — to'lovlar tarixi
    POST /api/payments/initiate/             — AlifPay orqali to'lov boshlash
    POST /api/payments/{id}/confirm/         — to'lov holatini tekshirish (polling)
    POST /api/payments/webhook/{provider}/   — provayder callback
"""

from __future__ import annotations

import logging
from decimal import Decimal

from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import HasApprovedMembership
from .models import Payment
from .services import PaymentService
from .serializers import PaymentSerializer, PaymentInitiateSerializer

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
    """POST /api/payments/initiate/ — AlifPay orqali to'lov boshlash"""
    permission_classes = [IsAuthenticated, HasApprovedMembership]

    @extend_schema(
        request=PaymentInitiateSerializer,
        responses={
            200: OpenApiResponse(description='Payment URL va ID'),
            404: OpenApiResponse(description='Bron topilmadi'),
        },
        summary='To\'lov boshlash (AlifPay)',
        description='Mijozni AlifPay checkout sahifasiga yo\'naltiradi.',
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
            return_url=(
                serializer.validated_data.get('return_url')
                or request.META.get('HTTP_ORIGIN')
            ),
            cancel_url=serializer.validated_data.get('cancel_url'),
            description=booking.title,
        )
        if not result.get('success', True) and result.get('message'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class PaymentConfirmView(APIView):
    """POST /api/payments/{payment_id}/confirm/ — holatni provayderdan tekshirish (polling)"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description='Joriy to\'lov holati')},
        summary='To\'lovni tasdiqlash (polling)',
        tags=['Payments'],
    )
    def post(self, request, payment_id):
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
        description='AlifPay: HMAC-SHA256 imzo tekshiriladi.',
        tags=['Payments'],
    )
    def post(self, request, provider: str):
        logger.info('Webhook [%s] qabul qilindi', provider)

        if provider == 'alifpay':
            return self._handle_alifpay(request)

        logger.warning('Webhook: noma\'lum provayder "%s"', provider)
        return Response({'status': 'unknown_provider'})

    def _handle_alifpay(self, request) -> Response:
        """
        AlifPay webhook:
        1. HMAC-SHA256 imzo (ALIFPAY_SECRET_KEY majburiy — DEBUG'dan mustaqil)
        2. top-level id (invoice ID) → Payment.external_transaction_id
        3. payment.status dan to'g'ridan-to'g'ri holat yangilash (qayta API chaqiruvsiz)
        """
        from django.conf import settings
        from apps.payments.providers.alifpay import verify_alifpay_signature, extract_receipt_url
        from .services import PaymentService

        received_sig = (
            request.META.get('HTTP_SIGNATURE')
            or request.META.get('HTTP_X_ALIFPAY_SIGNATURE', '')
        )
        secret_key = getattr(settings, 'ALIFPAY_SECRET_KEY', '')

        if not secret_key:
            logger.error('AlifPay webhook: ALIFPAY_SECRET_KEY o\'rnatilmagan')
            return Response({'status': 'misconfigured'}, status=500)

        if not verify_alifpay_signature(
            body=request.body,
            secret_key=secret_key,
            received=received_sig,
        ):
            logger.warning('AlifPay webhook: noto\'g\'ri imzo. received=%s', received_sig[:16])
            return Response({'status': 'forbidden'}, status=403)

        data = request.data
        invoice_id = data.get('id')
        payment_data = data.get('payment') or {}
        pay_status = payment_data.get('status', '')

        logger.info(
            'AlifPay webhook: invoice_id=%s, status=%s',
            invoice_id, pay_status,
        )

        if not invoice_id:
            logger.warning('AlifPay webhook: invoice id topilmadi. payload=%s', data)
            return Response({'status': 'ok'})

        receipt_url = extract_receipt_url(payment_data)

        webhook_amount = None
        raw_amount = payment_data.get('amount')
        if raw_amount is not None:
            webhook_amount = Decimal(str(raw_amount)) / 100

        try:
            PaymentService.apply_webhook_status(
                str(invoice_id),
                pay_status,
                webhook_amount=webhook_amount,
                receipt_url=receipt_url,
                raw=data if isinstance(data, dict) else None,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                'AlifPay webhook: holat yangilashda xato. invoice_id=%s', invoice_id,
            )

        return Response({'status': 'ok'})
