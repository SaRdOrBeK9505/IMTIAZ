"""
AI harakatlari uchun backend tasdiqlash mexanizmi.
AIActionLog modeli ustida ishlaydi — parallel tizim yo'q.

Oqim:
    1. AI book_flight tool'ini chaqiradi
    2. requires_confirmation(user, 'book') → True (manual mode)
    3. create_pending_action() → AIActionLog(status='needs_confirmation') yaratiladi
       Booking YARATILMAYDI
    4. Frontend'ga action_id va summary qaytariladi
    5. Foydalanuvchi alohida tugmani bosadi →
       POST /api/ai/actions/{action_id}/confirm
    6. confirm_pending_action() → tekshiruvlar → haqiqiy booking yaratiladi
       AIActionLog(status='success') ga o'tkaziladi

Muhim:
    - "ha" deb yozish tasdiqlash EMAS — faqat alohida HTTP endpoint orqali
    - Har bir action_id bir martagina ishlatiladi (replay attack oldini olish)
    - 5 daqiqa o'tgach eskiradi
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)

CONFIRMATION_TTL_MINUTES = 5

# Har doim tasdiqlash talab qiluvchi action turlari
ALWAYS_CONFIRM_ACTIONS = frozenset({'cancel', 'payment_confirm', 'payment_initiate'})

# semi_auto uchun bepul limit
SEMI_AUTO_FREE_LIMIT = Decimal('300_000')


# ─── requires_confirmation ────────────────────────────────────────────────────

def requires_confirmation(user, action_type: str, amount: Decimal | None = None) -> bool:
    """
    Ushbu harakat uchun foydalanuvchi tasdig'i kerakmi?

    manual   → har doim True
    semi_auto → ALWAYS_CONFIRM_ACTIONS uchun True,
                boshqalar uchun faqat amount > SEMI_AUTO_FREE_LIMIT bo'lsa True
    full_auto → ALWAYS_CONFIRM_ACTIONS uchun True,
                boshqalar uchun faqat amount > user.ai_auto_price_limit bo'lsa True
    """
    autonomy = user.ai_autonomy_level

    if action_type in ALWAYS_CONFIRM_ACTIONS:
        return True

    if autonomy == 'manual':
        return True

    if autonomy == 'semi_auto':
        if amount and amount > SEMI_AUTO_FREE_LIMIT:
            return True
        return False

    if autonomy == 'full_auto':
        if amount and amount > user.ai_auto_price_limit:
            return True
        return False

    return True  # noma'lum daraja — ehtiyot uchun True


# ─── create_pending_action ────────────────────────────────────────────────────

def create_pending_action(
    user,
    session,
    action_type: str,
    service_type: str,
    payload: dict,
    amount: Decimal | None = None,
) -> 'AIActionLog':
    """
    AIActionLog(status='needs_confirmation') yozuvini yaratadi.
    Booking YARATILMAYDI — faqat "so'rov qilingan" holat saqlanadi.
    expires_at = now() + 5 daqiqa.
    """
    from .models import AIActionLog

    log = AIActionLog.objects.create(
        user=user,
        session=session,
        action_type=action_type,
        service_type=service_type,
        payload=payload,
        status=AIActionLog.ActionStatus.NEEDS_CONFIRMATION,
        amount_requiring_confirmation=amount,
        expires_at=timezone.now() + timedelta(minutes=CONFIRMATION_TTL_MINUTES),
    )
    logger.info(
        'Pending action yaratildi: id=%s, type=%s, user=%s, amount=%s',
        log.id, action_type, user.id, amount,
    )
    return log


# ─── confirm_pending_action ───────────────────────────────────────────────────

class ConfirmationError(Exception):
    """Tasdiqlash muvaffaqiyatsiz — sababi xabar ichida."""
    pass


def confirm_pending_action(
    action_log_id: str,
    user,
    confirmation_source: str,
) -> 'AIActionLog':
    """
    Frontend tugmasi bosilganda chaqiriladi.

    confirmation_source MAJBURIY va faqat 'frontend_button' qabul qilinadi.
    Chat xabaridan ("ha" deb yozish) kelgan chaqiruv rad etiladi.

    Tekshiruvlar:
    1. action_log shu user'ga tegishlimi
    2. status hali 'needs_confirmation'mi (ikki marta tasdiqlash mumkin emas)
    3. expires_at o'tmadimi

    Muvaffaqiyatli bo'lsa:
    - Haqiqiy booking/action bajariladi
    - status='success' ga o'tkaziladi
    """
    from .models import AIActionLog

    # confirmation_source tekshiruvi
    if confirmation_source != 'frontend_button':
        raise ConfirmationError(
            f"Tasdiqlash faqat frontend tugmasi orqali mumkin. "
            f"Kelgan manba: '{confirmation_source}'"
        )

    # Log topish
    try:
        log = AIActionLog.objects.select_for_update().get(id=action_log_id)
    except AIActionLog.DoesNotExist:
        raise ConfirmationError(f'AIActionLog topilmadi: {action_log_id}')

    # User tekshiruvi
    if log.user_id != user.id:
        logger.warning(
            'Boshqa user tasdiqlashga urindi: log.user=%s, request.user=%s',
            log.user_id, user.id,
        )
        raise ConfirmationError('Bu harakat sizga tegishli emas.')

    # Status tekshiruvi (ikki marta tasdiqlash oldini olish)
    if log.status != AIActionLog.ActionStatus.NEEDS_CONFIRMATION:
        raise ConfirmationError(
            f"Bu harakat allaqachon '{log.status}' holatida. "
            f"Qayta tasdiqlash mumkin emas."
        )

    # Muddati tekshiruvi
    if log.expires_at and timezone.now() > log.expires_at:
        log.status = AIActionLog.ActionStatus.FAILED
        log.error_message = 'Tasdiqlash muddati o\'tdi (5 daqiqa)'
        log.save(update_fields=['status', 'error_message', 'updated_at'])
        raise ConfirmationError(
            "Tasdiqlash muddati o'tib ketdi. Iltimos, qaytadan so'rang."
        )

    # ── Haqiqiy bajarish ──────────────────────────────────────────────────────
    try:
        result = _execute_confirmed_action(log, user)
        log.result = result
        log.status = AIActionLog.ActionStatus.SUCCESS
        log.save(update_fields=['result', 'status', 'updated_at'])
        logger.info(
            'Pending action tasdiqlandi va bajarildi: id=%s, type=%s, user=%s',
            log.id, log.action_type, user.id,
        )
    except Exception as e:
        log.status = AIActionLog.ActionStatus.FAILED
        log.error_message = str(e)
        log.save(update_fields=['status', 'error_message', 'updated_at'])
        logger.exception('Confirmed action bajarishda xato: id=%s — %s', log.id, e)
        raise ConfirmationError(f'Harakat bajarishda xato: {e}')

    return log


# ─── reject_pending_action ────────────────────────────────────────────────────

def reject_pending_action(action_log_id: str, user) -> 'AIActionLog':
    """Foydalanuvchi bekor qildi — status='cancelled_by_user'."""
    from .models import AIActionLog

    try:
        log = AIActionLog.objects.get(id=action_log_id, user=user)
    except AIActionLog.DoesNotExist:
        raise ConfirmationError('AIActionLog topilmadi yoki sizga tegishli emas.')

    if log.status != AIActionLog.ActionStatus.NEEDS_CONFIRMATION:
        raise ConfirmationError(f"Bekor qilib bo'lmaydi — holat: '{log.status}'")

    log.status = AIActionLog.ActionStatus.CANCELLED_BY_USER
    log.save(update_fields=['status', 'updated_at'])
    logger.info('Pending action bekor qilindi: id=%s, user=%s', log.id, user.id)
    return log


# ─── _execute_confirmed_action ────────────────────────────────────────────────

def _execute_confirmed_action(log: 'AIActionLog', user) -> dict:
    """
    Tasdiqlangan harakatni bajaradi.
    action_type va service_type ga qarab to'g'ri handler chaqiriladi.
    """
    action_type  = log.action_type
    service_type = log.service_type
    payload      = log.payload

    if action_type == 'book':
        return _execute_booking(service_type, user, log, payload)

    if action_type == 'cancel':
        from .tool_handlers import handle_cancel_booking
        return handle_cancel_booking(user=user, **payload)

    raise ValueError(f"Noma'lum action_type: '{action_type}'")


def _execute_booking(service_type: str, user, log: 'AIActionLog', payload: dict) -> dict:
    """Bron turига qarab tegishli handler chaqiriladi."""

    if service_type == 'flight':
        return _create_flight_booking(user, log, payload)

    if service_type == 'restaurant':
        return _create_restaurant_booking(user, log, payload)

    raise ValueError(f"Noma'lum service_type: '{service_type}'")


def _create_restaurant_booking(user, log: 'AIActionLog', payload: dict) -> dict:
    """Tasdiqlangan restoran bronini yaratadi."""
    from django.utils.dateparse import parse_datetime
    from apps.booking.models import Booking, RestaurantBooking, ServiceType, BookingStatus

    date   = payload.get('date', '')
    time   = payload.get('time', '')
    guests = payload.get('guests', 2)
    reservation_at = parse_datetime(f'{date}T{time}:00')

    booking = Booking.objects.create(
        user=user,
        service_type=ServiceType.RESTAURANT,
        status=BookingStatus.PENDING,
        title=f'Restoran — {date} {time}, {guests} kishi',
        booking_date=reservation_at,
        base_price=log.amount_requiring_confirmation or 0,
        final_price=log.amount_requiring_confirmation or 0,
        created_by_ai=True,
        ai_action_log=log,
    )
    branch = None
    try:
        from apps.crm.models import Branch
        branch = Branch.objects.get(id=payload.get('branch_id', ''))
    except Exception:
        pass

    RestaurantBooking.objects.create(
        booking=booking,
        branch=branch,
        reservation_at=reservation_at,
        guest_count=guests,
        special_requests=payload.get('special_requests', ''),
    )
    logger.info('Tasdiqlangan restoran broni yaratildi: booking=%s, user=%s', booking.id, user.id)
    return {
        'status':     'ok',
        'booking_id': str(booking.id),
        'message':    f"Restoran stoli muvaffaqiyatli band qilindi. Bron ID: {booking.id}",
    }


def _create_flight_booking(user, log: 'AIActionLog', payload: dict) -> dict:
    """
    Tasdiqlangan parvoz bronini yaratadi.
    BookharaAdapter mavjud bo'lsa — undan foydalanadi.
    Yo'q bo'lsa — DB'ga skeleton yozadi.
    """
    from django.utils.dateparse import parse_datetime
    from apps.booking.models import Booking, FlightBooking, ServiceType, BookingStatus

    offer_id   = payload.get('offer_id', '')
    passengers = payload.get('passengers', 1)

    from apps.integrations.errors import is_bookhara_configured

    ext_id = None
    bookhara_note = ''
    try:
        from apps.integrations.adapters.bookhara import BookharaAdapter

        if is_bookhara_configured():
            adapter = BookharaAdapter()
            result = adapter.create_booking(offer_id=offer_id, passengers=passengers)
            ext_id = result.external_booking_id if result.success else None
            if not ext_id:
                bookhara_note = (
                    'Aviachipta tizimi hozir javob bermadi — '
                    'bron saqlandi, menejer qo\'lda tekshiradi.'
                )
        else:
            bookhara_note = (
                'Aviachipta tizimi bilan bog\'lanishda kechikish — '
                'bron qayd etildi, menejer tez orada chiptani tasdiqlaydi.'
            )
    except Exception as exc:
        logger.warning('Bookhara booking xato: %s', exc)
        bookhara_note = (
            'Aviachipta tizimi vaqtincha ishlamayapti — '
            'bron saqlandi, menejer siz bilan bog\'lanadi.'
        )

    booking = Booking.objects.create(
        user=user,
        service_type=ServiceType.FLIGHT,
        status=BookingStatus.PENDING,
        title=f'Parvoz broni — {payload.get("origin", "?")}→{payload.get("destination", "?")}',
        base_price=log.amount_requiring_confirmation or 0,
        final_price=log.amount_requiring_confirmation or 0,
        created_by_ai=True,
        ai_action_log=log,
        external_booking_id=ext_id,
        external_provider='bookhara' if ext_id else '',
    )

    FlightBooking.objects.create(
        booking=booking,
        origin=payload.get('origin', ''),
        destination=payload.get('destination', ''),
        departure_at=(
            parse_datetime(payload.get('departure_at', ''))
            or timezone.now()
        ),
        passenger_count=passengers,
        seat_class=payload.get('seat_class', 'economy'),
    )

    logger.info(
        'Tasdiqlangan parvoz broni yaratildi: booking=%s, user=%s, ext_id=%s',
        booking.id, user.id, ext_id,
    )
    message = f"Parvoz broni yaratildi. Bron ID: {booking.id}"
    if bookhara_note and not ext_id:
        message = f"{message}\n\n⚠️ {bookhara_note}"
    return {
        'status':     'ok',
        'booking_id': str(booking.id),
        'message':    message,
    }
