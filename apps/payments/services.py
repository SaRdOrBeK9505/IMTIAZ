"""
PaymentService — to'lov oqimini boshqaradigan yagona entry point.

Provider abstraction:
    - Hozir: StubPaymentProvider (haqiqiy API yo'q)
    - Kelajak: get_provider() funksiyasiga yangi provider qo'shiladi,
      boshqa hech narsa o'zgarmaydi.

To'lov oqimi:
    1. initiate_payment()  → Payment yaratish + provider orqali URL olish
    2. confirm_payment()   → provider'dan holat tekshirish (polling / webhook)
    3. refund_payment()    → to'lovni qaytarish

State machine Payment.transition_to() orqali boshqariladi —
noto'g'ri holatlar exception bilan bloklangan.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from .models import Payment, PaymentLog, PaymentStatus, PaymentProvider
from .providers.base import BasePaymentProvider

logger = logging.getLogger(__name__)


# ─── Provider registry ────────────────────────────────────────────────────────

def get_provider(provider_name: str) -> BasePaymentProvider:
    """
    Provider nomiga qarab implementatsiyani qaytaradi.

    Yangi provider qo'shish:
        1. apps/payments/providers/<name>.py → BasePaymentProvider implement
        2. Shu yerga import va mapping qo'shing
        3. PaymentProvider enum'ga nom qo'shing (models.py)
    """
    from .providers.stub import StubPaymentProvider
    from .providers.alifpay import AlifPayProvider

    # TODO: haqiqiy provayderlar tayyor bo'lganda quyidagilarni yoqing:
    # from .providers.payme import PaymeProvider
    # from .providers.click import ClickProvider
    # from .providers.multicard import MulticardProvider

    registry: dict[str, type[BasePaymentProvider]] = {
        # Hozirda faqat stub — development uchun
        PaymentProvider.PAYME:     StubPaymentProvider,
        PaymentProvider.CLICK:     StubPaymentProvider,
        PaymentProvider.MULTICARD: StubPaymentProvider,
        PaymentProvider.WALLET:    StubPaymentProvider,
        # AlifPay — real implementatsiya tayyor
        PaymentProvider.ALIFPAY:   AlifPayProvider,
    }

    provider_class = registry.get(provider_name)
    if not provider_class:
        raise ValueError(
            f"Noma'lum to'lov provayderi: '{provider_name}'. "
            f"Mavjudlar: {list(registry.keys())}"
        )
    return provider_class()


# ─── Service ──────────────────────────────────────────────────────────────────

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
        """
        Yangi to'lov yaratadi va payment URL qaytaradi.

        Returns:
            {
                payment_id: str,
                status: str,
                payment_url: str | None,
                success: bool,
            }
        """
        # 1. DB yozuvi — faqat bitta faol to'lov
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

        # 2. Provider chaqiruvi
        provider = get_provider(provider_name)
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

        # 3. Natijaga qarab holat o'zgartirish
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
        }

    @staticmethod
    def confirm_payment(payment_id: str) -> dict:
        """
        Provayderdan to'lov holatini tekshiradi.
        Webhook yetib kelmagan yoki polling kerak bo'lganda chaqiriladi.
        """
        try:
            payment = Payment.objects.select_related('booking').get(id=payment_id)
        except Payment.DoesNotExist:
            return {'success': False, 'message': 'To\'lov topilmadi'}

        # Allaqachon yakunlangan
        if payment.status == PaymentStatus.SUCCESS:
            return {'success': True, 'status': payment.status, 'is_paid': True}
        if payment.status in (PaymentStatus.CANCELLED, PaymentStatus.REFUNDED):
            return {'success': True, 'status': payment.status, 'is_paid': False}

        provider = get_provider(payment.provider)
        result = provider.check_status(payment.external_transaction_id or '')

        old_status = payment.status

        if result.is_paid:
            payment.transition_to(PaymentStatus.SUCCESS)
            PaymentService._on_payment_success(payment)
            logger.info('Payment %s muvaffaqiyatli tasdiqlandi', payment_id)

        elif result.is_failed:
            payment.error_message = result.error_message
            payment.save(update_fields=['error_message', 'updated_at'])
            payment.transition_to(PaymentStatus.FAILED)
            logger.warning('Payment %s muvaffaqiyatsiz: %s', payment_id, result.error_message)

        if old_status != payment.status:
            PaymentLog.objects.create(
                payment=payment,
                from_status=old_status,
                to_status=payment.status,
                note='Provayder orqali tasdiqlandi',
                metadata=result.raw or {},
            )

        return {
            'success': True,
            'status': payment.status,
            'is_paid': result.is_paid,
        }

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

        provider = get_provider(payment.provider)
        result = provider.refund(payment.external_transaction_id or '', amount)

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
        """To'lov muvaffaqiyatli bo'lganda booking va xizmat-specific amallar."""
        if not payment.booking:
            return

        from apps.booking.models import BookingStatus, ServiceType
        booking = payment.booking

        if booking.status != BookingStatus.CONFIRMED:
            booking.status = BookingStatus.CONFIRMED
            booking.save(update_fields=['status', 'updated_at'])

        # Parvoz — Bookhara'ga to'lov (GDS ticket)
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
        """Webhook yoki polling orqali to'lovni failed deb belgilash."""
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return
        if payment.status not in (PaymentStatus.PENDING, PaymentStatus.PROCESSING):
            return
        old = payment.status
        if reason:
            payment.error_message = reason
            payment.save(update_fields=['error_message', 'updated_at'])
        payment.transition_to(PaymentStatus.FAILED)
        PaymentLog.objects.create(
            payment=payment,
            from_status=old,
            to_status=PaymentStatus.FAILED,
            note=reason or 'To\'lov muvaffaqiyatsiz',
        )

    @staticmethod
    def process_wallet_payment(
        booking,
        amount: Decimal,
        user,
    ) -> dict:
        """
        IMTIAZ ichki hamyon orqali to'lov.
        Tashqi API talab qilmaydi — balans yetarli bo'lsa darhol tasdiqlaydi.
        """
        if user.balance < amount:
            return {
                'success': False,
                'message': f'Hamyon balansi yetarli emas. '
                           f'Kerak: {amount} UZS, mavjud: {user.balance} UZS',
            }

        # Balansdan yechish
        user.balance -= amount
        user.save(update_fields=['balance', 'updated_at'])

        # WalletTransaction yozuvi
        from apps.users.models import WalletTransaction
        WalletTransaction.objects.create(
            user=user,
            transaction_type=WalletTransaction.TransactionType.PAYMENT,
            amount=-amount,
            balance_after=user.balance,
            description=f'Bron to\'lovi: {booking.title if booking else ""}',
        )

        # Payment yozuvi
        payment = Payment.objects.create(
            booking=booking,
            user=user,
            provider=PaymentProvider.WALLET,
            status=PaymentStatus.SUCCESS,
            amount=amount,
            external_transaction_id=f'wallet-{booking.id if booking else "direct"}',
        )

        # Booking tasdiqlash
        if booking:
            from apps.booking.models import BookingStatus
            booking.status = BookingStatus.CONFIRMED
            booking.save(update_fields=['status', 'updated_at'])
            PaymentService._on_payment_success(payment)

        PaymentLog.objects.create(
            payment=payment,
            from_status='',
            to_status=PaymentStatus.SUCCESS,
            note='Hamyon orqali to\'lov amalga oshirildi',
        )

        return {
            'payment_id': str(payment.id),
            'status': PaymentStatus.SUCCESS,
            'success': True,
        }
