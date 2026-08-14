"""
Telegram bot webhook'ini BotFather orqali ro'yxatdan o'tkazish.

Ishlatish:
    python manage.py setup_telegram_webhook
    python manage.py setup_telegram_webhook --url https://api.imtiaz.uz/api/notifications/telegram/webhook/
    python manage.py setup_telegram_webhook --delete
"""

from __future__ import annotations

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Telegram bot webhook URL ni sozlaydi yoki o\'chiradi'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            default='',
            help='Webhook URL (default: joriy domen + /api/notifications/telegram/webhook/)',
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Webhook ni o\'chirish (polling rejimiga qaytish)',
        )

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError('TELEGRAM_BOT_TOKEN .env da sozlanmagan')

        base = f'https://api.telegram.org/bot{token}'

        if options['delete']:
            resp = httpx.post(f'{base}/deleteWebhook', timeout=15)
            data = resp.json()
            if not data.get('ok'):
                raise CommandError(data.get('description', 'deleteWebhook xato'))
            self.stdout.write(self.style.SUCCESS('Webhook o\'chirildi'))
            return

        webhook_url = options['url']
        if not webhook_url:
            allowed = settings.ALLOWED_HOSTS
            host = next((h for h in allowed if h not in ('localhost', '127.0.0.1', '*')), '')
            if not host:
                raise CommandError(
                    '--url bering yoki ALLOWED_HOSTS ga production domen qo\'shing'
                )
            webhook_url = f'https://{host}/api/notifications/telegram/webhook/'

        payload: dict = {'url': webhook_url}
        secret = settings.TELEGRAM_BOT_SECRET
        if secret:
            payload['secret_token'] = secret

        resp = httpx.post(f'{base}/setWebhook', json=payload, timeout=15)
        data = resp.json()
        if not data.get('ok'):
            raise CommandError(data.get('description', 'setWebhook xato'))

        self.stdout.write(self.style.SUCCESS(f'Webhook o\'rnatildi: {webhook_url}'))
