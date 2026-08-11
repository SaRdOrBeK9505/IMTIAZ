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
            'AlifPay (production) yoki stub provayderlar orqali to\'lov boshlash. '
            'AlifPay: checkout sahifasiga yo\'naltiradi.'
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
            'AlifPay: HMAC-SHA256 imzo tekshiriladi.'
        ),
        tags=['Payments'],
    )
    def post(self, request, provider: str):
        logger.info('Webhook [%s] qabul qilindi', provider)

        if provider == 'alifpay':
            return self._handle_alifpay(request)

        # Boshqa provayderlar uchun kelajakda shu yerga qo'shiladi
        logger.warning('Webhook: noma\'lum provayder "%s"', provider)
        return Response({'status': 'unknown_provider'})

    def _handle_alifpay(self, request) -> Response:
        """
        AlifPay webhook:
        1. HMAC-SHA256(request.body, ALIFPAY_SECRET_KEY) → Base64 → imzo tekshiruvi
        2. payment.meta.order_id orqali Payment topish
        3. SUCCEEDED bo'lsa — Payment va Booking yangilash
        4. receipt_url ni FlightPayment'ga saqlash
        5. Har doim 200 OK qaytar
        """
        from django.conf import settings
        from apps.payments.providers.alifpay import verify_alifpay_signature
        from .models import Payment, PaymentStatus
        from .services import PaymentService

        # ── Imzo tekshiruvi (AlifPay docs: HTTP header "Signature") ─────
        received_sig = (
            request.META.get('HTTP_SIGNATURE')
            or request.META.get('HTTP_X_ALIFPAY_SIGNATURE', '')
        )
        secret_key   = getattr(settings, 'ALIFPAY_SECRET_KEY', '')

        if not secret_key and not settings.DEBUG:
            logger.error('AlifPay webhook: ALIFPAY_SECRET_KEY o\'rnatilmagan (production)')
            return Response({'status': 'misconfigured'}, status=500)

        if secret_key and not verify_alifpay_signature(
            body=request.body,
            secret_key=secret_key,
            received=received_sig,
        ):
            logger.warning('AlifPay webhook: noto\'g\'ri imzo. received=%s', received_sig[:16])
            return Response({'status': 'forbidden'}, status=403)

        # ── Payload parse ───────────────────────────────────────────────
        data     = request.data
        payment_data = data.get('payment') or {}
        meta         = payment_data.get('meta') or {}
        order_id     = meta.get('order_id') or data.get('order_id')
        pay_status   = payment_data.get('status', '')

        logger.info(
            'AlifPay webhook: order_id=%s, status=%s',
            order_id, pay_status,
        )

        if not order_id:
            logger.warning('AlifPay webhook: order_id topilmadi. payload=%s', data)
            return Response({'status': 'ok'})

        # ── Payment topish va yangilash ───────────────────────────────
        try:
            payment = Payment.objects.select_related('booking').get(id=order_id)
        except Payment.DoesNotExist:
            logger.warning('AlifPay webhook: Payment topilmadi. order_id=%s', order_id)
            return Response({'status': 'ok'})
        except Exception:  # noqa: BLE001
            logger.exception('AlifPay webhook: Payment qidirishda xato. order_id=%s', order_id)
            return Response({'status': 'ok'})

        if pay_status == 'SUCCEEDED' and payment.status != PaymentStatus.SUCCESS:
            try:
                PaymentService.confirm_payment(str(payment.id))
            except Exception:  # noqa: BLE001
                logger.exception(
                    'AlifPay webhook: confirm_payment xatosi. payment_id=%s', payment.id,
                )
        elif pay_status in ('FAILED', 'CANCELLED', 'EXPIRED'):
            PaymentService.mark_payment_failed(
                str(payment.id),
                reason=f'AlifPay status: {pay_status}',
            )

        # ── Receipt URL ni FlightPayment'ga saqlash ───────────────────────
        receipt_url = None
        results = (payment_data.get('receipt') or {}).get('results', [])
        if results and isinstance(results, list):
            receipt_url = results[0].get('url')

        if receipt_url and payment.booking:
            try:
                from apps.booking.models import FlightBooking
                fb = FlightBooking.objects.filter(
                    booking=payment.booking
                ).first()
                if fb and not fb.provider_response:
                    fb.provider_response = {}
                if fb:
                    fb.provider_response = {**(fb.provider_response or {}), 'receipt_url': receipt_url}
                    fb.save(update_fields=['provider_response', 'updated_at'])
                    logger.info(
                        'AlifPay receipt_url saqlandi: booking=%s, url=%s',
                        payment.booking_id, receipt_url,
                    )
                # FlightPayment modeliga ham saqlash
                from apps.booking.models import FlightPayment
                fp = FlightPayment.objects.filter(flight_booking=fb).first() if fb else None
                if fp and not fp.receipt_url:
                    fp.receipt_url = receipt_url
                    fp.save(update_fields=['receipt_url'])
            except Exception:  # noqa: BLE001
                logger.exception(
                    'AlifPay webhook: receipt_url saqlashda xato. payment_id=%s', payment.id,
                )

        return Response({'status': 'ok'})
