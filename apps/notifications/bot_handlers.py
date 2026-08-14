"""
Telegram bot update handler'lari — /start va inline tugmalar.
"""

from __future__ import annotations

import logging

from apps.users.models import User

from .bot_content import (
    CB_MENU,
    SECTION_TEXTS,
    main_menu_keyboard,
    section_keyboard,
    welcome_text,
)
from .telegram import get_bot

logger = logging.getLogger(__name__)


def handle_update(update: dict) -> None:
    """Telegram webhook update'ini qayta ishlaydi."""
    if 'message' in update:
        _handle_message(update['message'])
    elif 'callback_query' in update:
        _handle_callback(update['callback_query'])


def _handle_message(message: dict) -> None:
    text = (message.get('text') or '').strip()
    chat_id = message['chat']['id']

    if text.startswith('/start'):
        _handle_start(message)
        return

    tg_user = message.get('from') or {}
    lang, first_name = _get_user_info(chat_id, tg_user)

    bot = get_bot()
    bot.send_message(
        chat_id,
        welcome_text(first_name=first_name, lang=lang),
        reply_markup=main_menu_keyboard(lang=lang),
    )


def _handle_start(message: dict) -> None:
    chat_id = message['chat']['id']
    tg_user = message.get('from') or {}
    text_raw = (message.get('text') or '').strip()

    # Deep linking parsing (masalan: /start hotel_booking)
    parts = text_raw.split(maxsplit=1)
    start_param = parts[1] if len(parts) > 1 else 'ai_chat'

    _sync_telegram_profile(chat_id, tg_user)
    lang, first_name = _get_user_info(chat_id, tg_user)

    bot = get_bot()
    bot.send_message(
        chat_id,
        welcome_text(first_name=first_name, lang=lang),
        reply_markup=main_menu_keyboard(lang=lang, start_param=start_param),
    )


def _handle_callback(callback: dict) -> None:
    data = callback.get('data', '')
    message = callback.get('message') or {}
    chat_id = message.get('chat', {}).get('id')
    message_id = message.get('message_id')
    callback_id = callback.get('id')
    tg_user = callback.get('from') or {}

    bot = get_bot()
    bot.answer_callback_query(callback_id)

    if not chat_id or not message_id:
        return

    lang, first_name = _get_user_info(chat_id, tg_user)

    if data == CB_MENU:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=welcome_text(first_name=first_name, lang=lang),
            reply_markup=main_menu_keyboard(lang=lang),
        )
        return

    section_fn = SECTION_TEXTS.get(data)
    if section_fn:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=section_fn(lang=lang),
            reply_markup=section_keyboard(lang=lang),
        )


def _get_user_info(chat_id: int, tg_user: dict) -> tuple[str, str]:
    """User profilidan yoki Telegram updatedan til va ismni aniqlaydi."""
    user = User.objects.filter(telegram_id=chat_id).first()
    if user:
        lang = user.language_code or 'uz'
        first_name = user.first_name or tg_user.get('first_name', '')
    else:
        lang_code = (tg_user.get('language_code') or 'uz').split('-')[0].lower()
        lang = lang_code if lang_code in ('uz', 'ru', 'en') else 'uz'
        first_name = tg_user.get('first_name', '')
    return lang, first_name


def _sync_telegram_profile(chat_id: int, tg_user: dict) -> None:
    """Foydalanuvchi allaqachon ro'yxatdan o'tgan bo'lsa, telegram username yangilaydi."""
    username = tg_user.get('username')
    if not username:
        return

    updated = User.objects.filter(telegram_id=chat_id).update(
        telegram_username=username,
    )
    if updated:
        logger.debug('Telegram profil yangilandi: chat_id=%s', chat_id)
