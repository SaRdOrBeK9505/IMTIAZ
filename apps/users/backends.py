"""
Custom authentication backend — admin panel uchun.
telegram_id yoki phone + parol bilan kirish imkonini beradi.
"""

from django.contrib.auth.backends import ModelBackend
from .models import User


class TelegramIDBackend(ModelBackend):
    """
    Django admin'ga telegram_id + parol bilan kirish.
    Login field'ga telegram_id yoziladi.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        try:
            # telegram_id raqam bo'lsa
            tid = int(username)
            user = User.objects.get(telegram_id=tid)
        except (ValueError, User.DoesNotExist):
            # phone bilan ham sinab ko'rish
            try:
                user = User.objects.get(phone=username)
            except User.DoesNotExist:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
