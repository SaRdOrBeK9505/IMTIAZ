"""
AI Tool handler'lari — function-calling natijalarini real biznes logikaga bog'laydi.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from datetime import datetime

from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r'^\+998\d{9}$')

# Shahar nomlari → IATA (AI ba'zan shahar yuboradi)
_AIRPORT_ALIASES = {
    'toshkent': 'TAS', 'tashkent': 'TAS', 'ташкент': 'TAS',
    'dubay': 'DXB', 'dubai': 'DXB', 'дубай': 'DXB',
    'sharjah': 'SHJ', 'sharja': 'SHJ', 'шарджа': 'SHJ',
    'istanbul': 'IST', 'стамбул': 'IST', 'istanbul': 'IST',
    'moskva': 'SVO', 'moscow': 'SVO', 'москва': 'SVO',
    'antalya': 'AYT', 'антalya': 'AYT',
    'baku': 'GYD', 'bakı': 'GYD', 'баку': 'GYD',
    'almaty': 'ALA', 'алматы': 'ALA',
    'seoul': 'ICN', 'seul': 'ICN',
    'delhi': 'DEL', 'dehli': 'DEL',
    'parij': 'CDG', 'paris': 'CDG', 'париж': 'CDG',
    'london': 'LHR', 'londra': 'LHR', 'лондон': 'LHR',
}


def _normalize_airport(code: str) -> str:
    cleaned = (code or '').strip()
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()
    return _AIRPORT_ALIASES.get(cleaned.lower(), cleaned.upper())


def _parse_departure_date(departure_date: str):
    try:
        return datetime.strptime(departure_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _normalize_phone(value: str) -> str:
    phone = value.strip().replace(' ', '').replace('-', '')
    if not phone.startswith('+'):
        phone = '+' + phone
    return phone


def handle_search_flights(
    user, origin: str, destination: str, departure_date: str,
    return_date: str = None, passengers: int = 1,
    seat_class: str = 'economy', lang: str = 'uz', **kwargs,
) -> dict:
    """
    Parvoz qidirish — BookharaAdapter orqali.
    Sozlanmagan yoki xato bo'lsa — aniq xabar qaytaradi (mock emas).
    """
    from apps.integrations.errors import (
        flight_search_error,
        integration_error_dict,
        is_bookhara_configured,
    )

    origin = _normalize_airport(origin)
    destination = _normalize_airport(destination)

    dep = _parse_departure_date(departure_date)
    today = timezone.now().date()
    if dep is None:
        return flight_search_error(
            'invalid_date',
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            detail='invalid_date_format',
            lang=lang,
        )
    if dep < today:
        return flight_search_error(
            'past_date',
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            detail=f'date_in_past:{departure_date}',
            lang=lang,
        )

    logger.info('Parvoz qidiruv: %s→%s %s (user=%s)', origin, destination, departure_date, user.id)

    if not is_bookhara_configured():
        logger.warning(
            'Bookhara sozlanmagan (BOOKHARA_EMAIL / BOOKHARA_PASSWORD .env da yo\'q)'
        )
        return flight_search_error(
            'not_configured',
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            detail='bookhara_not_configured',
            lang=lang,
        )

    try:
        from apps.integrations.adapters.bookhara import BookharaAdapter
        adapter = BookharaAdapter()
        offers = adapter.search(
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
                for o in offers[:3]
            ],
        }
    except Exception as e:
        return {
            **integration_error_dict(
                e, service='flight', lang=lang,
                origin=origin, destination=destination, departure_date=departure_date,
            ),
            'origin': origin,
            'destination': destination,
            'departure_date': departure_date,
        }


def handle_search_trains(
    user, origin: str, destination: str, departure_date: str,
    passengers: int = 1, wagon_type: str = 'coupe', lang: str = 'uz', **kwargs,
) -> dict:
    from django.conf import settings
    from apps.integrations.errors import integration_error_dict, train_search_error

    logger.info('Poyezd qidiruv: %s→%s (user=%s)', origin, destination, user.id)

    if not settings.RAILWAY_API_KEY:
        logger.warning('Railway integratsiyasi sozlanmagan (RAILWAY_API_KEY yo\'q)')
        return train_search_error(
            'not_configured',
            origin=origin,
            destination=destination,
            detail='railway_not_configured',
            lang=lang,
        )

    return train_search_error(
        'unavailable',
        origin=origin,
        destination=destination,
        detail='railway_not_implemented',
        lang=lang,
    )


def handle_search_restaurants(
    user, city: str, date: str, time: str,
    guests: int = 2, cuisine: str = None, lang: str = 'uz', **kwargs,
) -> dict:
    from apps.crm.models import Branch
    from .i18n import localized_field

    qs = Branch.objects.filter(
        organization__org_type='restaurant',
        organization__is_active=True,
        is_active=True,
        city__icontains=city,
    ).select_related('organization')[:10]
    results = [
        {
            'branch_id':   str(b.id),
            'name':        localized_field(b.organization, 'name', lang),
            'branch_name': localized_field(b, 'name', lang),
            'address':     localized_field(b, 'address', lang),
            'city':        b.city,
            'phone':       b.phone,
            'description': localized_field(b.organization, 'description', lang),
            'working_hours': b.working_hours,
            'capacity':    b.capacity,
        }
        for b in qs
    ] or [
        {
            'branch_id':   'mock-branch-001',
            'name':        'Nobu Tashkent',
            'branch_name': 'Asosiy filial',
            'address':     "Amir Temur ko'chasi, 107B",
            'city':        city,
            'description': "Sharafli Yapon va Pan-Osiyo taomlari, premium interyer va ajoyib shinam muhit.",
            'working_hours': {'mon_sun': '12:00-23:00'},
        }
    ]
    return {'status': 'ok', 'results': results}


def handle_book_restaurant(
    user, branch_id: str = '', date: str = None, time: str = None,
    guests: int = 2, special_requests: str = '', phone: str = '', **kwargs,
) -> dict:
    """
    Eski book_restaurant chaqiruvini handle_submit_restaurant_lead ga yo'naltirish.
    """
    user_phone = phone or user.phone
    return handle_submit_restaurant_lead(
        user=user,
        branch_id=branch_id,
        phone=user_phone,
        full_name=user.full_name,
        preferred_date=date,
        preferred_time=time,
        guests=guests,
        note=special_requests,
        **kwargs,
    )


def handle_book_flight(
    user, offer_id: str, passengers: int = 1,
    payment_method: str = 'alifpay', **kwargs,
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
    date_to: str = None, category: str = None, lang: str = 'uz', **kwargs,
) -> dict:
    from apps.events.models import Event
    from .i18n import localized_field
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
                'title':             localized_field(e, 'title', lang),
                'starts_at':         e.starts_at.isoformat(),
                'venue':             localized_field(e, 'venue_name', lang),
                'price':             float(e.ticket_price),
                'available_tickets': e.available_tickets,
                'is_exclusive':      e.is_exclusive,
            }
            for e in qs[:10]
        ],
    }


def handle_cancel_booking(user, booking_id: str, reason: str = '', lang: str = 'uz', **kwargs) -> dict:
    from django.utils import timezone
    from apps.booking.models import Booking, BookingStatus
    from .i18n import status_label, t

    try:
        booking = Booking.objects.get(id=booking_id, user=user)
    except Booking.DoesNotExist:
        return {'status': 'error', 'message': t('booking_not_found', lang)}

    if booking.status in (BookingStatus.CANCELLED, BookingStatus.COMPLETED):
        return {
            'status': 'error',
            'message': t(
                'booking_already_status', lang,
                status=status_label(booking.status, lang),
            ),
        }

    booking.status              = BookingStatus.CANCELLED
    booking.cancellation_reason = reason
    booking.cancelled_at        = timezone.now()
    booking.save(update_fields=['status', 'cancellation_reason', 'cancelled_at', 'updated_at'])
    logger.info('AI bron bekor qildi: booking=%s, user=%s', booking_id, user.id)
    return {'status': 'ok', 'message': t('booking_cancelled', lang)}


def handle_get_user_bookings(
    user, status: str = 'all', service_type: str = None, limit: int = 10,
    lang: str = 'uz', **kwargs,
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
    service_type: str = 'restaurant', radius_km: float = 5, lang: str = 'uz', **kwargs,
) -> dict:
    import math
    from apps.crm.models import Branch
    from .i18n import localized_field

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
                'name':        localized_field(branch.organization, 'name', lang),
                'branch_name': localized_field(branch, 'name', lang),
                'address':     localized_field(branch, 'address', lang),
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


def handle_search_tour_packages(
    user,
    destination: str = None,
    departure_date_from: str = None,
    passengers: int = 1,
    query: str = None,
    lang: str = 'uz',
    **kwargs,
) -> dict:
    from django.db.models import Count, Q
    from django.utils import timezone

    from apps.crm.models import Organization
    from apps.tours.models import AvailabilityStatus, TourAvailability, TourDestination, TourPackage
    from .i18n import localized_field, t

    base_qs = TourPackage.objects.filter(
        is_active=True,
        organization__org_type='tour_company',
        organization__is_active=True,
    ).select_related('organization', 'destination')

    qs = base_qs
    if destination:
        qs = qs.filter(
            Q(destination__name__icontains=destination)
            | Q(destination__city__icontains=destination)
            | Q(destination__country__icontains=destination)
        )
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(short_description__icontains=query)
            | Q(organization__name__icontains=query)
            | Q(tags__icontains=query)
        )

    today = timezone.now().date()
    packages = list(qs.order_by('-is_featured', '-created_at')[:10])

    # Filtr juda tor — filtrsiz qayta urinib ko'ramiz
    if not packages and (destination or query):
        packages = list(base_qs.order_by('-is_featured', '-created_at')[:10])

    partners_qs = (
        Organization.objects.filter(
            org_type=Organization.OrgType.TOUR_COMPANY,
            is_active=True,
        )
        .annotate(package_count=Count('tour_packages', filter=Q(tour_packages__is_active=True)))
        .order_by('-package_count', 'name')[:8]
    )
    partners = [
        {
            'id': str(org.id),
            'name': localized_field(org, 'name', lang),
            'package_count': org.package_count,
            'phone': org.contact_phone or '',
        }
        for org in partners_qs
    ]

    popular_destinations = [
        {
            'name': localized_field(d, 'name', lang),
            'country': d.country,
        }
        for d in TourDestination.objects.filter(is_active=True).order_by(
            '-is_popular', 'name',
        )[:8]
    ]

    if not packages:
        return {
            'status': 'ok',
            'results': [],
            'partners': partners,
            'popular_destinations': popular_destinations,
            'passengers': passengers,
        }

    results = []
    for pkg in packages:
        avail_qs = TourAvailability.objects.filter(
            package=pkg,
            status=AvailabilityStatus.OPEN,
            departure_date__gte=today,
        ).order_by('departure_date')

        if departure_date_from:
            try:
                date_from = datetime.strptime(departure_date_from, '%Y-%m-%d').date()
                avail_qs = avail_qs.filter(departure_date__gte=date_from)
            except ValueError:
                pass

        next_departures = []
        for av in avail_qs[:3]:
            seats = av.available_seats
            if seats >= passengers:
                next_departures.append({
                    'departure_date': av.departure_date.isoformat(),
                    'return_date': av.return_date.isoformat() if av.return_date else None,
                    'available_seats': seats,
                    'price': float(av.effective_price),
                    'currency': pkg.currency,
                })

        results.append({
            'package_id': str(pkg.id),
            'title': localized_field(pkg, 'title', lang),
            'destination': localized_field(pkg.destination, 'name', lang),
            'country': pkg.destination.country,
            'duration_days': pkg.duration_days,
            'base_price': float(pkg.base_price),
            'currency': pkg.currency,
            'organization': localized_field(pkg.organization, 'name', lang),
            'avg_rating': float(pkg.avg_rating),
            'next_departures': next_departures,
        })

    return {
        'status': 'ok',
        'results': results,
        'partners': partners,
        'popular_destinations': popular_destinations,
        'passengers': passengers,
    }


def handle_submit_tour_lead(
    user,
    phone: str,
    package_id: str = None,
    full_name: str = '',
    destination: str = None,
    preferred_departure_date: str = None,
    duration_days: int = None,
    passengers: int = 1,
    budget: str = None,
    vacation_type: str = None,
    hotel_preference: str = None,
    flight_preference: str = None,
    existing_offer: str = None,
    purchase_readiness: str = None,
    note: str = '',
    session=None,
    lang: str = 'uz',
    **kwargs,
) -> dict:
    from apps.crm.models import Organization, TourLead, TourLeadStatus
    from apps.crm.tasks import send_tour_lead_to_crm
    from apps.tours.models import TourPackage
    from .i18n import t

    normalized_phone = _normalize_phone(phone)
    if not _PHONE_RE.match(normalized_phone):
        return {
            'status': 'error',
            'message': t('tour_lead_invalid_phone', lang),
        }

    package = None
    organization = None

    if package_id:
        try:
            package = TourPackage.objects.select_related('organization').get(
                id=package_id,
                is_active=True,
                organization__org_type='tour_company',
                organization__is_active=True,
            )
            organization = package.organization
        except (TourPackage.DoesNotExist, ValidationError, ValueError):
            pass

    if not organization:
        organization = Organization.objects.filter(
            org_type=Organization.OrgType.TOUR_COMPANY,
            is_active=True,
        ).first()

    if not organization:
        organization = Organization.objects.filter(is_active=True).first()

    dep_date = None
    if preferred_departure_date:
        try:
            dep_date = datetime.strptime(preferred_departure_date, '%Y-%m-%d').date()
        except ValueError:
            pass

    if not full_name or not full_name.strip():
        full_name = user.full_name or ''

    # To'plangan ma'lumotlarni sermazmun va tartibli note formatida yig'ish
    details = []
    if destination:
        details.append(f"📍 Yo'nalish: {destination}")
    if duration_days:
        details.append(f"⏱️ Davomiyligi: {duration_days} kun")
    if budget:
        details.append(f"💰 Byudjet: {budget}")
    if vacation_type:
        details.append(f"🏝️ Dam olish turi: {vacation_type}")
    if hotel_preference:
        details.append(f"🏨 Mehmonxona: {hotel_preference}")
    if flight_preference:
        details.append(f"✈️ Parvoz afzalligi: {flight_preference}")
    if existing_offer:
        details.append(f"📄 Mavjud taklif: {existing_offer}")
    if purchase_readiness:
        details.append(f"🛒 Sotib olishga tayyorlik: {purchase_readiness}")
    if note and note.strip():
        details.append(f"💬 Izoh: {note.strip()}")

    combined_note = "\n".join(details) if details else note.strip()

    lead = TourLead.objects.create(
        organization=organization,
        package=package,
        user=user,
        session=session,
        full_name=full_name.strip(),
        phone=normalized_phone,
        preferred_departure_date=dep_date,
        passengers=max(passengers, 1),
        note=combined_note,
        status=TourLeadStatus.NEW,
    )

    send_tour_lead_to_crm.delay(str(lead.id))

    tg_res = None
    try:
        from apps.crm.tasks import send_telegram_tour_lead_notification
        tg_res = send_telegram_tour_lead_notification(str(lead.id))
    except Exception as exc:
        logger.exception('Telegram lead notification direct send error: %s', exc)

    logger.info(
        'AI tur lead yaratildi: lead=%s, package=%s, user=%s, telegram_status=%s',
        lead.id, package.id if package else None, user.id, tg_res,
    )

    title_val = package.title if package else (destination or 'Sayohat turi')
    return {
        'status': 'ok',
        'lead_id': str(lead.id),
        'message': t('tour_lead_submitted', lang, title=title_val),
    }


def handle_submit_restaurant_lead(
    user,
    branch_id: str,
    phone: str,
    full_name: str = '',
    preferred_date: str = None,
    preferred_time: str = None,
    guests: int = 2,
    note: str = '',
    session=None,
    lang: str = 'uz',
    **kwargs,
) -> dict:
    from apps.crm.models import Branch, RestaurantLead, RestaurantLeadStatus
    from apps.crm.tasks import send_tour_lead_to_crm  # webhook handler
    from .i18n import t

    normalized_phone = _normalize_phone(phone)
    if not _PHONE_RE.match(normalized_phone):
        return {
            'status': 'error',
            'message': t('tour_lead_invalid_phone', lang),
        }

    try:
        branch = Branch.objects.select_related('organization').get(
            id=branch_id,
            is_active=True,
            organization__is_active=True,
        )
    except (Branch.DoesNotExist, ValidationError, ValueError):
        # Mock or general search fallback
        branch = Branch.objects.filter(is_active=True, organization__org_type='restaurant').first()
        if not branch:
            return {'status': 'error', 'message': 'Restoran filiali topilmadi.'}

    p_date = None
    if preferred_date:
        try:
            p_date = datetime.strptime(preferred_date, '%Y-%m-%d').date()
        except ValueError:
            pass

    p_time = None
    if preferred_time:
        try:
            p_time = datetime.strptime(preferred_time, '%H:%M').time()
        except ValueError:
            pass

    if not full_name.strip():
        full_name = user.full_name or ''

    lead = RestaurantLead.objects.create(
        organization=branch.organization,
        branch=branch,
        user=user,
        session=session,
        full_name=full_name.strip(),
        phone=normalized_phone,
        preferred_date=p_date,
        preferred_time=p_time,
        guests=max(guests, 1),
        note=note.strip(),
        status=RestaurantLeadStatus.NEW,
    )

    tg_res = None
    try:
        from apps.crm.tasks import send_telegram_restaurant_lead_notification
        tg_res = send_telegram_restaurant_lead_notification(str(lead.id))
    except Exception as exc:
        logger.exception('Telegram restaurant lead notification error: %s', exc)

    logger.info(
        'AI restoran lead yaratildi: lead=%s, branch=%s, user=%s, telegram_status=%s',
        lead.id, branch.id, user.id, tg_res,
    )

    return {
        'status': 'ok',
        'lead_id': str(lead.id),
        'message': f"✅ {branch.organization.name} bo'yicha stol bron so'rovingiz qabul qilindi. Restoran menejerlari tez fursatda siz bilan bog'lanishadi — bu uzoq vaqt olmaydi.",
    }


def handle_submit_service_lead(
    user,
    phone: str,
    category: str = 'other',
    full_name: str = '',
    service_name: str = '',
    customer_analysis: str = '',
    note: str = '',
    session=None,
    lang: str = 'uz',
    **kwargs,
) -> dict:
    from apps.crm.models import ServiceLead, ServiceLeadCategory, ServiceLeadStatus
    from apps.crm.tasks import send_telegram_service_lead_notification
    from .i18n import t

    normalized_phone = _normalize_phone(phone)
    if not _PHONE_RE.match(normalized_phone):
        return {
            'status': 'error',
            'message': t('tour_lead_invalid_phone', lang),
        }

    if not full_name or not full_name.strip():
        full_name = user.full_name or ''

    valid_category = category if category in ServiceLeadCategory.values else ServiceLeadCategory.OTHER

    lead = ServiceLead.objects.create(
        category=valid_category,
        user=user,
        session=session,
        full_name=full_name.strip(),
        phone=normalized_phone,
        service_name=service_name.strip(),
        customer_analysis=customer_analysis.strip(),
        note=note.strip(),
        status=ServiceLeadStatus.NEW,
    )

    tg_res = None
    try:
        tg_res = send_telegram_service_lead_notification(str(lead.id))
    except Exception as exc:
        logger.exception('Telegram service lead notification error: %s', exc)

    logger.info('AI service lead yaratildi: lead=%s, category=%s, user=%s, telegram_status=%s', lead.id, valid_category, user.id, tg_res)

    service_title = service_name or lead.get_category_display()
    return {
        'status': 'ok',
        'lead_id': str(lead.id),
        'message': f"✅ {service_title} bo'yicha so'rovingiz qabul qilindi. Mutaxassislarimiz tez orada siz bilan bog'lanishadi.",
    }


def handle_submit_flight_lead(
    user,
    phone: str,
    origin: str,
    destination: str,
    departure_date: str = None,
    passengers: int = 1,
    seat_class: str = 'economy',
    full_name: str = '',
    customer_analysis: str = '',
    note: str = '',
    session=None,
    lang: str = 'uz',
    **kwargs,
) -> dict:
    from apps.crm.models import ServiceLeadCategory

    details = [
        f"✈️ Yo'nalish: {origin} → {destination}",
        f"📅 Sana: {departure_date or 'Belgilanmagan'}",
        f"👥 Yo'lovchilar: {passengers} kishi ({seat_class} klass)",
    ]
    if note and note.strip():
        details.append(f"💬 Izoh: {note.strip()}")

    combined_note = "\n".join(details)
    service_title = f"Parvoz: {origin} → {destination}"

    return handle_submit_service_lead(
        user=user,
        phone=phone,
        category=ServiceLeadCategory.FLIGHT,
        full_name=full_name,
        service_name=service_title,
        customer_analysis=customer_analysis,
        note=combined_note,
        session=session,
        lang=lang,
        **kwargs,
    )


TOOL_DISPATCH: dict = {
    'search_flights':         handle_search_flights,
    'search_trains':          handle_search_trains,
    'search_restaurants':     handle_search_restaurants,
    'book_restaurant':        handle_book_restaurant,
    'book_flight':            handle_book_flight,
    'search_events':          handle_search_events,
    'cancel_booking':         handle_cancel_booking,
    'get_user_bookings':      handle_get_user_bookings,
    'get_nearby_places':      handle_get_nearby_places,
    'get_user_preferences':   handle_get_user_preferences,
    'search_tour_packages':   handle_search_tour_packages,
    'submit_tour_lead':       handle_submit_tour_lead,
    'submit_restaurant_lead': handle_submit_restaurant_lead,
    'submit_service_lead':    handle_submit_service_lead,
    'submit_flight_lead':     handle_submit_flight_lead,
}