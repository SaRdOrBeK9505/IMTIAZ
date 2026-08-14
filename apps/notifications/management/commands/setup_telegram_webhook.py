"""
Telegram Bot Webhook-ni sozlash uchun management command.

Ishlatish:
    python manage.py setup_telegram_webhook --url https://YOUR-DOMAIN.com
"""

from __future__ import annotations

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Telegram Bot Webhook-ni sozlash'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            required=True,
            help='VPS domeningiz URL-manzili (masalan: https://api.imtiaz.uz)',
        )

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError('TELEGRAM_BOT_TOKEN .env faylida sozlanmagan!')

        domain = options['url'].rstrip('/')
        webhook_url = f'{domain}/api/notifications/telegram/webhook/'
        secret = getattr(settings, 'TELEGRAM_BOT_SECRET', '')

        self.stdout.write(f'Webhook o\'rnatilmoqda: {webhook_url}')

        params = {'url': webhook_url}
        if secret:
            params['secret_token'] = secret

        try:
            resp = httpx.post(
                f'https://api.telegram.org/bot{token}/setWebhook',
                json=params,
                timeout=10,
            )
            data = resp.json()
            if data.get('ok'):
                self.stdout.write(self.style.SUCCESS('✅ Telegram Webhook muvaffaqiyatli o\'rnatildi!'))
                self.stdout.write(f"Natija: {data.get('description')}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ Webhook o'rnatishda xato: {data.get('description')}"))
        except Exception as e:
            raise CommandError(f'Telegram API ga ulanishda xato: {e}')
