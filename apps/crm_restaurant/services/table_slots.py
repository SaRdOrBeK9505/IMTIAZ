"""Stol vaqt slotlari — generatsiya, band qilish, bo'shatish."""

from __future__ import annotations

from datetime import date, datetime, timedelta, time
from typing import Iterator

from django.db import transaction
from django.utils.dateparse import parse_date

from apps.crm.models import Branch, RestaurantTable, TableTimeSlot

WEEKDAY_KEYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
DEFAULT_OPEN = time(9, 0)
DEFAULT_CLOSE = time(22, 0)
DEFAULT_SLOT_MINUTES = 30


def _parse_hhmm(value: str) -> time:
    value = value.strip()
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValueError(f'Noto\'g\'ri vaqt formati: {value}')


def get_branch_hours_for_date(branch: Branch, target_date: date) -> tuple[time, time] | None:
    """Filial ish vaqtini qaytaradi; yopiq kun bo'lsa None."""
    hours = branch.working_hours or {}
    if not hours:
        return DEFAULT_OPEN, DEFAULT_CLOSE

    key = WEEKDAY_KEYS[target_date.weekday()]
    raw = hours.get(key) or hours.get(key.capitalize()) or hours.get(str(target_date.weekday()))
    if raw is None:
        return DEFAULT_OPEN, DEFAULT_CLOSE
    if isinstance(raw, str) and raw.strip().lower() in ('closed', 'off', ''):
        return None
    if isinstance(raw, dict):
        return _parse_hhmm(raw['open']), _parse_hhmm(raw['close'])

    parts = str(raw).split('-', 1)
    if len(parts) != 2:
        return DEFAULT_OPEN, DEFAULT_CLOSE
    return _parse_hhmm(parts[0]), _parse_hhmm(parts[1])


def iter_slot_times(
    open_time: time,
    close_time: time,
    slot_minutes: int,
) -> Iterator[tuple[time, time]]:
    current = datetime.combine(date.min, open_time)
    end = datetime.combine(date.min, close_time)
    step = timedelta(minutes=slot_minutes)
    while current + step <= end:
        slot_end = current + step
        yield current.time(), slot_end.time()
        current = slot_end


def generate_slots_for_table(
    table: RestaurantTable,
    target_date: date,
    *,
    slot_minutes: int = DEFAULT_SLOT_MINUTES,
) -> int:
    """Bitta stol uchun kunlik slotlar yaratadi (mavjud slotlarni o'zgartirmaydi)."""
    window = get_branch_hours_for_date(table.branch, target_date)
    if not window:
        return 0

    open_time, close_time = window
    created = 0
    for start, end in iter_slot_times(open_time, close_time, slot_minutes):
        _, was_created = TableTimeSlot.objects.get_or_create(
            table=table,
            date=target_date,
            start_time=start,
            end_time=end,
            defaults={'is_available': True},
        )
        if was_created:
            created += 1
    return created


def generate_slots_for_branch(
    branch: Branch,
    start_date: date,
    end_date: date | None = None,
    *,
    slot_minutes: int = DEFAULT_SLOT_MINUTES,
) -> dict:
    """Filialdagi barcha faol stollar uchun slotlar generatsiya qiladi."""
    end_date = end_date or start_date
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    tables = RestaurantTable.objects.filter(branch=branch, is_active=True)
    total_created = 0
    days = (end_date - start_date).days + 1

    for offset in range(days):
        target = start_date + timedelta(days=offset)
        for table in tables:
            total_created += generate_slots_for_table(
                table, target, slot_minutes=slot_minutes,
            )

    return {
        'branch_id': str(branch.id),
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'tables_count': tables.count(),
        'slots_created': total_created,
        'slot_minutes': slot_minutes,
    }


def ensure_slots_for_table(table: RestaurantTable, target_date: date, **kwargs) -> None:
    if not table.time_slots.filter(date=target_date).exists():
        generate_slots_for_table(table, target_date, **kwargs)


def ensure_slots_for_branch(branch: Branch, target_date: date, **kwargs) -> None:
    for table in RestaurantTable.objects.filter(branch=branch, is_active=True):
        ensure_slots_for_table(table, target_date, **kwargs)


def _booking_window(restaurant_booking) -> tuple[date, time, time] | None:
    reservation_at = restaurant_booking.reservation_at
    if not reservation_at:
        return None
    duration = restaurant_booking.duration_minutes or 120
    start = reservation_at
    end_dt = start + timedelta(minutes=duration)
    return start.date(), start.time(), end_dt.time()


def _resolve_table(restaurant_booking, table: RestaurantTable | None = None) -> RestaurantTable | None:
    if table:
        return table
    if not restaurant_booking.branch:
        return None
    if restaurant_booking.table_number:
        return RestaurantTable.objects.filter(
            branch=restaurant_booking.branch,
            table_number=restaurant_booking.table_number,
            is_active=True,
        ).first()
    return None


@transaction.atomic
def reserve_slots_for_booking(
    restaurant_booking,
    *,
    table: RestaurantTable | None = None,
    slot_minutes: int = DEFAULT_SLOT_MINUTES,
) -> list[TableTimeSlot]:
    """Bron vaqt oralig'idagi slotlarni band qiladi."""
    window = _booking_window(restaurant_booking)
    if not window:
        return []

    target_date, start_time, end_time = window
    table = _resolve_table(restaurant_booking, table)
    if not table:
        return []

    ensure_slots_for_table(table, target_date, slot_minutes=slot_minutes)

    overlapping = TableTimeSlot.objects.select_for_update().filter(
        table=table,
        date=target_date,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )

    unavailable = overlapping.filter(is_available=False).exclude(
        booking=restaurant_booking,
    )
    if unavailable.exists():
        raise ValueError('Tanlangan vaqt oralig\'ida band slotlar mavjud.')

    reserved: list[TableTimeSlot] = []
    for slot in overlapping:
        slot.is_available = False
        slot.booking = restaurant_booking
        slot.save(update_fields=['is_available', 'booking', 'updated_at'])
        reserved.append(slot)
    return reserved


@transaction.atomic
def release_slots_for_booking(restaurant_booking) -> int:
    """Bron bilan bog'langan slotlarni bo'shatadi."""
    updated = TableTimeSlot.objects.filter(booking=restaurant_booking).update(
        is_available=True,
        booking=None,
    )
    return updated


def parse_target_date(value: str | date | None) -> date:
    if isinstance(value, date):
        return value
    if not value:
        return date.today()
    parsed = parse_date(str(value))
    if not parsed:
        raise ValueError('date YYYY-MM-DD formatida bo\'lishi kerak.')
    return parsed
