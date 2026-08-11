"""
Tashqi integratsiyalar — xatoliklar.

Mijozga: professional concierge uslubida, texnik tafsilotlarsiz.
Log/dev: detail maydoni va logger.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """Tashqi xizmat bilan bog'lanishda xato."""

    user_message: str
    error_code: str

    def __init__(self, user_message: str, error_code: str = 'unavailable', detail: str = ''):
        self.user_message = user_message
        self.error_code = error_code
        self.detail = detail
        super().__init__(user_message)


class IntegrationNotConfiguredError(IntegrationError):
    """Dev: .env da kalitlar yo'q. Mijozga umumiy kechikish xabari ketadi."""

    def __init__(self, service: str = 'generic', *, detail: str = ''):
        super().__init__(
            user_message=customer_message(service, 'unavailable'),
            error_code='not_configured',
            detail=detail,
        )


class IntegrationUnavailableError(IntegrationError):
    """Xizmat sozlangan, lekin javob bermadi."""

    def __init__(self, service: str = 'generic', *, detail: str = ''):
        super().__init__(
            user_message=customer_message(service, 'unavailable'),
            error_code='unavailable',
            detail=detail,
        )


# ─── Mijozga ko'rinadigan matnlar (concierge uslubi) ─────────────────────────

def customer_message(service: str, error_code: str, **ctx) -> str:
    """Texnik tafsilotsiz, IMTIAZ concierge uslubida xabar."""
    builders = {
        'flight': _flight_message,
        'train':  _train_message,
    }
    builder = builders.get(service, _generic_message)
    return builder(error_code, **ctx)


def _flight_message(error_code: str, **ctx) -> str:
    origin = ctx.get('origin') or 'jo\'nash shahri'
    destination = ctx.get('destination') or 'manzil'
    date = ctx.get('departure_date') or ''
    date_line = f" ({date})" if date else ''

    return (
        f"Hozir {origin} → {destination}{date_line} bo'yicha onlayn parvoz "
        f"qidiruv vaqtincha mavjud emas — aviachiptalar tizimi bilan bog'lanishda "
        f"biroz kechikish bor.\n\n"
        f"Shu bilan birga sizga yordam bera olaman:\n"
        f"• Boshqa sana yoki yaqin aeroport bo'yicha variant ko'rib chiqish\n"
        f"• Sayohatingiz uchun restoran yoki tadbir bronlash\n"
        f"• Menejerimiz orqali chipta — biz siz uchun qo'lda tekshirib, "
        f"eng qulay variantni topamiz\n\n"
        f"Bir ozdan keyin avtomatik qidiruvni yana sinab ko'ramiz. "
        f"Hozir qaysi yo'nalish sizga qulayroq?"
    )


def _train_message(error_code: str, **ctx) -> str:
    origin = ctx.get('origin') or 'jo\'nash punkti'
    destination = ctx.get('destination') or 'manzil'

    return (
        f"Hozir {origin} → {destination} yo'nalishida poyezd qidiruv "
        f"vaqtincha ishlamayapti — bu xizmat tez orada ulab qo'yiladi.\n\n"
        f"Ayni paytda parvoz qidiruv, restoran bron yoki boshqa "
        f"IMTIAZ xizmatlari bilan yordam bera olaman. Nima qidiramiz?"
    )


def _generic_message(error_code: str, **ctx) -> str:
    return (
        "So'rovingizni hozir to'liq bajara olmadim — xizmat vaqtincha band "
        "yoki bog'lanishda kechikish bor.\n\n"
        "Boshqa yo'nalish, sana yoki xizmat turini sinab ko'ramizmi? "
        "Yoki menejerimiz siz bilan bog'lanishini tashkil qilay?"
    )


# ─── Tool handler javoblari ───────────────────────────────────────────────────

def flight_search_error(
    error_code: str,
    origin: str = '',
    destination: str = '',
    departure_date: str = '',
    detail: str = '',
) -> dict:
    if detail:
        logger.warning('Flight search xato [%s]: %s', error_code, detail)
    return {
        'status':         'error',
        'error_code':     error_code,
        'message':        customer_message(
            'flight', error_code,
            origin=origin, destination=destination, departure_date=departure_date,
        ),
        'origin':         origin,
        'destination':    destination,
        'departure_date': departure_date,
    }


def train_search_error(
    error_code: str,
    origin: str = '',
    destination: str = '',
    detail: str = '',
) -> dict:
    if detail:
        logger.warning('Train search xato [%s]: %s', error_code, detail)
    return {
        'status':  'error',
        'error_code': error_code,
        'message': customer_message(
            'train', error_code, origin=origin, destination=destination,
        ),
    }


def integration_error_dict(
    exc: Exception,
    service: str = 'generic',
    **ctx,
) -> dict:
    """Exception → mijozga tushunarli dict."""
    if isinstance(exc, IntegrationError):
        if exc.detail:
            logger.warning('Integration xato [%s]: %s', exc.error_code, exc.detail)
        # IntegrationError allaqachon customer message bilan yaratilgan
        msg = exc.user_message
        # Flight/train uchun context bilan boyitish
        if service in ('flight', 'train') and ctx:
            msg = customer_message(service, exc.error_code, **ctx)
        return {
            'status':     'error',
            'error_code': exc.error_code,
            'message':    msg,
        }
    logger.exception('Integration kutilmagan xato: %s', exc)
    return {
        'status':     'error',
        'error_code': 'unavailable',
        'message':    customer_message(service, 'unavailable', **ctx),
    }


def is_bookhara_configured() -> bool:
    from django.conf import settings
    return bool(settings.BOOKHARA_EMAIL and settings.BOOKHARA_PASSWORD)
