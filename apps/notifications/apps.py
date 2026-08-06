from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'apps.notifications'
    verbose_name       = 'Bildirishnomalar'

    def ready(self):
        # Periodic tasks management.py orqali yoki
        # deploy vaqtida alohida management command bilan ro'yxatga olinadi.
        # AppConfig.ready() ichida DB query qilinmaydi — RuntimeWarning oldini olish.
        pass
