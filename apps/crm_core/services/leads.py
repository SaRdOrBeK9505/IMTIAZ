"""Lead pipeline — yaratish va booking bilan sinxronlash."""

from __future__ import annotations

from django.utils import timezone

from apps.crm_core.models import Lead


def _customer_fields(booking) -> tuple[str, str]:
    user = booking.user
    return user.full_name or '', user.phone or ''


def create_lead_from_restaurant_booking(booking, restaurant_booking) -> Lead | None:
    branch = restaurant_booking.branch
    if not branch:
        return None

    customer_name, customer_phone = _customer_fields(booking)
    title = f'Restoran bron — {branch.name}'
    metadata = {
        'booking_id': str(booking.id),
        'branch_id': str(branch.id),
        'branch_name': branch.name,
        'reservation_at': restaurant_booking.reservation_at.isoformat(),
        'guest_count': restaurant_booking.guest_count,
        'table_number': restaurant_booking.table_number or '',
    }

    lead, _ = Lead.objects.get_or_create(
        booking=booking,
        defaults={
            'organization': branch.organization,
            'branch': branch,
            'vertical': Lead.Vertical.RESTAURANT,
            'title': title,
            'customer_name': customer_name,
            'customer_phone': customer_phone,
            'metadata': metadata,
        },
    )
    return lead


def create_lead_from_tour_booking(booking, tour_booking) -> Lead | None:
    organization = tour_booking.package.organization
    customer_name, customer_phone = _customer_fields(booking)
    title = f'Tur arizasi — {tour_booking.package.title}'
    metadata = {
        'booking_id': str(booking.id),
        'tour_booking_id': str(tour_booking.id),
        'package_id': str(tour_booking.package_id),
        'package_title': tour_booking.package.title,
        'tourist_count': tour_booking.tourist_count,
        'departure_date': str(tour_booking.availability.departure_date),
        'final_price': str(booking.final_price),
        'currency': booking.currency,
    }

    lead, _ = Lead.objects.get_or_create(
        booking=booking,
        defaults={
            'organization': organization,
            'vertical': Lead.Vertical.TRAVEL,
            'title': title,
            'customer_name': customer_name,
            'customer_phone': customer_phone,
            'metadata': metadata,
        },
    )
    return lead


def sync_lead_stage_for_booking(booking, stage: str) -> None:
    """Bron holati o'zgarganda lead bosqichini yangilaydi."""
    if stage not in Lead.Stage.values:
        return

    closed_at = timezone.now() if stage in (Lead.Stage.WON, Lead.Stage.LOST) else None
    Lead.objects.filter(booking=booking).update(
        stage=stage,
        closed_at=closed_at,
        updated_at=timezone.now(),
    )


def sync_lead_stage_from_booking_status(booking) -> None:
    """Booking.status dan lead stage ga mapping."""
    from apps.booking.models import BookingStatus

    mapping = {
        BookingStatus.PENDING: Lead.Stage.NEW,
        BookingStatus.IN_PROGRESS: Lead.Stage.CONTACTED,
        BookingStatus.CONFIRMED: Lead.Stage.WON,
        BookingStatus.COMPLETED: Lead.Stage.WON,
        BookingStatus.CANCELLED: Lead.Stage.LOST,
    }
    stage = mapping.get(booking.status)
    if stage:
        sync_lead_stage_for_booking(booking, stage)
