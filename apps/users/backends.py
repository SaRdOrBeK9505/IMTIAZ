"""
Custom authentication backends.

PhoneBackend  — phone + password bilan kirish (API va Django admin).
                USERNAME_FIELD = 'phone' bo'lganligi uchun bu asosiy backend.

Ishlatilish tartibi (settings.py AUTHENTICATION_BACKENDS):
    1. apps.users.backends.PhoneBackend   — phone orqali
    2. django.contrib.auth.backends.ModelBackend  — zaxira
"""

from django.contrib.auth.backends import ModelBackend

from .models import User


class PhoneBackend(ModelBackend):
    """
    Telefon raqam + parol bilan autentifikatsiya.
    Django admin va API login uchun ishlaydi.
    """

    def authenticate(self, request, username: str = None, password: str = None, **kwargs):
        if not username or not password:
            return None

        # phone field bilan qidirish (+ belgisi bilan yoki usiz)
        phone = username.strip()
        if not phone.startswith('+'):
            phone = '+' + phone

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            # Timing attack dan himoya — parolni tekshirib qo'yamiz
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
