"""
AI Tool handler'lari — function-calling natijalarini real biznes logikaga bog'laydi.
"""

from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def handle_search_flights(
    user, origin: str, destination: str, departure_date: str,
    return_date: str = None, passengers: int = 1,
    seat_class: str = 'economy', **kwargs,
) -> dict:
    """
    Parvoz qidirish — BookharaAdapter orqali.
    API kaliti yo'q bo'lsa mock natija qaytaradi.
    """
    logger.info('Parvoz qidiruv: %s→%s %s (user=%s)', origin, destination, departure_date, user.id)

    from django.conf import settings
    if settings.BOOKHARA_API_KEY and settings.BOOKHARA_LOGIN:
        try:
            from apps.integrations.adapters.bookhara import BookharaAdapter
            adapter = BookharaAdapter()
            offers  = adapter.search(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                passengers=passengers,
                seat_class=seat_class,
                return_date=return_date,
            )
            return {
                'status':         'ok',
                'origin':         origin,
                'destination':    destination,
                'departure_date': departure_date,
                'offers': [
                    {
                        'offer_id':        o.offer_id,
                        'airline':         o.airline,
                        'flight_number':   o.flight_number,
                        'departure_at':    o.departure_at,
                        'arrival_at':      o.arrival_at,
                        'price':           float(o.price),
                        'currency':        o.currency,
                        'seat_class':      o.seat_class,
                        'available_seats': o.available_seats,
                        'baggage':         o.baggage_included,
                    }
                    for o in offers
                ],
            }
        except Exception as e:
            logger.warning('Bookhara search xato, mock qaytarilmoqda: %s', e)

    # Mock — API sozlanmagan yoki xato
    return {
        'status':         'ok',
        'origin':         origin,
        'destination':    destination,
        'departure_date': departure_date,
        'offers': [
            {
                'offer_id':        'mock-flight-001',
                'airline':         'Uzbekistan Airways',
                'flight_number':   'HY401',
                'departure_at':    f'{departure_date}T08:00:00',
                'arrival_at':      f'{departure_date}T10:30:00',
                'price':           1_500_000,
                'currency':        'UZS',
                'seat_class':      seat_class,
                'available_seats': 15,
                'baggage':         False,
            }
        ],
    }


def handle_search_trains(
    user, origin: str, destination: str, departure_date: str,
    passengers: int = 1, wagon_type: str = 'coupe', **kwargs,
) -> dict:
    logger.info('Poyezd qidiruv: %s→%s (user=%s)', origin, destination, user.id)
    return {
        'status': 'ok',
        'offers': [
            {
                'offer_id':    'mock-train-001',
                'train_number':'005',
                'departure_at': f'{departure_date}T18:00:00',
                'arrival_at':   f'{departure_date}T22:00:00',
                'price':        350_000,
                'currency':     'UZS',
                'wagon_type':   wagon_type,
            }
        ],
    }


def handle_search_restaurants(
    user, city: str, date: str, time: str,
    guests: int = 2, cuisine: str = None, **kwargs,
) -> dict:
    from apps.crm.models import Branch
    qs = Branch.objects.filter(
        organization__org_type='restaurant',
        organization__is_active=True,
        is_active=True,
        city__icontains=city,
    ).select_related('organization')[:10]
    results = [
        {
            'branch_id':   str(b.id),
            'name':        b.organization.name,
            'branch_name': b.name,
            'address':     b.address,
            'city':        b.city,
            'phone':       b.phone,
        }
        for b in qs
    ] or [
        {
            'branch_id':   'mock-branch-001',
            'name':        'Nobu Tashkent',
            'branch_name': 'Asosiy filial',
            'address':     "Amir Temur ko'chasi, 107B",
            'city':        city,
        }
    ]
    return {'status': 'ok', 'results': results}


def handle_book_restaurant(
    user, branch_id: str, date: str, time: str,
    guests: int = 2, special_requests: str = '', **kwargs,
) -> dict:
    """
    Bu handler services.py dagi WRITE_TOOL_TO_ACTION orqali
    requires_confirmation() ga yuboriladi.
    Haqiqiy booking confirmation.py::_execute_booking() orqali yaratiladi.
    """
    raise NotImplementedError(
        "handle_book_restaurant to'g'ridan-to'g'ri chaqirilmaydi. "
        "Tasdiqlangan holda confirmation.py::_execute_booking() ishga tushadi."
    )


def handle_book_flight(
    user, offer_id: str, passengers: int = 1,
    payment_method: str = 'wallet', **kwargs,
) -> dict:
    """
    Bu handler services.py tomonidan WRITE_TOOL_TO_ACTION orqali
    requires_confirmation() ga yuboriladi.
    Manual/semi_auto da bu handler umuman chaqirilmaydi —
    o'rniga create_pending_action() chaqiriladi.
    Full_auto + limit ichida bo'lsa ham hozircha
    confirmation orqali ishlaydi (ehtiyot sababli).
    Haqiqiy booking confirmation.py::_create_flight_booking() da yaratiladi.
    """
    raise NotImplementedError(
        "handle_book_flight to'g'ridan-to'g'ri chaqirilmaydi. "
        "Tasdiqlangan holda confirmation.py::_create_flight_booking() ishga tushadi."
    )


def handle_search_events(
    user, city: str = None, date_from: str = None,
    date_to: str = None, category: str = None, **kwargs,
) -> dict:
    from apps.events.models import Event
    try:
        has_exclusive = user.membership_tier.exclusive_events_access
    except Exception:
        has_exclusive = False
    qs = Event.objects.filter(status='published')
    if not has_exclusive:
        qs = qs.filter(is_exclusive=False)
    if city:
        qs = qs.filter(venue_address__icontains=city)
    return {
        'status': 'ok',
        'results': [
            {
                'event_id':          str(e.id),
                'title':             e.title,
                'starts_at':         e.starts_at.isoformat(),
                'venue':             e.venue_name,
                'price':             float(e.ticket_price),
                'available_tickets': e.available_tickets,
                'is_exclusive':      e.is_exclusive,
            }
            for e in qs[:10]
        ],
    }


def handle_cancel_booking(user, booking_id: str, reason: str = '', **kwargs) -> dict:
    from django.utils import timezone
    from apps.booking.models import Booking, BookingStatus

    try:
        booking = Booking.objects.get(id=booking_id, user=user)
    except Booking.DoesNotExist:
        return {'status': 'error', 'message': 'Bron topilmadi.'}

    if booking.status in (BookingStatus.CANCELLED, BookingStatus.COMPLETED):
        return {'status': 'error', 'message': f'Bron allaqachon {booking.status}.'}

    booking.status              = BookingStatus.CANCELLED
    booking.cancellation_reason = reason
    booking.cancelled_at        = timezone.now()
    booking.save(update_fields=['status', 'cancellation_reason', 'cancelled_at', 'updated_at'])
    logger.info('AI bron bekor qildi: booking=%s, user=%s', booking_id, user.id)
    return {'status': 'ok', 'message': 'Bron bekor qilindi.'}


def handle_get_user_bookings(
    user, status: str = 'all', service_type: str = None, limit: int = 10, **kwargs
) -> dict:
    from apps.booking.models import Booking
    qs = Booking.objects.filter(user=user).order_by('-created_at')
    if status != 'all':
        qs = qs.filter(status=status)
    if service_type:
        qs = qs.filter(service_type=service_type)
    return {
        'status': 'ok',
        'bookings': [
            {
                'booking_id':   str(b.id),
                'service_type': b.service_type,
                'title':        b.title,
                'status':       b.status,
                'final_price':  float(b.final_price),
                'created_at':   b.created_at.isoformat(),
            }
            for b in qs[:limit]
        ],
    }


def handle_get_nearby_places(
    user, latitude: float, longitude: float,
    service_type: str = 'restaurant', radius_km: float = 5, **kwargs,
) -> dict:
    import math
    from apps.crm.models import Branch

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon/2)**2)
        return R * 2 * math.asin(math.sqrt(a))

    org_type_map = {'restaurant': 'restaurant', 'event': 'event_organizer', 'hotel': 'hotel'}
    qs = Branch.objects.filter(
        organization__org_type=org_type_map.get(service_type, service_type),
        is_active=True, latitude__isnull=False, longitude__isnull=False,
    ).select_related('organization')

    nearby = []
    for branch in qs:
        dist = haversine(latitude, longitude, float(branch.latitude), float(branch.longitude))
        if dist <= radius_km:
            nearby.append({
                'branch_id':   str(branch.id),
                'name':        branch.organization.name,
                'branch_name': branch.name,
                'address':     branch.address,
                'distance_km': round(dist, 2),
                'phone':       branch.phone,
            })
    nearby.sort(key=lambda x: x['distance_km'])
    return {'status': 'ok', 'latitude': latitude, 'longitude': longitude,
            'radius_km': radius_km, 'results': nearby[:5]}


def handle_get_user_preferences(user, **kwargs) -> dict:
    from apps.booking.models import Booking
    recent = (
        Booking.objects
        .filter(user=user, status__in=['confirmed', 'completed'])
        .order_by('-created_at')
        .values('service_type', 'final_price', 'booking_date')[:20]
    )
    service_counts: dict[str, int] = {}
    total_spent: float = 0
    for b in recent:
        stype = b['service_type']
        service_counts[stype] = service_counts.get(stype, 0) + 1
        total_spent += float(b['final_price'] or 0)
    preferred = max(service_counts, key=service_counts.get) if service_counts else None
    return {
        'status':            'ok',
        'total_bookings':    len(list(recent)),
        'total_spent_uzs':   total_spent,
        'service_breakdown': service_counts,
        'preferred_service': preferred,
        'ai_price_limit':    float(user.ai_auto_price_limit),
        'autonomy_level':    user.ai_autonomy_level,
    }


TOOL_DISPATCH: dict = {
    'search_flights':       handle_search_flights,
    'search_trains':        handle_search_trains,
    'search_restaurants':   handle_search_restaurants,
    'book_restaurant':      handle_book_restaurant,
    'book_flight':          handle_book_flight,
    'search_events':        handle_search_events,
    'cancel_booking':       handle_cancel_booking,
    'get_user_bookings':    handle_get_user_bookings,
    'get_nearby_places':    handle_get_nearby_places,
    'get_user_preferences': handle_get_user_preferences,
}
