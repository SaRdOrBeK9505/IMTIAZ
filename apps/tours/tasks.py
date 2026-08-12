"""
Tours app — Celery async tasks.

Jadval (celery beat):
    expire_tour_availabilities  — har 1 soat
    update_all_package_stats    — har 6 soat
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='tours.expire_past_availabilities', bind=True, max_retries=3)
def expire_past_availabilities(self):
    """O'tib ketgan jo'nash sanalarini CLOSED qiladi."""
    try:
        from .services import TourAvailabilityService
        count = TourAvailabilityService.expire_past_dates()
        logger.info('[tours] Expired %d availabilities', count)
        return {'expired': count}
    except Exception as exc:
        logger.error('[tours] expire_past_availabilities xato: %s', exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='tours.update_package_stats', bind=True, max_retries=3)
def update_package_stats_task(package_id: str):
    """Paket reyting va bron statistikasini yangilaydi."""
    try:
        from .services import TourAvailabilityService
        TourAvailabilityService.update_package_stats(package_id)
        return {'package_id': package_id, 'status': 'updated'}
    except Exception as exc:
        logger.error('[tours] update_package_stats xato: %s', exc)
        raise


@shared_task(name='tours.update_all_package_stats', bind=True)
def update_all_package_stats(self):
    """Barcha aktiv paketlar statistikasini yangilaydi."""
    from .models import TourPackage
    from .services import TourAvailabilityService
    ids = TourPackage.objects.filter(is_active=True).values_list('id', flat=True)
    updated = 0
    for pkg_id in ids:
        try:
            TourAvailabilityService.update_package_stats(str(pkg_id))
            updated += 1
        except Exception as e:
            logger.error('[tours] Paket %s stats xato: %s', pkg_id, e)
    return {'updated': updated}


@shared_task(name='tours.send_voucher_notification')
def send_voucher_notification(voucher_id: str) -> dict:
    """Voaucher yaratilganda mijozga xabar yuboradi."""
    try:
        from .models import TourVoucher
        from apps.notifications.models import Notification
        from apps.notifications.tasks import notify_user

        voucher = TourVoucher.objects.select_related(
            'tour_booking__booking__user',
            'tour_booking__package',
            'tour_booking__availability',
        ).get(id=voucher_id)

        tb = voucher.tour_booking
        user = tb.booking.user
        body = (
            f'Sizning {tb.package.title} turiga voaucher tayyor.\n'
            f'Raqam: {voucher.voucher_number}\n'
            f"Jo'nash: {voucher.valid_from.strftime('%d.%m.%Y')}"
        )

        notify_user(
            user,
            Notification.NotificationType.GENERAL,
            'Voauchingiz tayyor! 🎉',
            body,
            metadata={
                'type': 'tour_voucher',
                'voucher_id': str(voucher.id),
                'voucher_number': voucher.voucher_number,
                'booking_id': str(tb.booking_id),
            },
        )
        logger.info(
            '[tours] Voucher notification sent: %s → user %s',
            voucher.voucher_number, user.id,
        )
        return {'status': 'sent', 'voucher_id': str(voucher.id)}
    except Exception as exc:
        logger.error('[tours] send_voucher_notification xato: %s', exc)
        return {'status': 'error', 'message': str(exc)}
