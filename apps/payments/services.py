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
        # 1. DB yozuvi
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
            # Booking ham tasdiqlansin
            if payment.booking:
                from apps.booking.models import BookingStatus
                payment.booking.status = BookingStatus.CONFIRMED
                payment.booking.save(update_fields=['status', 'updated_at'])
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
