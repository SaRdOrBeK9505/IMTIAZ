"""
QR Codes — Celery async tasks.
    calculate_qr_analytics — kunlik 01:00
    expire_qr_codes        — har 1 soat
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='qr_codes.calculate_daily_analytics', bind=True, max_retries=3)
def calculate_qr_analytics(self):
    """Kechagi sana uchun barcha QR kodlar analitikasini hisoblaydi."""
    try:
        from .services import QRAnalyticsService
        count = QRAnalyticsService.calculate_daily_analytics()
        logger.info('[qr_codes] Analytics calculated: %d records', count)
        return {'records': count}
    except Exception as exc:
        logger.error('[qr_codes] calculate_qr_analytics xato: %s', exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='qr_codes.expire_codes', bind=True)
def expire_qr_codes(self):
    """Muddati o'tgan QR kodlarni is_active=False qiladi."""
    from .models import QRCode
    from django.utils import timezone

    expired = QRCode.objects.filter(
        is_active=True,
        valid_until__lt=timezone.now(),
    ).update(is_active=False)

    logger.info('[qr_codes] Expired %d QR codes', expired)
    return {'expired': expired}
