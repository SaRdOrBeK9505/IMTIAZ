"""
PaymentService — to'lov oqimini boshqaradigan yagona entry point.

Parvoz (Bookhara) oqimi — saga pattern:
    1. initiate_payment()  → pre-flight tekshiruv → PRICE_LOCKED → AlifPay invoice
    2. confirm/webhook     → PAYMENT_CAPTURED → Bookhara settlement
    3. Muvaffaqiyat        → COMPLETED → booking CONFIRMED
    4. Bookhara xato       → hold cancel + avtomatik refund (Celery retry)

Boshqa xizmatlar: to'lovdan keyin darhol CONFIRMED.

State machine Payment.transition_to() orqali boshqariladi.
Tashqi HTTP (AlifPay, Bookhara) DB qulfi ochiq holda chaqirilmaydi.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

from .models import Payment, PaymentLog, PaymentStatus, PaymentProvider

logger = logging.getLogger(__name__)

_ACTIVE_PROVIDER = PaymentProvider.ALIFPAY


def get_provider(provider_name: str):
    """Hozir faqat AlifPay qo'llab-quvvatlanadi."""
    if provider_name != _ACTIVE_PROVIDER:
        raise ValueError(
            f"To'lov provayderi '{provider_name}' qo'llab-quvvatlanmaydi. "
            f"Faqat '{_ACTIVE_PROVIDER}' mavjud."
        )
    from .providers.alifpay import AlifPayProvider
    return AlifPayProvider()


class PaymentService:
    """To'lov yaratish, tasdiqlash va qaytarish."""

    @staticmethod
    def initiate_payment(
        booking,
        provider_name: str,
        amount: Decimal,
        user,
        description: str = '',
        return_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict:
        """Yangi to'lov yaratadi va AlifPay checkout URL qaytaradi."""
        if provider_name != _ACTIVE_PROVIDER:
            return {
                'success': False,
                'message': f"Faqat {_ACTIVE_PROVIDER} provayderi orqali to'lov mumkin.",
            }

        from apps.booking.models import BookingStatus
        if booking.status not in (BookingStatus.PENDING, BookingStatus.IN_PROGRESS):
            return {
                'success': False,
                'message': f'Bu bron uchun to\'lov qabul qilinmaydi. Holat: {booking.status}',
            }

        from apps.payments.settlement_service import FlightSettlementService
        if FlightSettlementService.requires_settlement(booking):
            preflight = FlightSettlementService.run_preflight(booking)
            if not preflight.ok:
                return {
                    'success': False,
                    'message': preflight.message,
                    'error_code': preflight.error_code,
                }

        active = Payment.objects.filter(
            booking=booking,
            status__in=[PaymentStatus.PENDING, PaymentStatus.PROCESSING],
        ).exists()
        if active:
            return {
                'success': False,
                'message': 'Bu bron uchun allaqachon faol to\'lov mavjud.',
            }

        payment = Payment.objects.create(
            booking=booking,
            user=user,
            provider=provider_name,
            status=PaymentStatus.PENDING,
            amount=amount,
        )
        PaymentLog.objects.create(
            payment=payment,
            from_status='',
            to_status=PaymentStatus.PENDING,
            note='To\'lov sessiyasi yaratildi',
        )

        try:
            provider = get_provider(provider_name)
        except ValueError as exc:
            payment.error_message = str(exc)
            payment.transition_to(PaymentStatus.FAILED)
            return {'success': False, 'message': str(exc)}

        intent = provider.create_payment(
            order_id=str(payment.id),
            amount=amount,
            description=description or f'IMTIAZ #{payment.id}',
            return_url=return_url,
            extra={
                'phone':      getattr(user, 'phone', ''),
                'cancel_url': cancel_url or return_url,
            },
        )

        if intent.success:
            payment.external_transaction_id = intent.external_transaction_id
            payment.provider_response = intent.raw or {}
            payment.transition_to(PaymentStatus.PROCESSING)
            log_note = f'Provayder sessiyasi ochildi: {intent.external_transaction_id}'
        else:
            payment.error_message = intent.error_message
            payment.transition_to(PaymentStatus.FAILED)
            log_note = f'Provayder xatosi: {intent.error_message}'
            logger.error('Payment %s yaratishda xato: %s', payment.id, intent.error_message)

        PaymentLog.objects.create(
            payment=payment,
            from_status=PaymentStatus.PENDING,
            to_status=payment.status,
            note=log_note,
        )

        return {
            'payment_id': str(payment.id),
            'status': payment.status,
            'payment_url': intent.payment_url,
            'success': intent.success,
            'message': intent.error_message if not intent.success else '',
        }

    @staticmethod
    def confirm_payment(payment_id: str) -> dict:
        """
        Polling: provayderdan to'lov holatini tekshiradi.
        AlifPay HTTP qulfdan tashqarida — faqat DB yangilanishi qulf ichida.
        """
        with transaction.atomic():
            try:
                payment = (
                    Payment.objects
                    .select_for_update()
                    .select_related('booking')
                    .get(id=payment_id)
                )
            except Payment.DoesNotExist:
                return {'success': False, 'message': 'To\'lov topilmadi'}

            if payment.status == PaymentStatus.SUCCESS:
                return {'success': True, 'status': payment.status, 'is_paid': True}
            if payment.status in (PaymentStatus.CANCELLED, PaymentStatus.REFUNDED):
                return {'success': True, 'status': payment.status, 'is_paid': False}
            if payment.status not in (PaymentStatus.PENDING, PaymentStatus.PROCESSING):
                return {'success': True, 'status': payment.status, 'is_paid': False}

            ext_id = payment.external_transaction_id or ''
            provider_name = payment.provider

        try:
            provider = get_provider(provider_name)
        except ValueError as exc:
            return {'success': False, 'message': str(exc)}

        result = provider.check_status(ext_id)

        settle_id: str | None = None
        final_status: str
        is_paid: bool

        with transaction.atomic():
            payment = (
                Payment.objects
                .select_for_update()
                .select_related('booking')
                .get(id=payment_id)
            )

            if payment.status == PaymentStatus.SUCCESS:
                return {'success': True, 'status': payment.status, 'is_paid': True}
            if payment.status not in (PaymentStatus.PENDING, PaymentStatus.PROCESSING):
                return {
                    'success': True,
                    'status': payment.status,
                    'is_paid': False,
                }

            if result.is_paid:
                if PaymentService._mark_success_locked(
                    payment,
                    receipt_url=(result.raw or {}).get('_receipt_url'),
                    log_note='Polling orqali tasdiqlandi',
                    metadata=result.raw,
                ):
                    settle_id = str(payment.id)
                    logger.info('Payment %s polling orqali tasdiqlandi', payment_id)
            elif result.is_failed:
                PaymentService._mark_failed_locked(
                    payment,
                    reason=result.error_message or 'To\'lov muvaffaqiyatsiz',
                    log_note='Polling orqali rad etildi',
                    metadata=result.raw,
                )
                logger.warning(
                    'Payment %s polling muvaffaqiyatsiz: %s',
                    payment_id, result.error_message,
                )

            final_status = payment.status
            is_paid = payment.status == PaymentStatus.SUCCESS

        if settle_id:
            payment = Payment.objects.select_related('booking').get(id=settle_id)
            PaymentService._on_payment_success(payment)

        return {'success': True, 'status': final_status, 'is_paid': is_paid}

    @staticmethod
    def apply_webhook_status(
        invoice_id: str,
        pay_status: str,
        *,
        webhook_amount: Decimal | None = None,
        receipt_url: str | None = None,
        raw: dict | None = None,
    ) -> None:
        """
        AlifPay webhook payload'dan to'g'ridan-to'g'ri holat yangilash.
        Bookhara settlement qulfdan keyin alohida chaqiriladi.
        """
        settle_id: str | None = None

        with transaction.atomic():
            try:
                payment = (
                    Payment.objects
                    .select_for_update()
                    .select_related('booking')
                    .get(external_transaction_id=invoice_id)
                )
            except Payment.DoesNotExist:
                logger.warning(
                    'AlifPay webhook: Payment topilmadi. invoice_id=%s', invoice_id,
                )
                return

            if payment.status == PaymentStatus.SUCCESS:
                return

            if pay_status == 'SUCCEEDED':
                if webhook_amount is not None and webhook_amount != payment.amount:
                    logger.error(
                        'AlifPay webhook: summa nomuvofiqlik. payment=%s '
                        'kutilgan=%s kelgan=%s invoice_id=%s',
                        payment.id, payment.amount, webhook_amount, invoice_id,
                    )
                    return

                if PaymentService._mark_success_locked(
                    payment,
                    receipt_url=receipt_url,
                    log_note='AlifPay webhook orqali tasdiqlandi',
                    metadata=raw,
                ):
                    settle_id = str(payment.id)

            elif pay_status in ('FAILED', 'CANCELLED', 'EXPIRED'):
                PaymentService._mark_failed_locked(
                    payment,
                    reason=f'AlifPay status: {pay_status}',
                    log_note='AlifPay webhook orqali rad etildi',
                    metadata=raw,
                )

        if settle_id:
            payment = Payment.objects.select_related('booking').get(id=settle_id)
            PaymentService._on_payment_success(payment)

    @staticmethod
    def _mark_success_locked(
        payment: Payment,
        *,
        receipt_url: str | None,
        log_note: str,
        metadata: dict | None = None,
    ) -> bool:
        """
        DB holatini SUCCESS ga o'tkazadi (qulf ichida).
        Tashqi HTTP chaqirilmaydi. True — yangi o'tish bo'ldi.
        """
        if payment.status == PaymentStatus.SUCCESS:
            return False

        old_status = payment.status
        if receipt_url:
            payment.provider_response = {
                **(payment.provider_response or {}),
                '_receipt_url': receipt_url,
            }
            payment.save(update_fields=['provider_response', 'updated_at'])

        payment.transition_to(PaymentStatus.SUCCESS)

        PaymentLog.objects.create(
            payment=payment,
            from_status=old_status,
            to_status=PaymentStatus.SUCCESS,
            note=log_note,
            metadata=metadata,
        )
        return True

    @staticmethod
    def _mark_failed_locked(
        payment: Payment,
        *,
        reason: str,
        log_note: str,
        metadata: dict | None = None,
    ) -> None:
        if payment.status not in (PaymentStatus.PENDING, PaymentStatus.PROCESSING):
            return

        old_status = payment.status
        payment.error_message = reason
        payment.save(update_fields=['error_message', 'updated_at'])
        payment.transition_to(PaymentStatus.FAILED)

        PaymentLog.objects.create(
            payment=payment,
            from_status=old_status,
            to_status=PaymentStatus.FAILED,
            note=log_note,
            metadata=metadata,
        )

    @staticmethod
    def refund_payment(
        payment_id: str,
        amount: Decimal | None = None,
        reason: str = '',
    ) -> dict:
        """To'lovni qaytaradi — to'liq yoki qisman."""
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return {'success': False, 'message': 'To\'lov topilmadi'}

        if payment.status != PaymentStatus.SUCCESS:
            return {
                'success': False,
                'message': f'Faqat muvaffaqiyatli to\'lovni qaytarish mumkin. '
                           f'Joriy holat: {payment.status}',
            }

        if payment.provider != _ACTIVE_PROVIDER:
            msg = (
                f"Bu to'lov provayderi ({payment.provider!r}) endi qo'llab-quvvatlanmaydi. "
                f"Faqat {_ACTIVE_PROVIDER} orqali qaytarish mumkin."
            )
            logger.error('Payment %s refund rad etildi: %s', payment_id, msg)
            return {'success': False, 'message': msg}

        try:
            provider = get_provider(payment.provider)
        except ValueError as exc:
            logger.error('Payment %s refund: %s', payment_id, exc)
            return {'success': False, 'message': str(exc)}

        try:
            result = provider.refund(payment.external_transaction_id or '', amount)
        except NotImplementedError as exc:
            logger.warning('Payment %s qisman qaytarish rad etildi: %s', payment_id, exc)
            return {'success': False, 'message': str(exc)}

        if result.success:
            refund_amount = amount or payment.amount
            payment.refunded_amount = refund_amount
            payment.refund_reason = reason
            payment.save(update_fields=['refunded_amount', 'refund_reason', 'updated_at'])

            new_status = (
                PaymentStatus.PARTIALLY_REFUNDED
                if amount and amount < payment.amount
                else PaymentStatus.REFUNDED
            )
            old_status = payment.status
            payment.transition_to(new_status)

            PaymentLog.objects.create(
                payment=payment,
                from_status=old_status,
                to_status=new_status,
                note=f'Qaytarildi: {refund_amount} UZS. Sabab: {reason}',
            )
            logger.info('Payment %s qaytarildi: %s UZS', payment_id, refund_amount)
        else:
            logger.error('Payment %s qaytarishda xato: %s', payment_id, result.error_message)

        return {
            'success': result.success,
            'message': result.error_message,
        }

    @staticmethod
    def _on_payment_success(payment: Payment) -> None:
        """
        To'lov muvaffaqiyatli — booking settlement saga (qulfsiz).

        Parvoz: booking CONFIRMED faqat Bookhara settlement COMPLETED dan keyin.
        Boshqa xizmatlar: darhol CONFIRMED.
        """
        if not payment.booking:
            return

        from apps.payments.settlement_service import FlightSettlementService

        FlightSettlementService.on_payment_captured(payment.booking, payment)

    @staticmethod
    def _settle_flight_booking(booking, payment: Payment) -> None:
        """Deprecated — FlightSettlementService ga o'tkazildi."""
        from apps.payments.settlement_service import FlightSettlementService
        FlightSettlementService.settle_with_bookhara(booking, payment)

    @staticmethod
    def mark_payment_failed(payment_id: str, reason: str = '') -> None:
        """Polling orqali to'lovni failed deb belgilash."""
        with transaction.atomic():
            try:
                payment = Payment.objects.select_for_update().get(id=payment_id)
            except Payment.DoesNotExist:
                return
            PaymentService._mark_failed_locked(
                payment,
                reason=reason or 'To\'lov muvaffaqiyatsiz',
                log_note=reason or 'To\'lov muvaffaqiyatsiz',
            )
