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

    def __init__(self, service: str = 'generic', *, detail: str = '', lang: str = 'uz'):
        super().__init__(
            user_message=customer_message(service, 'unavailable', lang=lang),
            error_code='not_configured',
            detail=detail,
        )


class IntegrationUnavailableError(IntegrationError):
    """Xizmat sozlangan, lekin javob bermadi."""

    def __init__(self, service: str = 'generic', *, detail: str = '', lang: str = 'uz'):
        super().__init__(
            user_message=customer_message(service, 'unavailable', lang=lang),
            error_code='unavailable',
            detail=detail,
        )


# ─── Mijozga ko'rinadigan matnlar (concierge uslubi) ─────────────────────────

def customer_message(service: str, error_code: str, lang: str = 'uz', **ctx) -> str:
    """Texnik tafsilotsiz, IMTIAZ concierge uslubida xabar."""
    from apps.ai_assistant.i18n import normalize_language, t

    lang = normalize_language(lang)

    if service == 'flight':
        origin = ctx.get('origin') or t('origin_default', lang)
        destination = ctx.get('destination') or t('destination_default', lang)
        date = ctx.get('departure_date') or ''
        date_line = f" ({date})" if date else ''
        if error_code == 'past_date':
            from datetime import timedelta
            from django.utils import timezone
            tomorrow_hint = (timezone.now().date() + timedelta(days=1)).isoformat()
            return t(
                'flight_past_date', lang,
                date=date,
                tomorrow_hint=tomorrow_hint,
            )
        if error_code == 'invalid_date':
            return t('flight_invalid_date', lang)
        return t(
            'flight_unavailable', lang,
            origin=origin,
            destination=destination,
            date_line=date_line,
        )

    if service == 'train':
        origin = ctx.get('origin') or t('origin_train_default', lang)
        destination = ctx.get('destination') or t('destination_default', lang)
        return t('train_unavailable', lang, origin=origin, destination=destination)

    return t('integration_generic', lang)


# ─── Tool handler javoblari ───────────────────────────────────────────────────

def flight_search_error(
    error_code: str,
    origin: str = '',
    destination: str = '',
    departure_date: str = '',
    detail: str = '',
    lang: str = 'uz',
) -> dict:
    if detail:
        logger.warning('Flight search xato [%s]: %s', error_code, detail)
    return {
        'status':         'error',
        'error_code':     error_code,
        'message':        customer_message(
            'flight', error_code, lang=lang,
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
    lang: str = 'uz',
) -> dict:
    if detail:
        logger.warning('Train search xato [%s]: %s', error_code, detail)
    return {
        'status':  'error',
        'error_code': error_code,
        'message': customer_message(
            'train', error_code, lang=lang,
            origin=origin, destination=destination,
        ),
    }


def integration_error_dict(
    exc: Exception,
    service: str = 'generic',
    lang: str = 'uz',
    **ctx,
) -> dict:
    """Exception → mijozga tushunarli dict."""
    if isinstance(exc, IntegrationError):
        if exc.detail:
            logger.warning('Integration xato [%s]: %s', exc.error_code, exc.detail)
        msg = exc.user_message
        if service in ('flight', 'train') and ctx:
            msg = customer_message(service, exc.error_code, lang=lang, **ctx)
        return {
            'status':     'error',
            'error_code': exc.error_code,
            'message':    msg,
        }
    logger.exception('Integration kutilmagan xato: %s', exc)
    return {
        'status':     'error',
        'error_code': 'unavailable',
        'message':    customer_message(service, 'unavailable', lang=lang, **ctx),
    }


def is_bookhara_configured() -> bool:
    from django.conf import settings
    return bool(settings.BOOKHARA_EMAIL and settings.BOOKHARA_PASSWORD)
