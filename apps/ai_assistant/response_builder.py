"""
Tool natijalaridan foydalanuvchiga javob yig'ish — ikkinchi AI chaqiruvsiz.
Token tejash va barqaror xato xabarlari uchun (asosan o'zbek tilida).
"""

from __future__ import annotations

import json

from .i18n import normalize_language, service_label, status_label, t


def trim_tool_result_for_ai(result: dict, max_offers: int = 5) -> dict:
    """AI ga yuboriladigan tool natijasini qisqartirish."""
    if not isinstance(result, dict):
        return result
    trimmed = dict(result)
    if 'offers' in trimmed and isinstance(trimmed['offers'], list):
        trimmed['offers'] = trimmed['offers'][:max_offers]
        if len(result['offers']) > max_offers:
            trimmed['offers_truncated'] = True
    if 'results' in trimmed and isinstance(trimmed['results'], list):
        trimmed['results'] = trimmed['results'][:max_offers]
    return trimmed


def can_reply_without_ai(tool_results: list[dict]) -> bool:
    """Barcha tool natijalari lokal formatlash mumkinmi?"""
    if not tool_results:
        return False
    for item in tool_results:
        result = item.get('result')
        if not isinstance(result, dict) or 'status' not in result:
            return False
    return True


def should_use_local_reply(tool_results: list[dict], user_message: str, lang: str) -> bool:
    """
    Ikkinchi AI chaqiruvsiz local-shablon bilan javob berish mumkinmi?

    Strategiya — faqat eng oddiy, ro'yxat-tipidagi natijalar uchun shablon.
    Qolgan barcha holatlar (shaxsiy ma'lumot, bronlar, afzalliklar,
    bo'sh natija, murakkab kontekst) uchun Gemini o'zi jonli javob yozadi.

    Nima uchun muhim:
      - get_user_preferences, get_user_bookings — shaxsiy, kontekstga bog'liq
      - search_tour_packages — bo'sh natijada partner/yo'nalish taklif kerak
      - Umumiy qoida: AI javob berishi > shablon, faqat token/tezlik sabab cheklanadi
    """
    from django.conf import settings

    if not can_reply_without_ai(tool_results):
        return False
    if not getattr(settings, 'AI_SKIP_SECOND_CALL', True):
        return False
    if normalize_language(lang) != 'uz':
        return False

    # Faqat ro'yxat-tipidagi oddiy tool'lar uchun shablon ruxsat etiladi.
    # Shaxsiy/kontekstga bog'liq tool'lar (preferences, bookings) — har doim AI orqali.
    SIMPLE_LIST_TOOLS = {'search_flights', 'search_restaurants', 'search_events', 'search_trains'}
    tool_names = {item.get('tool_name') for item in tool_results}
    if not tool_names.issubset(SIMPLE_LIST_TOOLS):
        return False

    msg = (user_message or '').lower()
    detail_keywords = (
        'vaqt', 'soat', 'nechchida', 'qachon', "to'liq", 'batafsil',
        'kelish', 'ketish', 'qancha vaqt', 'kechqurun', 'ertalab',
        'подробн', 'время', 'когда', 'detail', 'time', 'when',
    )
    if any(kw in msg for kw in detail_keywords):
        return False

    # Ro'yxat bo'sh bo'lsa — AI alternativa taklif qilsin
    for item in tool_results:
        result = item.get('result') or {}
        has_results = (
            result.get('offers') or result.get('results') or result.get('flights')
        )
        if not has_results:
            return False

    return True


def _format_time_short(dt_str: str) -> str:
    """ISO datetime → HH:MM (mahalliy vaqt sifatida)."""
    if not dt_str:
        return '—'
    if 'T' in dt_str:
        return dt_str.split('T')[1][:5]
    if ' ' in dt_str:
        return dt_str.split(' ')[1][:5]
    return dt_str[:5] if len(dt_str) >= 5 else dt_str


def build_reply_from_tools(tool_results: list[dict], lang: str = 'uz') -> str:
    """Tool natijalaridan foydalanuvchiga javob — tilga mos."""
    lang = normalize_language(lang)
    parts: list[str] = []

    for item in tool_results:
        name = item.get('tool_name', '')
        result = item.get('result') or {}

        if result.get('status') == 'error':
            parts.append(result.get('message') or t('service_unavailable', lang))
            continue

        if name == 'search_flights':
            parts.append(_format_flights(result, lang))
        elif name == 'search_trains':
            parts.append(_format_trains(result, lang))
        elif name == 'search_restaurants':
            parts.append(_format_restaurants(result, lang))
        elif name == 'search_events':
            parts.append(_format_events(result, lang))
        elif name == 'get_user_bookings':
            parts.append(_format_bookings(result, lang))
        elif name == 'get_nearby_places':
            parts.append(_format_nearby(result, lang))
        elif name == 'get_user_preferences':
            parts.append(_format_preferences(result, lang))
        elif name == 'search_tour_packages':
            parts.append(_format_tours(result, lang))
        elif name == 'submit_tour_lead':
            parts.append(result.get('message', t('action_done', lang)))
        elif name == 'cancel_booking':
            parts.append(result.get('message', t('action_done', lang)))
        else:
            parts.append(json.dumps(result, ensure_ascii=False)[:500])

    return '\n\n'.join(p for p in parts if p).strip() or t('default_tool_reply', lang)


def _format_flights(result: dict, lang: str) -> str:
    offers = result.get('offers') or []
    if not offers:
        route = f"{result.get('origin', '?')} → {result.get('destination', '?')}"
        return t(
            'flights_not_found', lang,
            route=route,
            date=result.get('departure_date', ''),
        )

    lines = [
        t(
            'flights_header', lang,
            origin=result.get('origin'),
            destination=result.get('destination'),
            date=result.get('departure_date'),
            count=len(offers),
        )
    ]
    seen: set[str] = set()
    shown = 0
    for o in offers:
        dep_t = _format_time_short(o.get('departure_at', ''))
        arr_t = _format_time_short(o.get('arrival_at', ''))
        key = f"{o.get('airline')}|{o.get('flight_number')}|{dep_t}|{o.get('price')}"
        if key in seen:
            continue
        seen.add(key)
        shown += 1
        if shown > 5:
            break
        baggage = o.get('baggage')
        baggage_str = t('flight_baggage_yes', lang) if baggage else ''
        lines.append(t(
            'flight_item', lang,
            i=shown,
            airline=o.get('airline', '?'),
            number=o.get('flight_number', ''),
            departure_time=dep_t,
            arrival_time=arr_t,
            price=o.get('price', 0),
            currency=o.get('currency', 'UZS'),
            baggage=baggage_str,
        ))
    remaining = max(len(offers) - shown, 0)
    if remaining > 0:
        lines.append(t('flights_more', lang, count=remaining))
    lines.append(t('flights_book_hint', lang))
    return '\n'.join(lines)


def _format_trains(result: dict, lang: str) -> str:
    offers = result.get('offers') or []
    if not offers:
        return t('trains_not_found', lang)
    lines = [t('trains_header', lang, count=len(offers))]
    for i, o in enumerate(offers[:5], 1):
        lines.append(t(
            'train_item', lang,
            i=i,
            number=o.get('train_number', '?'),
            price=o.get('price', 0),
        ))
    return '\n'.join(lines)


def _format_restaurants(result: dict, lang: str) -> str:
    items = result.get('results') or []
    if not items:
        return t('restaurants_not_found', lang)
    lines = [t('restaurants_header', lang, count=len(items))]
    for i, r in enumerate(items[:5], 1):
        lines.append(f"{i}. {r.get('name', '?')} — {r.get('address', '')}")
    return '\n'.join(lines)


def _format_events(result: dict, lang: str) -> str:
    items = result.get('results') or []
    if not items:
        return t('events_not_found', lang)
    lines = [t('events_header', lang, count=len(items))]
    for i, e in enumerate(items[:5], 1):
        lines.append(f"{i}. {e.get('title', '?')} — {e.get('venue', '')}")
    return '\n'.join(lines)


def _format_bookings(result: dict, lang: str) -> str:
    bookings = result.get('bookings') or []
    if not bookings:
        return t('bookings_empty', lang)
    lines = [t('bookings_header', lang, count=len(bookings))]
    for b in bookings[:5]:
        lines.append(t(
            'booking_item', lang,
            title=b.get('title', '?'),
            status=status_label(b.get('status', '?'), lang),
            price=b.get('final_price', 0),
        ))
    return '\n'.join(lines)


def _format_nearby(result: dict, lang: str) -> str:
    items = result.get('results') or []
    if not items:
        return t('nearby_not_found', lang)
    lines = [t('nearby_header', lang, count=len(items))]
    for r in items:
        lines.append(t(
            'nearby_item', lang,
            name=r.get('name', '?'),
            distance=r.get('distance_km', '?'),
        ))
    return '\n'.join(lines)


def _format_preferences(result: dict, lang: str) -> str:
    preferred = service_label(result.get('preferred_service'), lang)
    total = result.get('total_bookings', 0)
    spent = result.get('total_spent_uzs', 0)
    return t(
        'preferences_summary', lang,
        total=total,
        spent=spent,
        preferred=preferred,
    )


def _format_tours(result: dict, lang: str) -> str:
    items = result.get('results') or []
    if items:
        lines = [t('tours_header', lang, count=len(items))]
        for i, pkg in enumerate(items[:5], 1):
            dep = pkg.get('next_departures') or []
            dep_str = dep[0]['departure_date'] if dep else t('tour_date_flexible', lang)
            org = pkg.get('organization', '')
            org_part = f" ({org})" if org else ''
            lines.append(t(
                'tour_item', lang,
                i=i,
                title=pkg.get('title', '?'),
                destination=pkg.get('destination', '?'),
                price=pkg.get('base_price', 0),
                currency=pkg.get('currency', 'UZS'),
                departure=dep_str,
                organization=org_part,
            ))
        if len(items) > 5:
            lines.append(t('tours_more', lang, count=len(items) - 5))
        lines.append(t('tours_interest_hint', lang))
        return '\n'.join(lines)

    lines = [t('tours_no_packages_intro', lang)]
    partners = result.get('partners') or []
    if partners:
        lines.append(t('tours_partners_header', lang))
        for i, p in enumerate(partners[:5], 1):
            pkg_count = p.get('package_count', 0)
            if pkg_count:
                lines.append(t(
                    'tour_partner_item', lang,
                    i=i, name=p.get('name', '?'), package_count=pkg_count,
                ))
            else:
                lines.append(t(
                    'tour_partner_item_new', lang,
                    i=i, name=p.get('name', '?'),
                ))
    destinations = result.get('popular_destinations') or []
    if destinations:
        dest_names = ', '.join(
            f"{d.get('name', '?')} ({d.get('country', '')})" for d in destinations[:6]
        )
        lines.append(t('tours_destinations_hint', lang, destinations=dest_names))

    lines.append(t('tours_empty_suggest', lang))
    return '\n'.join(lines)
