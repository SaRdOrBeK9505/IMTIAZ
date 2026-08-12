"""
CRM bildirishnomalar — yangi lead/bron tushganda owner va xodimlarga xabar.

Kanallar:
    - in_app  — CRM web panel (darhol SENT)
    - telegram — agar user.telegram_id bo'lsa
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from apps.booking.models import Booking
    from apps.crm.models import Organization

logger = logging.getLogger(__name__)


def get_organization_crm_recipients(organization: Organization) -> list:
    """Tashkilot owneri + faol filial xodimlari."""
    from apps.crm.models import BranchStaff
    from apps.users.models import User, UserRole

    seen: set = set()
    recipients: list = []

    owner = organization.owner
    if owner and owner.is_active:
        recipients.append(owner)
        seen.add(owner.pk)

    staff_qs = (
        BranchStaff.objects.filter(
            branch__organization=organization,
            is_active=True,
            user__is_active=True,
            user__role__in=(UserRole.RESTAURANT_STAFF, UserRole.TOUR_STAFF),
        )
        .select_related('user')
    )
    for profile in staff_qs:
        if profile.user_id not in seen:
            recipients.append(profile.user)
            seen.add(profile.user_id)

    return recipients


def _create_crm_notification(
    user,
    *,
    notification_type: str,
    title: str,
    body: str,
    metadata: dict,
    channel: str,
) -> None:
    from apps.notifications.models import Notification
    from apps.notifications.tasks import send_notification

    notif = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        channel=channel,
        title=title,
        body=body,
        metadata=metadata,
    )

    if channel == Notification.Channel.IN_APP:
        from django.utils import timezone
        notif.status = Notification.Status.SENT
        notif.sent_at = timezone.now()
        notif.save(update_fields=['status', 'sent_at'])
    else:
        send_notification.delay(str(notif.id))


def notify_crm_users(
    organization: Organization,
    *,
    notification_type: str,
    title: str,
    body: str,
    metadata: dict | None = None,
) -> int:
    """
    Tashkilot CRM foydalanuvchilariga bildirishnoma yuboradi.
    Returns: xabar olgan userlar soni.
    """
    from apps.notifications.models import Notification

    if not organization or not organization.is_active:
        return 0

    meta = metadata or {}
    meta['organization_id'] = str(organization.id)
    recipients = get_organization_crm_recipients(organization)

    if not recipients:
        logger.warning(
            'CRM notification: recipient yo\'q. org=%s type=%s',
            organization.id, notification_type,
        )
        return 0

    count = 0
    for user in recipients:
        _create_crm_notification(
            user,
            notification_type=notification_type,
            title=title,
            body=body,
            metadata=meta,
            channel=Notification.Channel.IN_APP,
        )
        count += 1

        if user.telegram_id:
            _create_crm_notification(
                user,
                notification_type=notification_type,
                title=title,
                body=body,
                metadata=meta,
                channel=Notification.Channel.TELEGRAM,
            )

    logger.info(
        'CRM notification yuborildi: org=%s type=%s recipients=%d',
        organization.id, notification_type, count,
    )
    return count


def notify_new_tour_lead(booking: Booking, tour_booking) -> int:
    """Mijoz tur bron qilganda — tur kompaniyasi CRM ga lead."""
    from apps.notifications.models import Notification

    organization = tour_booking.package.organization
    customer_name = booking.user.full_name or booking.user.phone
    meta = {
        'panel': 'tour',
        'booking_id': str(booking.id),
        'tour_booking_id': str(tour_booking.id),
        'package_id': str(tour_booking.package_id),
        'package_title': tour_booking.package.title,
        'tourist_count': tour_booking.tourist_count,
        'departure_date': str(tour_booking.availability.departure_date),
        'customer_name': customer_name,
        'customer_phone': booking.user.phone,
        'final_price': str(booking.final_price),
        'currency': booking.currency,
    }

    title = f'Yangi tur arizasi — {tour_booking.package.title}'
    body = (
        f'Mijoz: {customer_name}\n'
        f'Sana: {tour_booking.availability.departure_date}\n'
        f'Sayohatchilar: {tour_booking.tourist_count}\n'
        f'Summa: {booking.final_price:,.0f} {booking.currency}'
    )

    count = notify_crm_users(
        organization,
        notification_type=Notification.NotificationType.NEW_LEAD,
        title=title,
        body=body,
        metadata=meta,
    )
    _ensure_tour_lead(booking, tour_booking)
    return count


def notify_new_restaurant_lead(booking: Booking, restaurant_booking) -> int:
    """Mijoz restoran bron qilganda — restoran CRM ga lead."""
    from apps.notifications.models import Notification

    branch = restaurant_booking.branch
    if not branch:
        logger.warning(
            'Restoran lead notification: branch yo\'q. booking=%s', booking.id,
        )
        return 0

    organization = branch.organization
    customer_name = booking.user.full_name or booking.user.phone
    meta = {
        'panel': 'restaurant',
        'booking_id': str(booking.id),
        'branch_id': str(branch.id),
        'branch_name': branch.name,
        'reservation_at': restaurant_booking.reservation_at.isoformat(),
        'guest_count': restaurant_booking.guest_count,
        'customer_name': customer_name,
        'customer_phone': booking.user.phone,
    }

    title = f'Yangi restoran bron — {branch.name}'
    body = (
        f'Mijoz: {customer_name}\n'
        f'Vaqt: {restaurant_booking.reservation_at.strftime("%d.%m.%Y %H:%M")}\n'
        f'Mehmonlar: {restaurant_booking.guest_count}'
    )
    if restaurant_booking.special_requests:
        body += f'\nIzoh: {restaurant_booking.special_requests[:200]}'

    count = notify_crm_users(
        organization,
        notification_type=Notification.NotificationType.NEW_LEAD,
        title=title,
        body=body,
        metadata=meta,
    )
    _ensure_restaurant_lead(booking, restaurant_booking)
    return count


def notify_customer_booking_confirmed(booking: Booking, *, message: str = '') -> None:
    """Mijozga bron tasdiqlangan xabari."""
    from apps.notifications.models import Notification
    from apps.notifications.tasks import notify_user

    body = message or f'{booking.title} — broningiz tasdiqlandi.'
    notify_user(
        booking.user,
        Notification.NotificationType.BOOKING_CONFIRMED,
        'Bron tasdiqlandi ✅',
        body,
        metadata={'booking_id': str(booking.id), 'service_type': booking.service_type},
    )


def notify_customer_booking_rejected(
    booking: Booking,
    *,
    reason: str = '',
) -> None:
    """Mijozga bron rad etilgan xabari."""
    from apps.notifications.models import Notification
    from apps.notifications.tasks import notify_user

    body = f'{booking.title} — arizangiz rad etildi.'
    if reason:
        body += f'\nSabab: {reason}'

    notify_user(
        booking.user,
        Notification.NotificationType.BOOKING_CANCELLED,
        'Bron rad etildi',
        body,
        metadata={
            'booking_id': str(booking.id),
            'service_type': booking.service_type,
            'reason': reason,
        },
    )


def schedule_lead_notification(callback) -> None:
    """DB commit dan keyin notification yuborish (transaction.on_commit)."""
    transaction.on_commit(callback)


def _ensure_tour_lead(booking, tour_booking) -> None:
    from apps.crm_core.services.leads import create_lead_from_tour_booking

    create_lead_from_tour_booking(booking, tour_booking)


def _ensure_restaurant_lead(booking, restaurant_booking) -> None:
    from apps.crm_core.services.leads import create_lead_from_restaurant_booking

    create_lead_from_restaurant_booking(booking, restaurant_booking)
