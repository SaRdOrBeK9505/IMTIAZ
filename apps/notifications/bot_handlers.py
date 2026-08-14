"""
Telegram bot update handler'lari — /start va inline tugmalar.
"""

from __future__ import annotations

import logging

from apps.ai_assistant.services import AIAssistantService
from apps.users.models import User, UserRole

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

    if not text:
        return

    tg_user = message.get('from') or {}
    bot = get_bot()

    # Telegram'da "typing..." statusini ko'rsatish
    bot.send_chat_action(chat_id, 'typing')

    # Foydalanuvchini olish yoki avtomatik yaratish
    user = _get_or_create_user(chat_id, tg_user)
    lang = user.language_code or 'uz'

    try:
        ai_service = AIAssistantService()
        result = ai_service.chat(user=user, message=text)
        reply_content = result.get('content') or ''

        if result.get('requires_confirmation'):
            if lang == 'ru':
                note = "\n\n📌 <i>Для подтверждения этого действия перейдите в Mini App:</i>"
            elif lang == 'en':
                note = "\n\n📌 <i>To confirm this action, please proceed to the Mini App:</i>"
            else:
                note = "\n\n📌 <i>Ushbu amallarni tasdiqlash uchun Mini App ga o'ting:</i>"
            reply_content += note

        _send_split_message(bot, chat_id, reply_content, reply_markup=main_menu_keyboard(lang=lang))

    except Exception as e:
        logger.exception('Bot AI message error: %s', e)
        if lang == 'ru':
            err_msg = "Извините, произошла ошибка при обработке вашего запроса. Попробуйте позже."
        elif lang == 'en':
            err_msg = "Sorry, an error occurred while processing your request. Please try again later."
        else:
            err_msg = "Kechirasiz, so'rovingizni qayta ishlashda xatolik yuz berdi. Iltimos, bir ozdan so'ng qayta urinib ko'ring."
        bot.send_message(chat_id, err_msg, reply_markup=main_menu_keyboard(lang=lang))


def _send_split_message(bot, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    """Telegram 4096 belgilik cheklovini hisobga olib xabarni bo'lib yuboradi."""
    max_len = 4000
    if len(text) <= max_len:
        bot.send_message(chat_id, text, reply_markup=reply_markup)
        return

    chunks = [text[i:i + max_len] for i in range(0, len(text), max_len)]
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        bot.send_message(chat_id, chunk, reply_markup=markup)


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
    username = tg_user.get('username')
    user = User.objects.filter(telegram_id=chat_id).first()

    if not user and username:
        user = User.objects.filter(telegram_username__iexact=username).first()
        if user:
            user.telegram_id = chat_id
            user.save(update_fields=['telegram_id'])

    if user:
        lang = user.language_code or 'uz'
        first_name = user.first_name or tg_user.get('first_name', '')
    else:
        lang_code = (tg_user.get('language_code') or 'uz').split('-')[0].lower()
        lang = lang_code if lang_code in ('uz', 'ru', 'en') else 'uz'
        first_name = tg_user.get('first_name', '')
    return lang, first_name


def _sync_telegram_profile(chat_id: int, tg_user: dict) -> None:
    """Foydalanuvchi allaqachon ro'yxatdan o'tgan bo'lsa, telegram username va id ni yangilaydi."""
    username = tg_user.get('username')
    if not username:
        return

    user = User.objects.filter(telegram_id=chat_id).first()
    if user:
        if user.telegram_username != username:
            user.telegram_username = username
            user.save(update_fields=['telegram_username'])
    else:
        User.objects.filter(telegram_username__iexact=username, telegram_id__isnull=True).update(
            telegram_id=chat_id,
        )


def _get_or_create_user(chat_id: int, tg_user: dict) -> User:
    """Chat ID bo'yicha User topadi yoki yangi Telegram mijoz yaratadi."""
    username = tg_user.get('username')
    user = User.objects.filter(telegram_id=chat_id).first()

    if not user and username:
        user = User.objects.filter(telegram_username__iexact=username).first()
        if user:
            user.telegram_id = chat_id
            user.save(update_fields=['telegram_id'])

    if not user:
        first_name = tg_user.get('first_name', '') or f'User_{chat_id}'
        last_name = tg_user.get('last_name', '')
        lang_code = (tg_user.get('language_code') or 'uz').split('-')[0].lower()
        lang = lang_code if lang_code in ('uz', 'ru', 'en') else 'uz'
        phone_placeholder = f'+tg_{chat_id}'

        user = User.objects.create(
            phone=phone_placeholder,
            telegram_id=chat_id,
            telegram_username=username or None,
            first_name=first_name,
            last_name=last_name,
            language_code=lang,
            role=UserRole.CUSTOMER,
        )

    return user


