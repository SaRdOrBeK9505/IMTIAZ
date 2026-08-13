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
    for i, o in enumerate(offers[:5], 1):
        price = o.get('price', 0)
        currency = o.get('currency', 'UZS')
        lines.append(t(
            'flight_item', lang,
            i=i,
            airline=o.get('airline', '?'),
            number=o.get('flight_number', ''),
            price=price,
            currency=currency,
        ))
    if len(offers) > 5:
        lines.append(t('flights_more', lang, count=len(offers) - 5))
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
    if not items:
        return result.get('message') or t('tours_not_found', lang)
    lines = [t('tours_header', lang, count=len(items))]
    for i, pkg in enumerate(items[:5], 1):
        dep = pkg.get('next_departures') or []
        dep_str = dep[0]['departure_date'] if dep else '—'
        lines.append(t(
            'tour_item', lang,
            i=i,
            title=pkg.get('title', '?'),
            destination=pkg.get('destination', '?'),
            price=pkg.get('base_price', 0),
            currency=pkg.get('currency', 'UZS'),
            departure=dep_str,
        ))
    return '\n'.join(lines)
