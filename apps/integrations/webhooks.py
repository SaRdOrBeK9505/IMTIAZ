"""
Bookhara webhook handler — bron holati o'zgarishi bildirishnomasi.

Endpoint: POST /api/webhooks/bookhara/status/

Xavfsizlik:
    1. X-Auth headeridan token olinadi
    2. f"{BOOKHARA_EMAIL}{booking_id}{BOOKHARA_WEBHOOK_SECRET}" qatori tuziladi
    3. SHA256 hash hisoblanib, Base64 formatga o'giriladi
    4. Hisoblangan qiymat X-Auth bilan taqqoslanadi (hmac.compare_digest — timing-safe)
    5. Mos kelmasa — 403 qaytariladi va log yoziladi

Payload strukturasi (Bookhara hujjatiga ko'ra):
    {
        "request_id": "...",
        "created_at": "...",
        "message": "...",
        "data": {
            "id": "<booking_id>",
            "status": "<provider_status>",
            ...
        }
    }

Muvaffaqiyatli tekshiruvdan so'ng:
    - booking_id bo'yicha FlightBooking topiladi
    - provider_status va Booking.status yangilanadi
    - Har doim 200 OK qaytariladi (Bookhara qayta yubormasligi uchun)
"""

from __future__ import annotations

import hashlib
import base64
import hmac
import logging

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from apps.integrations.adapters.bookhara import BOOKHARA_STATUS_MAP

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Integrations'],
    summary='Bookhara bron holati webhook',
    description='Bookhara provayderidan bron holati o\'zgarishi. Har doim 200 qaytariladi.',
    request=OpenApiTypes.OBJECT,
    responses={200: OpenApiResponse(description='Webhook qabul qilindi')},
)
@api_view(['POST'])
@permission_classes([AllowAny])
def bookhara_status_webhook(request: Request) -> Response:
    """
    Bookhara bron holati o'zgarishi webhook'i.
    Har doim 200 qaytariladi — Bookhara qayta yuborishdan to'xtatilsin.
    """
    payload = request.data

    # ── Payload ichidan data olish ────────────────────────────────────────
    # Bookhara barcha javoblarni "data" kaliti ichida yuboradi.
    # Ehtiyot uchun: agar to'g'ridan-to'g'ri yuborilsa ham ishlaydi.
    data = payload.get('data') or payload

    booking_id = (
        data.get('id')
        or data.get('booking_id')
        or data.get('bookingId')
    )

    # ── Signature tekshiruvi ──────────────────────────────────────────────
    # MUHIM: imzo booking_id asosida hisoblanadi, lekin booking_id yo'q bo'lsa
    # ham autentifikatsiyasiz so'rov 403 olishi kerak — "ignored" emas.
    received_auth = request.headers.get('X-Auth', '')

    if booking_id:
        expected_auth = _compute_signature(str(booking_id))
        auth_valid = bool(received_auth) and hmac.compare_digest(received_auth, expected_auth)
    else:
        auth_valid = False

    if not auth_valid:
        logger.warning(
            'Bookhara webhook: noto\'g\'ri X-Auth imzosi yoki booking_id yo\'q. '
            'booking_id=%s received_auth_prefix=%s',
            booking_id,
            (received_auth[:8] + '...') if received_auth else '(bo\'sh)',
        )
        return Response({'status': 'forbidden'}, status=403)

    if not booking_id:
        logger.warning('Bookhara webhook: booking_id topilmadi. payload=%s', payload)
        return Response({'status': 'ignored', 'reason': 'no booking_id'})

    # ── Holat yangilash ───────────────────────────────────────────────────
    provider_status = (
        data.get('status')
        or data.get('booking_status')
        or ''
    ).lower()

    internal_status = BOOKHARA_STATUS_MAP.get(provider_status)

    try:
        _update_booking(str(booking_id), provider_status, internal_status, payload)
    except Exception:  # noqa: BLE001
        logger.exception('Bookhara webhook: booking yangilashda xato. booking_id=%s', booking_id)

    logger.info(
        'Bookhara webhook qabul qilindi: booking_id=%s, status=%s -> %s',
        booking_id, provider_status, internal_status,
    )
    return Response({'status': 'ok'})


def _compute_signature(booking_id: str) -> str:
    """X-Auth imzosini hisoblaydi: SHA256(email + booking_id + secret) → Base64."""
    raw = f"{settings.BOOKHARA_EMAIL}{booking_id}{settings.BOOKHARA_WEBHOOK_SECRET}"
    digest = hashlib.sha256(raw.encode('utf-8')).digest()
    return base64.b64encode(digest).decode('utf-8')


def _update_booking(
    booking_id: str,
    provider_status: str,
    internal_status: str | None,
    payload: dict,
) -> None:
    """FlightBooking va Booking yozuvlarini yangilaydi."""
    from apps.booking.models import FlightBooking, BookingStatus

    try:
        flight_booking = FlightBooking.objects.select_related('booking').get(
            booking__external_booking_id=booking_id,
        )
    except FlightBooking.DoesNotExist:
        logger.warning('Bookhara webhook: FlightBooking topilmadi. booking_id=%s', booking_id)
        return
    except FlightBooking.MultipleObjectsReturned:
        logger.error('Bookhara webhook: bir nechta FlightBooking. booking_id=%s', booking_id)
        return

    # FlightBooking.provider_status yangilash
    flight_booking.provider_status   = provider_status
    flight_booking.provider_response = payload
    flight_booking.save(update_fields=['provider_status', 'provider_response', 'updated_at'])

    # Booking.status yangilash (faqat ma'lum holat bo'lsa)
    if internal_status:
        booking = flight_booking.booking
        status_map = {
            'pending':   BookingStatus.PENDING,
            'confirmed': BookingStatus.CONFIRMED,
            'cancelled': BookingStatus.CANCELLED,
            'refunded':  BookingStatus.REFUNDED,
        }
        new_status = status_map.get(internal_status)
        if new_status and booking.status != new_status:
            booking.status = new_status
            booking.save(update_fields=['status', 'updated_at'])
            logger.info(
                'Booking %s holati yangilandi: %s', booking.id, new_status,
            )
