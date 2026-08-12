"""
Payment Celery tasklari — settlement saga retry va depozit monitoring.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name='payments.retry_settlement_refund',
    bind=True,
    max_retries=5,
    default_retry_delay=120,
)
def retry_settlement_refund(self, settlement_id: str) -> dict:
    """REFUND_PENDING holatidagi settlement uchun qaytarishni qayta urinish."""
    from apps.booking.models import BookingSettlement
    from apps.booking.settlement import SettlementStatus
    from apps.payments.settlement_service import FlightSettlementService

    try:
        settlement = BookingSettlement.objects.select_related(
            'booking', 'payment',
        ).get(pk=settlement_id)
    except BookingSettlement.DoesNotExist:
        logger.warning('Settlement topilmadi: %s', settlement_id)
        return {'status': 'not_found'}

    if settlement.status != SettlementStatus.REFUND_PENDING:
        return {'status': 'skipped', 'current': settlement.status}

    if not settlement.payment_id:
        logger.error('Settlement payment yo\'q: %s', settlement_id)
        return {'status': 'no_payment'}

    FlightSettlementService._attempt_refund(
        settlement.booking,
        settlement.payment,
        settlement,
    )

    settlement.refresh_from_db()
    if settlement.status == SettlementStatus.REFUND_PENDING:
        raise self.retry(exc=Exception('Refund hali REFUND_PENDING'))

    return {'status': settlement.status}


@shared_task(
    name='payments.retry_bookhara_settlement',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def retry_bookhara_settlement(self, settlement_id: str) -> dict:
    """BOOKHARA_FAILED holatida settlement qayta urinish (manual/admin trigger)."""
    from apps.booking.models import BookingSettlement
    from apps.booking.settlement import SettlementStatus
    from apps.payments.settlement_service import FlightSettlementService

    try:
        settlement = BookingSettlement.objects.select_related(
            'booking', 'payment',
        ).get(pk=settlement_id)
    except BookingSettlement.DoesNotExist:
        return {'status': 'not_found'}

    if settlement.status not in (
        SettlementStatus.BOOKHARA_FAILED,
        SettlementStatus.PAYMENT_CAPTURED,
    ):
        return {'status': 'skipped', 'current': settlement.status}

    if not settlement.payment_id:
        return {'status': 'no_payment'}

    ok = FlightSettlementService.settle_with_bookhara(
        settlement.booking,
        settlement.payment,
    )
    settlement.refresh_from_db()
    if not ok and settlement.status == SettlementStatus.BOOKHARA_FAILED:
        raise self.retry(exc=Exception('Settlement hali muvaffaqiyatsiz'))

    return {'status': settlement.status, 'ok': ok}


@shared_task(name='payments.check_bookhara_deposit')
def check_bookhara_deposit() -> dict:
    """Periodic: Bookhara depozit balansini tekshirish."""
    from apps.payments.settlement_service import FlightSettlementService
    return FlightSettlementService.check_deposit_health()


@shared_task(name='payments.process_pending_refunds')
def process_pending_refunds() -> dict:
    """Periodic: barcha REFUND_PENDING settlementlarni qayta ishlash."""
    from apps.payments.settlement_service import FlightSettlementService
    count = FlightSettlementService.retry_pending_refunds()
    return {'processed': count}
