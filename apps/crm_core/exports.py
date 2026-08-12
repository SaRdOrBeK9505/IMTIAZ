"""CRM hisobot eksport — CSV va Excel."""

from __future__ import annotations

import csv
import io
from datetime import timedelta

from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus


def _period_start(period: str):
    now = timezone.now()
    if period == 'weekly':
        return now - timedelta(days=7)
    if period == 'monthly':
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def get_restaurant_bookings_queryset(organization, *, period: str = 'daily', branch=None):
    start = _period_start(period)
    qs = Booking.objects.filter(
        restaurant_detail__isnull=False,
        created_at__gte=start,
    ).select_related('user', 'restaurant_detail', 'restaurant_detail__branch')

    if branch:
        qs = qs.filter(restaurant_detail__branch=branch)
    else:
        branch_ids = organization.branches.filter(is_active=True).values_list('id', flat=True)
        qs = qs.filter(restaurant_detail__branch_id__in=branch_ids)
    return qs.order_by('-created_at')


def build_restaurant_analytics_summary(organization, *, period: str = 'daily', branch=None) -> dict:
    qs = get_restaurant_bookings_queryset(organization, period=period, branch=branch)
    confirmed = qs.filter(status=BookingStatus.CONFIRMED)
    aggregated = confirmed.aggregate(total_revenue=Sum('final_price'))
    return {
        'period': period,
        'organization': organization.name,
        'branch': branch.name if branch else 'Barcha filiallar',
        'total_bookings': qs.count(),
        'pending': qs.filter(status=BookingStatus.PENDING).count(),
        'confirmed': confirmed.count(),
        'cancelled': qs.filter(status=BookingStatus.CANCELLED).count(),
        'total_revenue': aggregated['total_revenue'] or 0,
    }


def export_restaurant_bookings_csv(organization, *, period: str = 'daily', branch=None) -> HttpResponse:
    qs = get_restaurant_bookings_queryset(organization, period=period, branch=branch)
    summary = build_restaurant_analytics_summary(organization, period=period, branch=branch)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['IMTIAZ — Restoran bronlari hisoboti'])
    writer.writerow(['Tashkilot', summary['organization']])
    writer.writerow(['Filial', summary['branch']])
    writer.writerow(['Davr', summary['period']])
    writer.writerow(['Jami bronlar', summary['total_bookings']])
    writer.writerow(['Tasdiqlangan', summary['confirmed']])
    writer.writerow(['Kutilmoqda', summary['pending']])
    writer.writerow(['Bekor', summary['cancelled']])
    writer.writerow(['Daromad', summary['total_revenue']])
    writer.writerow([])
    writer.writerow([
        'Sana', 'Mijoz', 'Telefon', 'Filial', 'Mehmonlar', 'Holat', 'Summa',
    ])

    for booking in qs:
        rd = booking.restaurant_detail
        writer.writerow([
            rd.reservation_at.strftime('%Y-%m-%d %H:%M') if rd else '',
            booking.user.full_name,
            booking.user.phone,
            rd.branch.name if rd and rd.branch else '',
            rd.guest_count if rd else '',
            booking.status,
            booking.final_price,
        ])

    response = HttpResponse(buffer.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="restaurant_bookings_{period}.csv"'
    return response


def export_restaurant_bookings_xlsx(organization, *, period: str = 'daily', branch=None) -> HttpResponse:
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise ImportError('openpyxl o\'rnatilmagan. pip install openpyxl') from exc

    qs = get_restaurant_bookings_queryset(organization, period=period, branch=branch)
    summary = build_restaurant_analytics_summary(organization, period=period, branch=branch)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Bronlar'
    ws.append(['IMTIAZ — Restoran bronlari'])
    for row in (
        ['Tashkilot', summary['organization']],
        ['Filial', summary['branch']],
        ['Davr', summary['period']],
        ['Jami', summary['total_bookings']],
        ['Tasdiqlangan', summary['confirmed']],
        ['Daromad', float(summary['total_revenue'])],
        [],
        ['Sana', 'Mijoz', 'Telefon', 'Filial', 'Mehmonlar', 'Holat', 'Summa'],
    ):
        ws.append(row)

    for booking in qs:
        rd = booking.restaurant_detail
        ws.append([
            rd.reservation_at.strftime('%Y-%m-%d %H:%M') if rd else '',
            booking.user.full_name,
            booking.user.phone,
            rd.branch.name if rd and rd.branch else '',
            rd.guest_count if rd else '',
            booking.status,
            float(booking.final_price or 0),
        ])

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    response = HttpResponse(
        stream.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="restaurant_bookings_{period}.xlsx"'
    return response
