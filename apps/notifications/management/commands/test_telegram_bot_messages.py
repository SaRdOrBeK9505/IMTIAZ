"""
Bot matnlarini ko'rish va test yuborish (management command).

Faqat matnlarni terminalda ko'rish:
    python manage.py test_telegram_bot_messages

Telegram'ga yuborish (o'z chat_id ingiz):
    python manage.py test_telegram_bot_messages --chat-id 123456789

Ruscha tilida test qilish:
    python manage.py test_telegram_bot_messages --chat-id 123456789 --lang ru

Telefon bo'yicha (User.telegram_id bo'lsa):
    python manage.py test_telegram_bot_messages --phone +998901234567

Faqat bitta bo'lim:
    python manage.py test_telegram_bot_messages --section welcome --chat-id 123456789
"""

from __future__ import annotations

import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ai_assistant.i18n import t
from apps.notifications.bot_content import (
    about_text,
    help_text,
    main_menu_keyboard,
    mini_app_ai_url,
    section_keyboard,
    services_text,
    welcome_text,
)
from apps.users.models import User


class Command(BaseCommand):
    help = 'Telegram bot matnlarini ko\'rsatadi va test yuboradi'

    def add_arguments(self, parser):
        parser.add_argument(
            '--chat-id',
            type=int,
            default=None,
            help='Telegram chat_id (yuborish uchun)',
        )
        parser.add_argument(
            '--phone',
            default='',
            help='Foydalanuvchi telefoni (+998...) — telegram_id olinadi',
        )
        parser.add_argument(
            '--lang',
            choices=['uz', 'ru', 'en'],
            default='uz',
            help='Matn tili (default: uz)',
        )
        parser.add_argument(
            '--first-name',
            default='Asilbek',
            help='Salomlashishda ishlatiladigan ism',
        )
        parser.add_argument(
            '--section',
            choices=['welcome', 'services', 'about', 'help', 'ai_welcome', 'all'],
            default='all',
            help='Qaysi bo\'lim matni (default: all)',
        )
        parser.add_argument(
            '--send',
            action='store_true',
            help='Telegram\'ga yuborish (--chat-id yoki --phone kerak)',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Xabarlar orasidagi pauza (sekund, default: 1)',
        )

    def handle(self, *args, **options):
        self._ensure_utf8_stdout()

        chat_id = options['chat_id']
        phone = (options['phone'] or '').strip()
        lang = options['lang']
        first_name = options['first_name']

        if phone and not chat_id:
            chat_id = self._resolve_chat_id(phone)

        section = options['section']

        sections_def = {
            'welcome': (
                '🌟 /start — Asosiy xabar (2x2 Grid)',
                lambda: welcome_text(first_name=first_name, lang=lang),
                lambda: main_menu_keyboard(lang=lang),
            ),
            'services': (
                '🧭 Xizmatlar bo\'limi',
                lambda: services_text(lang=lang),
                lambda: section_keyboard(lang=lang),
            ),
            'about': (
                'ℹ️ Biz haqimizda bo\'limi',
                lambda: about_text(lang=lang),
                lambda: section_keyboard(lang=lang),
            ),
            'help': (
                '💬 Yordam bo\'limi',
                lambda: help_text(lang=lang),
                lambda: section_keyboard(lang=lang),
            ),
            'ai_welcome': (
                '🤖 IMTIAZ AI birinchi kirish xabari',
                lambda: t('ai_welcome', lang),
                None,
            ),
        }

        sections = list(sections_def.keys()) if section == 'all' else [section]

        should_send = options['send'] or bool(chat_id)
        if should_send and not chat_id:
            raise CommandError(
                'Yuborish uchun --chat-id yoki --phone bering.\n'
                'Faqat ko\'rish: python manage.py test_telegram_bot_messages'
            )

        if should_send and not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError('TELEGRAM_BOT_TOKEN .env da sozlanmagan')

        bot = None
        if should_send:
            from apps.notifications.telegram import get_bot
            bot = get_bot()
            self.stdout.write(self.style.HTTP_INFO(
                f'Telegram\'ga yuborilmoqda → chat_id={chat_id}, lang={lang}\n'
            ))

        self.stdout.write(self.style.HTTP_INFO(
            f'Mini App AI URL: {mini_app_ai_url()}\n'
        ))
        self.stdout.write('=' * 60 + '\n')

        for key in sections:
            title, text_fn, kb_fn = sections_def[key]
            text = text_fn()
            kb = kb_fn() if kb_fn else None

            self._safe_write(f'\n[{key}] {title}', style=self.style.MIGRATE_HEADING)
            self._safe_write('-' * 60)
            self._safe_write(text)
            self._safe_write('-' * 60)

            if kb and 'inline_keyboard' in kb:
                self._safe_write('\nTugmalar:')
                for row in kb['inline_keyboard']:
                    labels = []
                    for btn in row:
                        if 'web_app' in btn:
                            labels.append(f"{btn['text']} → {btn['web_app']['url']}")
                        else:
                            labels.append(f"{btn['text']} ({btn['callback_data']})")
                    self._safe_write('  ' + ' | '.join(labels))

            if should_send and bot:
                msg_id = bot.send_message(chat_id, text, reply_markup=kb)
                if msg_id:
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ Yuborildi (message_id={msg_id})'
                    ))
                else:
                    self.stdout.write(self.style.ERROR('  ✗ Yuborilmadi'))
                if options['delay'] > 0 and key != sections[-1]:
                    time.sleep(options['delay'])

        self.stdout.write('')
        if should_send:
            self.stdout.write(self.style.SUCCESS('Tayyor — Telegram\'ni tekshiring.'))
        else:
            self.stdout.write(self.style.WARNING(
                'Faqat ko\'rsatildi. Yuborish: python manage.py test_telegram_bot_messages --chat-id YOUR_ID'
            ))

    @staticmethod
    def _resolve_chat_id(phone: str) -> int:
        user = User.objects.filter(phone=phone).first()
        if not user:
            raise CommandError(f'Foydalanuvchi topilmadi: {phone}')
        if not user.telegram_id:
            raise CommandError(
                f'{phone} uchun telegram_id yo\'q. '
                'Botda /start bosing yoki --chat-id bering.'
            )
        return user.telegram_id

    @staticmethod
    def _ensure_utf8_stdout() -> None:
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, 'reconfigure', None)
            if callable(reconfigure):
                try:
                    reconfigure(encoding='utf-8', errors='replace')
                except Exception:
                    pass

    def _safe_write(self, msg: str, style=None) -> None:
        try:
            if style:
                self.stdout.write(style(msg))
            else:
                self.stdout.write(msg)
        except UnicodeEncodeError:
            safe = msg.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(
                sys.stdout.encoding or 'utf-8', errors='replace'
            )
            if style:
                self.stdout.write(style(safe))
            else:
                self.stdout.write(safe)
