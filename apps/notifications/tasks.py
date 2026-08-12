"""
Notifications Celery tasks.

Tasks:
    send_notification          — bitta bildirishnoma yuborish
    send_booking_reminder      — bron eslatmasi (scheduled)
    process_scheduled_notifications — navbatdagi bildirishnomalar
    retry_failed_subscription_payments — obuna qayta to'lov
    cleanup_old_notifications  — eski bildirishnomalar tozalash
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── Asosiy yuborish ──────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='notifications.send_notification',
)
def send_notification(self, notification_id: str) -> bool:
    """
    Bitta bildirishnomani yuboradi.
    Muvaffaqiyatsiz bo'lsa 3 marta qayta urinadi (1 daqiqa oralig'ida).
    """
    from .models import Notification

    try:
        notif = Notification.objects.select_related('user').get(id=notification_id)
    except Notification.DoesNotExist:
        logger.error('Notification topilmadi: id=%s', notification_id)
        return False

    # Allaqachon yuborilgan
    if notif.status == Notification.Status.SENT:
        return True

    try:
        if notif.channel == Notification.Channel.IN_APP:
            notif.status = Notification.Status.SENT
            notif.sent_at = timezone.now()
            notif.save(update_fields=['status', 'sent_at'])
            logger.info('In-app bildirishnoma: id=%s, user=%s', notif.id, notif.user_id)
            return True

        if notif.channel == Notification.Channel.TELEGRAM:
            success = _send_telegram(notif)
        else:
            logger.warning('Kanal qo\'llab-quvvatlanmaydi: %s', notif.channel)
            success = False

        if success:
            notif.status = Notification.Status.SENT
            notif.sent_at = timezone.now()
            notif.save(update_fields=['status', 'sent_at'])
            logger.info('Bildirishnoma yuborildi: id=%s, user=%s', notif.id, notif.user_id)
        else:
            notif.error_message = 'Yuborish muvaffaqiyatsiz'
            notif.save(update_fields=['error_message'])

        return success

    except Exception as exc:
        logger.exception('Bildirishnoma yuborishda xato: id=%s, error=%s', notification_id, exc)
        notif.error_message = str(exc)
        notif.save(update_fields=['error_message'])
        # Celery retry
        raise self.retry(exc=exc)


def _send_telegram(notif) -> bool:
    """Telegram orqali yuboradi, message_id saqlaydi."""
    if not notif.user.telegram_id:
        logger.warning('User telegram_id yo\'q: user=%s', notif.user_id)
        return False

    from .telegram import get_bot
    bot = get_bot()

    # Bildirishnoma turiga qarab maxsus format
    message_id = None

    if notif.notification_type == 'booking_confirmed' and notif.metadata:
        try:
            from apps.booking.models import Booking
            booking = Booking.objects.get(id=notif.metadata.get('booking_id'))
            message_id = bot.send_booking_confirmation(notif.user.telegram_id, booking)
        except Exception:
            pass

    elif notif.notification_type == 'payment_success' and notif.metadata:
        amount = notif.metadata.get('amount', 0)
        message_id = bot.send_payment_success(notif.user.telegram_id, amount)

    elif notif.notification_type == 'new_lead' and notif.metadata:
        text = f"🔔 <b>{notif.title}</b>\n\n{notif.body}"
        panel = notif.metadata.get('panel', '')
        if panel == 'tour':
            text += "\n\n📋 CRM: Tur arizalar bo'limini oching."
        elif panel == 'restaurant':
            text += "\n\n📋 CRM: Bronlar bo'limini oching."
        message_id = bot.send_message(notif.user.telegram_id, text)

    elif notif.notification_type == 'waitlist_approved' and notif.metadata:
        tier_name = notif.metadata.get('tier_name', 'Standard')
        message_id = bot.send_waitlist_approved(notif.user.telegram_id, tier_name)

    else:
        # Umumiy xabar
        text = f"<b>{notif.title}</b>\n\n{notif.body}"
        message_id = bot.send_message(notif.user.telegram_id, text)

    if message_id:
        notif.telegram_message_id = message_id
        notif.save(update_fields=['telegram_message_id'])

    return message_id is not None


# ─── Bulk va Scheduled ────────────────────────────────────────────────────────

@shared_task(name='notifications.process_scheduled')
def process_scheduled_notifications() -> int:
    """
    Celery Beat: har daqiqada ishga tushadi.
    scheduled_at vaqti kelgan PENDING bildirishnomalarni yuboradi.
    """
    from .models import Notification

    now     = timezone.now()
    pending = Notification.objects.filter(
        status=Notification.Status.PENDING,
        scheduled_at__lte=now,
    ).values_list('id', flat=True)[:100]  # batch 100

    count = 0
    for notif_id in pending:
        send_notification.delay(str(notif_id))
        count += 1

    if count:
        logger.info('Scheduled notifications navbatga qo\'yildi: count=%d', count)
    return count


@shared_task(name='notifications.send_booking_reminders')
def send_booking_reminders() -> int:
    """
    Celery Beat: har soatda ishga tushadi.
    2 soatdan keyin bo'ladigan bronlar uchun eslatma yuboradi.
    """
    from apps.booking.models import Booking, BookingStatus
    from .models import Notification

    now        = timezone.now()
    remind_at  = now + timedelta(hours=2)
    window_end = remind_at + timedelta(minutes=30)

    bookings = Booking.objects.filter(
        status=BookingStatus.CONFIRMED,
        booking_date__gte=remind_at,
        booking_date__lt=window_end,
    ).select_related('user')

    count = 0
    for booking in bookings:
        # Takroriy eslatma oldini olish
        already_sent = Notification.objects.filter(
            notification_type='booking_reminder',
            metadata__booking_id=str(booking.id),
            status=Notification.Status.SENT,
        ).exists()

        if already_sent or not booking.user.telegram_id:
            continue

        notif = Notification.objects.create(
            user=booking.user,
            notification_type='booking_reminder',
            channel=Notification.Channel.TELEGRAM,
            title='Bron eslatmasi',
            body=f"{booking.title} — 2 soatdan so'ng",
            metadata={'booking_id': str(booking.id)},
        )

        from .telegram import get_bot
        bot    = get_bot()
        msg_id = bot.send_booking_reminder(booking.user.telegram_id, booking, hours_before=2)

        if msg_id:
            notif.status              = Notification.Status.SENT
            notif.sent_at             = timezone.now()
            notif.telegram_message_id = msg_id
            notif.save(update_fields=['status', 'sent_at', 'telegram_message_id'])
            count += 1

    if count:
        logger.info('Bron eslatmalari yuborildi: count=%d', count)
    return count


@shared_task(name='notifications.retry_subscriptions')
def retry_failed_subscription_payments() -> int:
    """
    Celery Beat: har kunda ishga tushadi.
    past_due obunalar uchun to'lovni qayta urinadi.
    3 marta urinishdan keyin bekor qilinadi va foydalanuvchiga xabar yuboriladi.
    """
    from apps.membership.models import Subscription

    past_due = Subscription.objects.filter(
        status=Subscription.Status.PAST_DUE,
        retry_count__lt=3,
    ).select_related('user', 'tier')

    count = 0
    for sub in past_due:
        logger.info(
            'Obuna to\'lovi qayta urinilmoqda: sub=%s, retry=%d', sub.id, sub.retry_count
        )

        # TODO: to'lov provayder tayyor bo'lganda
        # PaymentService.initiate_payment(subscription=sub, ...)

        sub.retry_count           += 1
        sub.last_payment_attempt   = timezone.now()
        sub.save(update_fields=['retry_count', 'last_payment_attempt'])

        # 3 marta muvaffaqiyatsiz — cancelled
        if sub.retry_count >= 3:
            sub.status = Subscription.Status.CANCELLED
            sub.save(update_fields=['status'])
            logger.warning('Obuna bekor qilindi (3 marta xato): sub=%s', sub.id)

            if sub.user.telegram_id:
                from .telegram import get_bot
                get_bot().send_message(
                    sub.user.telegram_id,
                    f"⚠️ <b>Obuna bekor qilindi</b>\n\n"
                    f"To'lov 3 marta muvaffaqiyatsiz bo'lgani uchun <b>{sub.tier.name}</b> "
                    f"obunangiz bekor qilindi.\n\n"
                    f"Obunani yangilash uchun ilovaga kiring.",
                )
        count += 1

    return count


@shared_task(name='notifications.cleanup_old')
def cleanup_old_notifications() -> int:
    """
    Celery Beat: haftada bir marta.
    30 kundan eski yuborilgan bildirishnomalarni o'chiradi.
    """
    from .models import Notification

    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = Notification.objects.filter(
        status=Notification.Status.SENT,
        sent_at__lt=cutoff,
    ).delete()

    logger.info('Eski bildirishnomalar tozalandi: count=%d', deleted)
    return deleted


# ─── Yordamchi funksiya ───────────────────────────────────────────────────────

def notify_user(
    user,
    notification_type: str,
    title: str,
    body: str,
    metadata: dict | None = None,
    scheduled_at=None,
) -> None:
    """
    Bildirishnoma yaratib, darhol Celery navbatiga qo'yadi.
    Butun loyiha bo'ylab shu funksiya ishlatiladi.

    Usage:
        from apps.notifications.tasks import notify_user
        notify_user(user, 'booking_confirmed', 'Bron tasdiqlandi', '...', metadata={...})
    """
    from .models import Notification

    notif = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        channel=Notification.Channel.TELEGRAM,
        title=title,
        body=body,
        metadata=metadata or {},
        scheduled_at=scheduled_at,
    )

    if scheduled_at:
        # Kechiktirilgan yuborish — process_scheduled_notifications topadi
        return

    # Darhol yuborish
    send_notification.delay(str(notif.id))
