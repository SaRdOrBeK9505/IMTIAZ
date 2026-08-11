"""
Tool natijalaridan foydalanuvchiga javob yig'ish — ikkinchi AI chaqiruvsiz.
Token tejash va barqaror xato xabarlari uchun.
"""

from __future__ import annotations

import json


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


def build_reply_from_tools(tool_results: list[dict]) -> str:
    """Tool natijalaridan o'zbekcha javob — AI chaqiruvsiz."""
    parts: list[str] = []

    for item in tool_results:
        name = item.get('tool_name', '')
        result = item.get('result') or {}

        if result.get('status') == 'error':
            parts.append(result.get('message') or 'Xizmat vaqtincha ishlamayapti.')
            continue

        if name == 'search_flights':
            parts.append(_format_flights(result))
        elif name == 'search_trains':
            parts.append(_format_trains(result))
        elif name == 'search_restaurants':
            parts.append(_format_restaurants(result))
        elif name == 'search_events':
            parts.append(_format_events(result))
        elif name == 'get_user_bookings':
            parts.append(_format_bookings(result))
        elif name == 'get_nearby_places':
            parts.append(_format_nearby(result))
        elif name == 'get_user_preferences':
            parts.append(_format_preferences(result))
        elif name == 'cancel_booking':
            parts.append(result.get('message', 'Amal bajarildi.'))
        else:
            parts.append(json.dumps(result, ensure_ascii=False)[:500])

    return '\n\n'.join(p for p in parts if p).strip() or (
        "So'rovingiz bo'yicha ma'lumot topildi."
    )


def _format_flights(result: dict) -> str:
    offers = result.get('offers') or []
    if not offers:
        route = f"{result.get('origin', '?')} → {result.get('destination', '?')}"
        return f"{route} yo'nalishida {result.get('departure_date', '')} sanasida parvoz topilmadi."

    lines = [
        f"✈️ {result.get('origin')} → {result.get('destination')} "
        f"({result.get('departure_date')}) — {len(offers)} ta variant:"
    ]
    for i, o in enumerate(offers[:5], 1):
        price = o.get('price', 0)
        currency = o.get('currency', 'UZS')
        lines.append(
            f"{i}. {o.get('airline', '?')} {o.get('flight_number', '')} — "
            f"{price:,.0f} {currency}"
        )
    if len(offers) > 5:
        lines.append(f"... va yana {len(offers) - 5} ta variant.")
    return '\n'.join(lines)


def _format_trains(result: dict) -> str:
    offers = result.get('offers') or []
    if not offers:
        return "Poyezd reyslari topilmadi."
    lines = [f"🚂 {len(offers)} ta poyezd varianti:"]
    for i, o in enumerate(offers[:5], 1):
        lines.append(
            f"{i}. Poyezd {o.get('train_number', '?')} — {o.get('price', 0):,.0f} UZS"
        )
    return '\n'.join(lines)


def _format_restaurants(result: dict) -> str:
    items = result.get('results') or []
    if not items:
        return "Restoran topilmadi."
    lines = [f"🍽 {len(items)} ta restoran:"]
    for i, r in enumerate(items[:5], 1):
        lines.append(f"{i}. {r.get('name', '?')} — {r.get('address', '')}")
    return '\n'.join(lines)


def _format_events(result: dict) -> str:
    items = result.get('results') or []
    if not items:
        return "Tadbir topilmadi."
    lines = [f"🎭 {len(items)} ta tadbir:"]
    for i, e in enumerate(items[:5], 1):
        lines.append(f"{i}. {e.get('title', '?')} — {e.get('venue', '')}")
    return '\n'.join(lines)


def _format_bookings(result: dict) -> str:
    bookings = result.get('bookings') or []
    if not bookings:
        return "Sizda hozircha bronlar yo'q."
    lines = [f"📋 {len(bookings)} ta bron:"]
    for b in bookings[:5]:
        lines.append(
            f"• {b.get('title', '?')} — {b.get('status', '?')} "
            f"({b.get('final_price', 0):,.0f} UZS)"
        )
    return '\n'.join(lines)


def _format_nearby(result: dict) -> str:
    items = result.get('results') or []
    if not items:
        return "Yaqin atrofda xizmat topilmadi."
    lines = [f"📍 Yaqin atrofda {len(items)} ta joy:"]
    for r in items:
        lines.append(
            f"• {r.get('name', '?')} — {r.get('distance_km', '?')} km"
        )
    return '\n'.join(lines)


def _format_preferences(result: dict) -> str:
    preferred = result.get('preferred_service') or 'aniqlanmadi'
    total = result.get('total_bookings', 0)
    spent = result.get('total_spent_uzs', 0)
    return (
        f"Sizda {total} ta bron, jami {spent:,.0f} UZS. "
        f"Afzal xizmat: {preferred}."
    )
