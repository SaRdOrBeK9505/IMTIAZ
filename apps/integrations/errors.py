"""
Tashqi integratsiyalar uchun foydalanuvchiga tushunarli xatoliklar.
"""

from __future__ import annotations


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
    """.env da kerakli kalitlar yo'q."""

    def __init__(self, provider: str, hint: str = ''):
        msg = (
            f"{provider} xizmati hozircha sozlanmagan. "
            f"Parvoz qidiruv vaqtincha mavjud emas."
        )
        if hint:
            msg = f"{msg} ({hint})"
        super().__init__(user_message=msg, error_code='not_configured', detail=hint)


class IntegrationUnavailableError(IntegrationError):
    """Xizmat sozlangan, lekin javob bermadi."""

    def __init__(self, provider: str, reason: str = ''):
        msg = (
            f"{provider} xizmati vaqtincha javob bermayapti. "
            f"Birozdan keyin qayta urinib ko'ring."
        )
        if reason:
            msg = f"{msg} Sabab: {reason}"
        super().__init__(user_message=msg, error_code='unavailable', detail=reason)


def is_bookhara_configured() -> bool:
    from django.conf import settings
    return bool(settings.BOOKHARA_EMAIL and settings.BOOKHARA_PASSWORD)


def integration_error_dict(exc: Exception, provider: str = 'Bookhara') -> dict:
    """Tool handler va API uchun standart xato javobi."""
    if isinstance(exc, IntegrationError):
        return {
            'status': 'error',
            'error_code': exc.error_code,
            'message': exc.user_message,
        }
    return {
        'status': 'error',
        'error_code': 'unavailable',
        'message': (
            f"{provider} xizmati bilan bog'lanishda muammo yuz berdi. "
            f"Keyinroq qayta urinib ko'ring."
        ),
    }
