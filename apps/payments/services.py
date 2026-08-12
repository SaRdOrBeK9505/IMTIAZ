"""
PaymentService — to'lov oqimini boshqaradigan yagona entry point.

To'lov oqimi:
    1. initiate_payment()  → Payment yaratish + AlifPay orqali checkout URL
    2. confirm_payment()   → polling (webhook yetmagan holatda)
    3. apply_webhook_status() → webhook payload'dan to'g'ridan-to'g'ri holat yangilash
    4. refund_payment()    → to'lovni qaytarish

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
        """To'lov muvaffaqiyatli — booking va Bookhara settlement (qulfsiz)."""
        if not payment.booking:
            return

        from apps.booking.models import BookingStatus, ServiceType
        booking = payment.booking

        if booking.status != BookingStatus.CONFIRMED:
            booking.status = BookingStatus.CONFIRMED
            booking.save(update_fields=['status', 'updated_at'])

        if booking.service_type == ServiceType.FLIGHT:
            PaymentService._settle_flight_booking(booking, payment)

    @staticmethod
    def _settle_flight_booking(booking, payment: Payment) -> None:
        """Mijoz to'lagach Bookhara orqali chipta rasmiylashtirish."""
        try:
            from apps.booking.models import FlightBooking, FlightPayment
            fb = FlightBooking.objects.filter(booking=booking).first()
            if not fb or not booking.external_booking_id:
                logger.warning(
                    'Flight booking settle: external_booking_id yo\'q. booking=%s', booking.id,
                )
                return

            from apps.integrations.adapters.bookhara import BookharaAdapter
            adapter = BookharaAdapter()
            pay_result = adapter.pay_booking(booking.external_booking_id)

            fiscal = pay_result.get('fiscalization_v2') or {}
            receipt_url = (payment.provider_response or {}).get('_receipt_url', '')

            FlightPayment.objects.update_or_create(
                flight_booking=fb,
                defaults={
                    'amount':             fiscal.get('amount', payment.amount),
                    'total_amount':       fiscal.get('total_amount', payment.amount),
                    'receipt_url':        receipt_url,
                    'ikpu_provider_1':    fiscal.get('ikpu_provider_1', ''),
                    'package_code_prov1': fiscal.get('package_code_prov1', ''),
                    'id_provider_1':      fiscal.get('id_provider_1', ''),
                    'nds_provider_1':     fiscal.get('nds_provider_1', 0),
                    'ikpu_bookhara':      fiscal.get('ikpu_bookhara', ''),
                    'package_code_bkh':   fiscal.get('package_code_bkh', ''),
                    'service_fee_bkh':    fiscal.get('service_fee_bkh', 0),
                    'nds_bookhara':       fiscal.get('nds_bookhara', 0),
                    'profit':             fiscal.get('profit', 0),
                    'discount':           fiscal.get('discount', 0),
                },
            )
            fb.provider_response = pay_result
            fb.provider_status = pay_result.get('status', 'ticketed')
            fb.save(update_fields=['provider_response', 'provider_status', 'updated_at'])
            logger.info('Flight booking settled via Bookhara: booking=%s', booking.id)
        except Exception:
            logger.exception('Flight booking settle xato: booking=%s', booking.id)

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
