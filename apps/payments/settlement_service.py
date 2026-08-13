"""
FlightSettlementService — Bookhara settlement saga orchestrator.

Pre-flight (to'lovdan OLDIN):
    - Bookhara konfiguratsiya
    - external_booking_id mavjudligi
    - payment permission
    - narx o'zgarmaganligi
    - depozit balansi yetarli

Post-payment (mijoz to'lagach):
    - Bookhara pay_booking (idempotent)
    - Muvaffaqiyat → booking CONFIRMED
    - Xato → hold cancel + avtomatik refund (Celery retry)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.booking.models import (
    Booking,
    BookingSettlement,
    BookingStatus,
    BookingTransactionLog,
    FlightBooking,
    FlightPayment,
    ServiceType,
)
from apps.booking.settlement import SettlementStatus, TransactionStep
from apps.integrations.adapters.bookhara import (
    BookharaAdapter,
    BookharaError,
    BookharaPriceChangedError,
    PaymentNotAllowedError,
)
from apps.integrations.errors import IntegrationError, is_bookhara_configured

logger = logging.getLogger(__name__)


@dataclass
class PreflightResult:
    ok: bool
    error_code: str = ''
    message: str = ''
    locked_price: Decimal | None = None
    deposit: Decimal | None = None


class FlightSettlementService:
    """Parvoz bronlari uchun settlement saga."""

    # ─── Public API ───────────────────────────────────────────────────────

    @classmethod
    def requires_settlement(cls, booking: Booking) -> bool:
        return booking.service_type == ServiceType.FLIGHT

    @classmethod
    def run_preflight(cls, booking: Booking) -> PreflightResult:
        """
        To'lov boshlashdan OLDIN barcha shartlarni tekshiradi.
        Muvaffaqiyatli bo'lsa settlement yaratiladi/yangilanadi → PRICE_LOCKED.
        """
        if not cls.requires_settlement(booking):
            return PreflightResult(ok=True)

        settlement = cls._get_or_create_settlement(booking)
        cls._log_step(
            settlement,
            TransactionStep.PRE_FLIGHT_START,
            success=True,
            message='Pre-flight tekshiruv boshlandi',
        )

        result = cls._execute_preflight_checks(booking)

        if not result.ok:
            cls._fail_preflight(settlement, result)
            return result

        with transaction.atomic():
            settlement = BookingSettlement.objects.select_for_update().get(pk=settlement.pk)
            settlement.locked_price = result.locked_price
            settlement.bookhara_deposit_at_preflight = result.deposit
            settlement.last_error_code = ''
            settlement.last_error_message = ''
            old = settlement.status
            if settlement.status == SettlementStatus.PENDING:
                settlement.transition_to(SettlementStatus.PRICE_LOCKED)
            cls._log_step(
                settlement,
                TransactionStep.PRE_FLIGHT_OK,
                from_status=old,
                to_status=settlement.status,
                success=True,
                message=f'Narx qulflandi: {result.locked_price} UZS',
                provider_response={
                    'deposit': str(result.deposit),
                    'locked_price': str(result.locked_price),
                },
            )

        return result

    @classmethod
    def on_payment_captured(cls, booking: Booking, payment) -> None:
        """
        Mijoz to'lovi qabul qilindi — Bookhara settlement boshlanadi.
        Booking hali CONFIRMED emas (faqat settlement COMPLETED dan keyin).
        """
        if not cls.requires_settlement(booking):
            cls._confirm_non_flight(booking)
            return

        settlement = cls._get_or_create_settlement(booking)

        with transaction.atomic():
            settlement = BookingSettlement.objects.select_for_update().get(pk=settlement.pk)
            settlement.payment = payment
            old = settlement.status

            if settlement.status in (
                SettlementStatus.PRICE_LOCKED,
                SettlementStatus.PENDING,
            ):
                settlement.transition_to(SettlementStatus.PAYMENT_CAPTURED)

            booking.status = BookingStatus.IN_PROGRESS
            booking.save(update_fields=['status', 'updated_at'])

            cls._log_step(
                settlement,
                TransactionStep.PAYMENT_CAPTURED,
                from_status=old,
                to_status=settlement.status,
                success=True,
                message=f'Payment {payment.id} qabul qilindi',
            )

        cls.settle_with_bookhara(booking, payment)

    @classmethod
    def settle_with_bookhara(cls, booking: Booking, payment) -> bool:
        """
        Bookhara pay_booking — idempotent.
        True = muvaffaqiyat, False = xato (kompensatsiya ishga tushiriladi).
        """
        settlement = BookingSettlement.objects.get(booking=booking)

        with transaction.atomic():
            settlement = BookingSettlement.objects.select_for_update().get(pk=settlement.pk)

            if settlement.status == SettlementStatus.COMPLETED:
                logger.info('Settlement allaqachon completed: booking=%s', booking.id)
                return True

            if settlement.status == SettlementStatus.BOOKHARA_CONFIRMED:
                cls._finalize_completed(settlement, booking)
                return True

            old = settlement.status
            if settlement.status in (
                SettlementStatus.PRICE_LOCKED,
                SettlementStatus.PAYMENT_CAPTURED,
                SettlementStatus.BOOKHARA_FAILED,
            ):
                if settlement.status == SettlementStatus.PRICE_LOCKED:
                    settlement.transition_to(SettlementStatus.PAYMENT_CAPTURED)
                settlement.transition_to(SettlementStatus.BOOKHARA_SETTLING)
                settlement.retry_count += 1
                settlement.save(update_fields=['retry_count', 'updated_at'])

            cls._log_step(
                settlement,
                TransactionStep.BOOKHARA_SETTLE_START,
                from_status=old,
                to_status=settlement.status,
                success=True,
                message=f'idempotency_key={settlement.idempotency_key}',
            )

        try:
            pay_result = cls._call_bookhara_pay(booking)
        except Exception as exc:
            cls._handle_settlement_failure(booking, payment, exc)
            return False

        cls._handle_settlement_success(booking, payment, pay_result)
        return True

    @classmethod
    def compensate(cls, booking: Booking, payment, reason: str = '') -> None:
        """Bookhara xato — hold bekor qilish + refund."""
        settlement = booking.settlement

        with transaction.atomic():
            settlement = BookingSettlement.objects.select_for_update().get(pk=settlement.pk)
            if settlement.status in (SettlementStatus.REFUNDED, SettlementStatus.COMPLETED):
                return
            old = settlement.status
            if settlement.status != SettlementStatus.REFUND_PENDING:
                if settlement.status != SettlementStatus.BOOKHARA_FAILED:
                    settlement.transition_to(SettlementStatus.BOOKHARA_FAILED)
                settlement.last_error_message = reason or settlement.last_error_message
                settlement.transition_to(SettlementStatus.REFUND_PENDING)

            cls._log_step(
                settlement,
                TransactionStep.REFUND_START,
                from_status=old,
                to_status=settlement.status,
                success=True,
                message=reason or 'Kompensatsiya boshlandi',
            )

        cls._cancel_bookhara_hold(booking, settlement)
        cls._attempt_refund(booking, payment, settlement)

    @classmethod
    def retry_pending_refunds(cls) -> int:
        """Celery: REFUND_PENDING holatidagi settlementlarni qayta urinish."""
        pending = BookingSettlement.objects.filter(
            status=SettlementStatus.REFUND_PENDING,
        ).select_related('booking', 'payment')[:50]

        count = 0
        for settlement in pending:
            if settlement.payment_id:
                cls._attempt_refund(settlement.booking, settlement.payment, settlement)
                count += 1
        return count

    @classmethod
    def check_deposit_health(cls) -> dict:
        """Celery: depozit balansini monitoring qilish."""
        if not is_bookhara_configured():
            return {'ok': False, 'reason': 'not_configured'}

        adapter = BookharaAdapter()
        try:
            balance = adapter.check_balance()
        except Exception as exc:
            logger.exception('Bookhara deposit check xato')
            return {'ok': False, 'reason': str(exc)}

        deposit = Decimal(str(balance.get('deposit') or 0))
        min_required = Decimal(str(getattr(settings, 'BOOKHARA_MIN_DEPOSIT', 0)))

        if deposit < min_required:
            logger.critical(
                'Bookhara depozit past! deposit=%s min=%s',
                deposit, min_required,
            )
            return {
                'ok': False,
                'deposit': deposit,
                'min_required': min_required,
                'reason': 'insufficient_deposit',
            }

        return {'ok': True, 'deposit': deposit, 'credit': balance.get('credit')}

    # ─── Pre-flight ichki ─────────────────────────────────────────────────

    @classmethod
    def _execute_preflight_checks(cls, booking: Booking) -> PreflightResult:
        if not is_bookhara_configured():
            return PreflightResult(
                ok=False,
                error_code='not_configured',
                message='Bookhara integratsiyasi sozlanmagan.',
            )

        if not booking.external_booking_id:
            return PreflightResult(
                ok=False,
                error_code='no_hold',
                message='Bookhara hold (external_booking_id) mavjud emas.',
            )

        if booking.external_provider and booking.external_provider != 'bookhara':
            return PreflightResult(
                ok=False,
                error_code='wrong_provider',
                message=f'Noto\'g\'ri provayder: {booking.external_provider}',
            )

        adapter = BookharaAdapter()

        try:
            if not adapter.check_payment_permission(booking.external_booking_id):
                return PreflightResult(
                    ok=False,
                    error_code='payment_not_allowed',
                    message='Bookhara: ushbu bron uchun to\'lovga ruxsat yo\'q.',
                )

            price_check = adapter.check_price(booking.external_booking_id)
            if price_check.get('is_price_changed'):
                # Bookhara check-price javobida yangi narx qaytmaydi —
                # yangilangan narxni olish uchun bron ma'lumotini qayta
                # so'rash kerak (update-avia-booking.md).
                new_price = None
                try:
                    booking_data = adapter.get_booking(booking.external_booking_id)
                    price_block = (booking_data.get('price') or {})
                    amount = price_block.get('amount')
                    if amount is not None:
                        new_price = Decimal(str(amount))
                except (BookharaError, IntegrationError) as exc:
                    logger.warning('Yangilangan narxni olib bolmadi: %s', exc)
                return PreflightResult(
                    ok=False,
                    error_code='price_changed',
                    message='Narx o\'zgargan. Qayta qidiring.',
                    locked_price=new_price,
                )

            locked_price = booking.final_price

            balance = adapter.check_balance()
            deposit = Decimal(str(balance.get('deposit') or 0))
            buffer_amount = Decimal(str(getattr(settings, 'BOOKHARA_DEPOSIT_BUFFER', 0)))
            required = locked_price + buffer_amount

            if deposit < required:
                return PreflightResult(
                    ok=False,
                    error_code='insufficient_deposit',
                    message=(
                        f'Bookhara depoziti yetarli emas. '
                        f'Kerak: {required} UZS, mavjud: {deposit} UZS.'
                    ),
                    locked_price=locked_price,
                    deposit=deposit,
                )

            return PreflightResult(
                ok=True,
                locked_price=locked_price,
                deposit=deposit,
            )

        except BookharaPriceChangedError as exc:
            return PreflightResult(
                ok=False,
                error_code='price_changed',
                message=str(exc),
                locked_price=exc.new_price,
            )
        except PaymentNotAllowedError as exc:
            return PreflightResult(
                ok=False,
                error_code='payment_not_allowed',
                message=str(exc),
            )
        except (BookharaError, IntegrationError) as exc:
            return PreflightResult(
                ok=False,
                error_code='bookhara_error',
                message=str(getattr(exc, 'user_message', None) or exc),
            )
        except Exception as exc:
            logger.exception('Pre-flight kutilmagan xato: booking=%s', booking.id)
            return PreflightResult(
                ok=False,
                error_code='preflight_error',
                message='Tizim vaqtincha xizmat ko\'rsata olmaydi.',
            )

    @classmethod
    def _fail_preflight(cls, settlement: BookingSettlement, result: PreflightResult) -> None:
        with transaction.atomic():
            settlement = BookingSettlement.objects.select_for_update().get(pk=settlement.pk)
            settlement.last_error_code = result.error_code
            settlement.last_error_message = result.message
            settlement.save(update_fields=[
                'last_error_code', 'last_error_message', 'updated_at',
            ])
            if settlement.status == SettlementStatus.PENDING:
                settlement.transition_to(SettlementStatus.FAILED)

            cls._log_step(
                settlement,
                TransactionStep.PRE_FLIGHT_FAILED,
                success=False,
                message=result.message,
                error_code=result.error_code,
                provider_response={
                    'locked_price': str(result.locked_price) if result.locked_price else None,
                    'deposit': str(result.deposit) if result.deposit else None,
                },
            )

    # ─── Settlement ichki ─────────────────────────────────────────────────

    @classmethod
    def _call_bookhara_pay(cls, booking: Booking) -> dict:
        adapter = BookharaAdapter()
        return adapter.pay_booking(booking.external_booking_id)

    @classmethod
    def _handle_settlement_success(cls, booking: Booking, payment, pay_result: dict) -> None:
        settlement = booking.settlement
        fb = FlightBooking.objects.filter(booking=booking).first()

        fiscal = pay_result.get('fiscalization_v2') or {}
        receipt_url = (payment.provider_response or {}).get('_receipt_url', '')

        with transaction.atomic():
            settlement = BookingSettlement.objects.select_for_update().get(pk=settlement.pk)
            old = settlement.status
            settlement.transition_to(SettlementStatus.BOOKHARA_CONFIRMED)
            settlement.last_error_code = ''
            settlement.last_error_message = ''
            settlement.save(update_fields=['last_error_code', 'last_error_message', 'updated_at'])

            cls._log_step(
                settlement,
                TransactionStep.BOOKHARA_SETTLE_OK,
                from_status=old,
                to_status=settlement.status,
                success=True,
                message='Bookhara pay_booking muvaffaqiyatli',
                provider_response=pay_result,
            )

            if fb:
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

            cls._finalize_completed(settlement, booking)

    @classmethod
    def _finalize_completed(cls, settlement: BookingSettlement, booking: Booking) -> None:
        with transaction.atomic():
            settlement = BookingSettlement.objects.select_for_update().get(pk=settlement.pk)
            if settlement.status == SettlementStatus.COMPLETED:
                return
            old = settlement.status
            settlement.transition_to(SettlementStatus.COMPLETED)
            settlement.completed_at = timezone.now()
            settlement.save(update_fields=['completed_at', 'updated_at'])

            booking.status = BookingStatus.CONFIRMED
            booking.save(update_fields=['status', 'updated_at'])

            cls._log_step(
                settlement,
                TransactionStep.BOOKHARA_SETTLE_OK,
                from_status=old,
                to_status=SettlementStatus.COMPLETED,
                success=True,
                message='Settlement yakunlandi, booking confirmed',
            )
        logger.info('Flight settlement completed: booking=%s', booking.id)

    @classmethod
    def _handle_settlement_failure(cls, booking: Booking, payment, exc: Exception) -> None:
        error_code = getattr(exc, 'error_code', None) or type(exc).__name__
        message = str(getattr(exc, 'user_message', None) or exc)

        settlement = booking.settlement
        with transaction.atomic():
            settlement = BookingSettlement.objects.select_for_update().get(pk=settlement.pk)
            old = settlement.status
            if settlement.status == SettlementStatus.BOOKHARA_SETTLING:
                settlement.transition_to(SettlementStatus.BOOKHARA_FAILED)
            settlement.last_error_code = str(error_code)
            settlement.last_error_message = message
            settlement.save(update_fields=[
                'last_error_code', 'last_error_message', 'updated_at',
            ])

            cls._log_step(
                settlement,
                TransactionStep.BOOKHARA_SETTLE_FAILED,
                from_status=old,
                to_status=settlement.status,
                success=False,
                message=message,
                error_code=str(error_code),
            )

        logger.error(
            'Bookhara settlement failed: booking=%s error=%s',
            booking.id, message,
        )

        cls.compensate(booking, payment, reason=message)

    @classmethod
    def _cancel_bookhara_hold(cls, booking: Booking, settlement: BookingSettlement) -> None:
        if not booking.external_booking_id:
            return
        try:
            adapter = BookharaAdapter()
            result = adapter.cancel_booking(booking.external_booking_id)
            cls._log_step(
                settlement,
                TransactionStep.BOOKHARA_CANCEL_HOLD,
                success=result.success,
                message=result.error_message or 'Hold bekor qilindi',
                provider_response=result.raw,
            )
        except Exception as exc:
            logger.warning(
                'Bookhara hold cancel xato: booking=%s %s', booking.id, exc,
            )
            cls._log_step(
                settlement,
                TransactionStep.BOOKHARA_CANCEL_HOLD,
                success=False,
                message=str(exc),
            )

    @classmethod
    def _attempt_refund(cls, booking: Booking, payment, settlement: BookingSettlement) -> None:
        from apps.payments.services import PaymentService

        settlement.refund_attempts += 1
        settlement.save(update_fields=['refund_attempts', 'updated_at'])

        result = PaymentService.refund_payment(
            str(payment.id),
            reason=f'Bookhara settlement xato: {settlement.last_error_message}',
        )

        with transaction.atomic():
            settlement = BookingSettlement.objects.select_for_update().get(pk=settlement.pk)

            if result.get('success'):
                old = settlement.status
                settlement.transition_to(SettlementStatus.REFUNDED)
                booking.status = BookingStatus.REFUNDED
                booking.save(update_fields=['status', 'updated_at'])

                cls._log_step(
                    settlement,
                    TransactionStep.REFUND_OK,
                    from_status=old,
                    to_status=settlement.status,
                    success=True,
                    message='Mijozga pul qaytarildi',
                )
                logger.info('Refund completed: booking=%s payment=%s', booking.id, payment.id)
            else:
                cls._log_step(
                    settlement,
                    TransactionStep.REFUND_FAILED,
                    success=False,
                    message=result.get('message', 'Refund xato'),
                    error_code='refund_failed',
                )
                logger.error(
                    'Refund failed: booking=%s payment=%s msg=%s',
                    booking.id, payment.id, result.get('message'),
                )
                cls._enqueue_refund_retry(settlement.pk)

    # ─── Yordamchi ────────────────────────────────────────────────────────

    @classmethod
    def _get_or_create_settlement(cls, booking: Booking) -> BookingSettlement:
        settlement, created = BookingSettlement.objects.get_or_create(
            booking=booking,
            defaults={'idempotency_key': cls._make_idempotency_key(booking)},
        )
        if created:
            logger.info('Settlement yaratildi: booking=%s', booking.id)
        return settlement

    @staticmethod
    def _make_idempotency_key(booking: Booking) -> str:
        return f'imtiaz-settle-{booking.id}-{uuid.uuid4().hex[:12]}'

    @staticmethod
    def _confirm_non_flight(booking: Booking) -> None:
        if booking.status != BookingStatus.CONFIRMED:
            booking.status = BookingStatus.CONFIRMED
            booking.save(update_fields=['status', 'updated_at'])

    @staticmethod
    def _log_step(
        settlement: BookingSettlement,
        step: str,
        *,
        from_status: str = '',
        to_status: str = '',
        success: bool = True,
        message: str = '',
        error_code: str = '',
        provider_response: dict | None = None,
    ) -> None:
        BookingTransactionLog.objects.create(
            settlement=settlement,
            step=step,
            from_status=from_status,
            to_status=to_status,
            success=success,
            message=message,
            error_code=error_code,
            provider_response=provider_response,
        )

    @staticmethod
    def _enqueue_refund_retry(settlement_id) -> None:
        try:
            from apps.payments.tasks import retry_settlement_refund
            retry_settlement_refund.apply_async(
                args=[str(settlement_id)],
                countdown=60,
            )
        except Exception:
            logger.exception(
                'Refund retry task yuborib bo\'lmadi: settlement=%s', settlement_id,
            )