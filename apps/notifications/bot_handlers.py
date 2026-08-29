"""
Telegram bot update handler'lari — /start va inline tugmalar.
"""

from __future__ import annotations

import logging

from apps.ai_assistant.services import AIAssistantService
from apps.users.models import User, UserRole

from .bot_content import (
    CB_MENU,
    CB_SERVICES,
    CB_SERVICE_TRAVEL,
    CB_SERVICE_RESTAURANT,
    CB_SERVICE_ROADSIDE,
    CB_SERVICE_MEDICAL,
    CB_SERVICE_INSURANCE,
    CB_SERVICE_FAMILY_OFFICE,
    CB_SERVICE_LEISURE,
    CB_SERVICE_DISCOUNTS,
    SECTION_TEXTS,
    hide_keyboard,
    main_menu_keyboard,
    quick_services_hint_text,
    quick_services_reply_keyboard,
    section_keyboard,
    services_menu_keyboard,
    service_selection_text,
    welcome_text,
)
from .telegram import get_bot

logger = logging.getLogger(__name__)

# Reply keyboard tugmalari (xizmatlar) -> callback data. Modul darajasida bir marta
# yaratiladi, har xabarda qayta qurilmaydi.
SERVICE_TEXT_MAPPING = {
    '✈️ Sayohatlar': CB_SERVICE_TRAVEL,
    '🍽️ Stol band qilish': CB_SERVICE_RESTAURANT,
    '🚗 Yo\'lda yordam': CB_SERVICE_ROADSIDE,
    '❤️ Tibbiyot': CB_SERVICE_MEDICAL,
    '🛡️ Sug\'urta': CB_SERVICE_INSURANCE,
    '💼 Oilaviy ofis': CB_SERVICE_FAMILY_OFFICE,
    '🎭 Dam olish': CB_SERVICE_LEISURE,
    '🏷️ Mening chegirmalarim': CB_SERVICE_DISCOUNTS,
    '✈️ Путешествия': CB_SERVICE_TRAVEL,
    '🍽️ Столики': CB_SERVICE_RESTAURANT,
    '🚗 Помощь в дороге': CB_SERVICE_ROADSIDE,
    '❤️ Медицина': CB_SERVICE_MEDICAL,
    '🛡️ Страхование': CB_SERVICE_INSURANCE,
    '💼 Семейный офис': CB_SERVICE_FAMILY_OFFICE,
    '🎭 Отдых': CB_SERVICE_LEISURE,
    '🏷️ Мои скидки': CB_SERVICE_DISCOUNTS,
    '✈️ Travel': CB_SERVICE_TRAVEL,
    '🍽️ Dining': CB_SERVICE_RESTAURANT,
    '🚗 Roadside Assist': CB_SERVICE_ROADSIDE,
    '❤️ Medical': CB_SERVICE_MEDICAL,
    '🛡️ Insurance': CB_SERVICE_INSURANCE,
    '💼 Family Office': CB_SERVICE_FAMILY_OFFICE,
    '🎭 Leisure': CB_SERVICE_LEISURE,
    '🏷️ My Discounts': CB_SERVICE_DISCOUNTS,
}


def handle_update(update: dict) -> None:
    """Telegram webhook update'ini qayta ishlaydi."""
    if 'message' in update:
        _handle_message(update['message'])
    elif 'callback_query' in update:
        _handle_callback(update['callback_query'])


def _handle_message(message: dict) -> None:
    chat = message.get('chat') or {}
    chat_id = chat.get('id')
    if not chat_id:
        return

    chat_type = chat.get('type')
    # Guruh va kanallardan kelgan xabarlarni inkor qilish.
    # Bot faqat lead/bildirishnomalarni yuboradi, guruhdagi suhbatlarga javob bermaydi.
    if chat_type in ('group', 'supergroup', 'channel') or (isinstance(chat_id, int) and chat_id < 0):
        logger.info("Guruh/kanal xabari inkor qilindi: chat_id=%s, type=%s", chat_id, chat_type)
        return

    text = (message.get('text') or '').strip()

    if text.startswith('/start'):
        _handle_start(message)
        return

    if not text:
        return

    # MUHIM: tg_user, user va lang service_mapping tekshiruvidan OLDIN aniqlanishi kerak,
    # aks holda "✈️ Sayohatlar" kabi reply-keyboard tugmasi bosilganda
    # UnboundLocalError (lang/tg_user hali mavjud emas) yuzaga kelardi.
    tg_user = message.get('from') or {}
    bot = get_bot()
    user = _get_or_create_user(chat_id, tg_user)
    lang = user.language_code or 'uz'

    if text in SERVICE_TEXT_MAPPING:
        # Reply keyboard tugmasi bosildi - callback sifatida qayta ishlash
        callback_data = SERVICE_TEXT_MAPPING[text]
        _handle_service_callback(bot, chat_id, None, callback_data, lang, tg_user)
        return

    # Telegram'da "typing..." statusini ko'rsatish
    bot.send_chat_action(chat_id, 'typing')

    try:
        ai_service = AIAssistantService()
        result = ai_service.chat(user=user, message=text, for_bot=True)
        reply_content = result.get('content') or ''

        if result.get('requires_confirmation'):
            if lang == 'ru':
                note = "\n\n📌 <i>Для подтверждения этого действия перейдите в Mini App:</i>"
            elif lang == 'en':
                note = "\n\n📌 <i>To confirm this action, please proceed to the Mini App:</i>"
            else:
                note = "\n\n📌 <i>Ushbu amallarni tasdiqlash uchun Mini App ga o'ting:</i>"
            reply_content += note

        # AI javobini bo'lib-bo'lib yuborish (Mira AI streaming effekti)
        _send_streaming_response(bot, chat_id, reply_content, lang=lang)

    except Exception as e:
        logger.exception('Bot AI message error: %s', e)
        if lang == 'ru':
            err_msg = "Извините, произошла ошибка при обработке вашего запроса. Попробуйте позже."
        elif lang == 'en':
            err_msg = "Sorry, an error occurred while processing your request. Please try again later."
        else:
            err_msg = "Kechirasiz, so'rovingizni qayta ishlashda xatolik yuz berdi. Iltimos, bir ozdan so'ng qayta urinib ko'ring."
        bot.send_message(chat_id, err_msg, reply_markup=None)


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
    user = _get_or_create_user(chat_id, tg_user)
    # /start chaqirilganda eski aktiv suhbat sessiyasini yangilash uchun is_active=False qilamiz
    from apps.ai_assistant.models import ConversationSession
    ConversationSession.objects.filter(user=user, is_active=True).update(is_active=False)

    lang, first_name = _get_user_info(chat_id, tg_user)

    bot = get_bot()
    bot.send_message(
        chat_id,
        welcome_text(first_name=first_name, lang=lang),
        reply_markup=main_menu_keyboard(lang=lang, start_param=start_param),
    )

    # MUHIM: Telegram bitta xabarda inline VA reply keyboard'ni birga
    # qo'llashga ruxsat bermaydi (reply_markup faqat bittasi bo'lishi mumkin).
    # Shu sabab, eng ko'p ishlatiladigan 4 ta xizmatni (Sayohatlar, Stol band
    # qilish, Yo'lda yordam, Tibbiyot) pastki doimiy klaviaturada ko'rsatish
    # uchun alohida, qisqa ikkinchi xabar yuboramiz.
    bot.send_message(
        chat_id,
        quick_services_hint_text(lang=lang),
        reply_markup=quick_services_reply_keyboard(lang=lang),
    )


def _handle_callback(callback: dict) -> None:
    # Lead status callbacklarini guruh va kanallardan qat'i nazar birinchi navbatda qayta ishlash
    if _handle_lead_status_callback(callback):
        return

    data = callback.get('data', '')
    message = callback.get('message') or {}
    chat = message.get('chat') or {}
    chat_id = chat.get('id')
    chat_type = chat.get('type')

    if not chat_id:
        return

    if chat_type in ('group', 'supergroup', 'channel') or (isinstance(chat_id, int) and chat_id < 0):
        return

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

    if data == CB_SERVICES:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=service_selection_text(lang=lang),
            reply_markup=services_menu_keyboard(lang=lang),
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
        return

    # Xizmatlar callback'lari
    _handle_service_callback(bot, chat_id, message_id, data, lang, tg_user)


def _handle_service_callback(bot, chat_id: int, message_id: int | None, data: str, lang: str, tg_user: dict) -> None:
    """Xizmat tanlanganda lead yig'ish jarayonini boshlaydi."""
    service_prompts = {
        CB_SERVICE_TRAVEL: {
            'uz': '✈️ <b>Sayohatlar</b>\n\nQaysi yo\'nalishga sayohat qilmoqchisiz? (masalan: Dubay, Turkiya, Maldiv)',
            'ru': '✈️ <b>Путешествия</b>\n\nВ какое направление вы хотите отправиться? (например: Дубай, Турция, Мальдивы)',
            'en': '✈️ <b>Travel</b>\n\nWhich destination would you like to travel to? (e.g., Dubai, Turkey, Maldives)',
        },
        CB_SERVICE_RESTAURANT: {
            'uz': '🍽️ <b>Stol band qilish</b>\n\nQaysi restoranda stol band qilmoqchisiz? (masalan: Nobu, Chayhona)',
            'ru': '🍽️ <b>Бронирование столика</b>\n\nВ каком ресторане вы хотите забронировать столик? (например: Nobu, Chayhona)',
            'en': '🍽️ <b>Table Reservation</b>\n\nWhich restaurant would you like to reserve a table at? (e.g., Nobu, Chayhona)',
        },
        CB_SERVICE_ROADSIDE: {
            'uz': '🚗 <b>Yo\'lda yordam</b>\n\nQaysi xizmat kerak? (masalan: evakuator, yoqilg\'i yetkazib berish)',
            'ru': '🚗 <b>Помощь в дороге</b>\n\nКакая услуга вам нужна? (например: эвакуатор, доставка топлива)',
            'en': '🚗 <b>Roadside Assistance</b>\n\nWhat service do you need? (e.g., tow truck, fuel delivery)',
        },
        CB_SERVICE_MEDICAL: {
            'uz': '❤️ <b>Tibbiyot</b>\n\nQanday tibbiy xizmat kerak? (masalan: shifokor konsultatsiyasi, diagnostika)',
            'ru': '❤️ <b>Медицина</b>\n\nКакая медицинская услуга вам нужна? (например: консультация врача, диагностика)',
            'en': '❤️ <b>Medical</b>\n\nWhat medical service do you need? (e.g., doctor consultation, diagnostics)',
        },
        CB_SERVICE_INSURANCE: {
            'uz': '🛡️ <b>Sug\'urta</b>\n\nQanday sug\'urta turini xohlaysiz? (masalan: sayohat sug\'urtasi, sog\'liq sug\'urtasi)',
            'ru': '🛡️ <b>Страхование</b>\n\nКакой тип страховки вы хотите? (например: туристическая, медицинская)',
            'en': '🛡️ <b>Insurance</b>\n\nWhat type of insurance do you want? (e.g., travel insurance, health insurance)',
        },
        CB_SERVICE_FAMILY_OFFICE: {
            'uz': '💼 <b>Oilaviy ofis</b>\n\nQanday moliyaviy xizmat kerak? (masalan: investitsiya maslahat, aktivlarni boshqarish)',
            'ru': '💼 <b>Семейный офис</b>\n\nКакая финансовая услуга вам нужна? (например: инвестиционный консалтинг, управление активами)',
            'en': '💼 <b>Family Office</b>\n\nWhat financial service do you need? (e.g., investment advisory, asset management)',
        },
        CB_SERVICE_LEISURE: {
            'uz': '🎭 <b>Dam olish</b>\n\nQanday tadbir yoki ko\'ngilochar xizmat kerak? (masalan: konsert, teatr, sport tadbiri)',
            'ru': '🎭 <b>Отдых</b>\n\nКакое мероприятие или развлечение вас интересует? (например: концерт, театр, спортивное событие)',
            'en': '🎭 <b>Leisure</b>\n\nWhat event or entertainment service do you need? (e.g., concert, theater, sports event)',
        },
        CB_SERVICE_DISCOUNTS: {
            'uz': '🏷️ <b>Mening chegirmalarim</b>\n\nSizning shaxsiy chegirmalaringiz va maxsus takliflaringiz AI yordamchisi orqali boshqariladi. Quyidagi tugmani bosing:',
            'ru': '🏷️ <b>Мои скидки</b>\n\nВаши персональные скидки и специальные предложения управляются через AI-помощника. Нажмите кнопку ниже:',
            'en': '🏷️ <b>My Discounts</b>\n\nYour personal discounts and special offers are managed via AI assistant. Tap the button below:',
        },
    }

    prompt_data = service_prompts.get(data)
    if not prompt_data:
        return

    prompt_text = prompt_data.get(lang, prompt_data.get('uz', ''))

    # Avval prompt matnini ko'rsatamiz va ESKI inline tugmalarni tozalaymiz.
    # MUHIM: edit_message_text ga reply_markup aniq berilmasa, Telegram oldingi
    # xabardagi inline_keyboard'ni (8 ta xizmat tugmasi) saqlab qoladi — shuning
    # uchun bo'sh reply_markup={'inline_keyboard': []} yuboramiz.
    if message_id:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=prompt_text,
                parse_mode='HTML',
                reply_markup={'inline_keyboard': []},
            )
        except Exception:
            logger.exception('Xizmat prompt matnini tahrirlashda xatolik: chat_id=%s', chat_id)
    else:
        bot.send_message(chat_id, prompt_text, parse_mode='HTML')

    bot.send_chat_action(chat_id, 'typing')

    user = _get_or_create_user(chat_id, tg_user)

    # Xizmat turi AI ga ma'lum qilish uchun maxsus prefiks
    service_context = {
        CB_SERVICE_TRAVEL: "Foydalanuvchi sayohat xizmatiga qiziqmoqda. ",
        CB_SERVICE_RESTAURANT: "Foydalanuvchi restoran bron qilmoqchi. ",
        CB_SERVICE_ROADSIDE: "Foydalanuvchi yo'lda yordam xizmatiga muhtoj. ",
        CB_SERVICE_MEDICAL: "Foydalanuvchi tibbiy xizmatga muhtoj. ",
        CB_SERVICE_INSURANCE: "Foydalanuvchi sug'urta xizmatiga qiziqmoqda. ",
        CB_SERVICE_FAMILY_OFFICE: "Foydalanuvchi oilaviy ofis xizmatiga qiziqmoqda. ",
        CB_SERVICE_LEISURE: "Foydalanuvchi dam olish tadbirlariga qiziqmoqda. ",
        CB_SERVICE_DISCOUNTS: "Foydalanuvchi chegirmalar haqida ma'lumot olmoqchi. ",
    }

    context_prefix = service_context.get(data, "")
    full_message = context_prefix + prompt_text

    # MUHIM: AI chaqiruvi try/except ichiga olindi. Avval bu yerda himoya yo'q edi —
    # AIAssistantService xatolik bersa, jarayon jim tugab, foydalanuvchi hech qanday
    # javob olmasdi (aynan "Xizmatlar" bosilgach reply chiqmasligi shundan edi).
    try:
        ai_service = AIAssistantService()
        result = ai_service.chat(user=user, message=full_message, for_bot=True)
        reply_content = result.get('content') or ''
        if not reply_content:
            raise ValueError('AIAssistantService bo\'sh javob qaytardi')
    except Exception as e:
        logger.exception('Xizmat callback uchun AI javobida xatolik: data=%s, chat_id=%s, %s', data, chat_id, e)
        if lang == 'ru':
            reply_content = "Извините, произошла ошибка при обработке вашего запроса. Попробуйте позже."
        elif lang == 'en':
            reply_content = "Sorry, an error occurred while processing your request. Please try again later."
        else:
            reply_content = "Kechirasiz, so'rovingizni qayta ishlashda xatolik yuz berdi. Iltimos, bir ozdan so'ng qayta urinib ko'ring."

    # AI javobini Mira AI uslubida streaming qilib yuborish
    _send_streaming_response(bot, chat_id, reply_content, lang=lang)


def _send_streaming_response(bot, chat_id: int, text: str, lang: str = 'uz', reply_markup: dict | None = None) -> None:
    """
    Javobni Mira AI uslubida bosqichma-bosqich chiqarish.

    TUZATISH #1 (avvalgi bug):
    - Eski versiya HAR HARF uchun edit_message_text chaqirardi (~40-60 so'rov/sek).
      Telegram editMessageText uchun bitta xabarga taxminan 1 so'rov/sekund
      chegarasi bor -> bu darhol 429 (Too Many Requests) ga olib kelardi va
      time.sleep() bilan birga butun so'rov o'nlab soniyalarga bloklanib qolardi.
    - Bu esa TelegramWebhookView'ni juda uzoq ushlab turardi -> Telegram javobni
      kutolmay o'sha update'ni QAYTA yuborardi -> bot foydalanuvchiga bir xabarni
      bir necha marta "takrorlagandek" ko'rinardi (masalan uchinchi "salom"dan
      keyingi holat).
    - Yangi versiya: matn so'z-so'z yig'iladi, lekin Telegram'ga edit so'rovi
      FAQAT ~0.7 soniyada bir marta yuboriladi (vaqt bo'yicha throttle).
      Natijada bor-yo'g'i bir necha o'nlab so'rov ketadi, rate-limit va
      bloklanish muammosi yo'qoladi, animatsiya effekti esa saqlanadi.

    TUZATISH #2 (bu versiyada qo'shildi):
    - AI javobi 4096 belgidan (Telegram xabar limiti) uzun bo'lsa, oldingi versiya
      edit_message_text'ga uzun matn yuborib xatolikka uchrardi va streaming
      "..." holatida to'xtab qolardi (except: pass uni yutib yuborardi, lekin
      foydalanuvchi hech qachon to'liq javobni ko'rmasdi).
    - Endi matn avval MAX_MSG_LEN bo'yicha bloklarga bo'linadi. Har bir blok
      o'z alohida xabarida so'z-so'z streaming qilib chiqariladi, ketma-ket.
      Tugmalar (reply_markup) faqat ENG OXIRGI blokning oxirgi xabariga
      qo'shiladi.
    """
    import time

    if not text:
        return

    # Juda qisqa javobni to'g'ridan-to'g'ri yuborish
    if len(text) < 50:
        bot.send_message(chat_id, text, reply_markup=reply_markup)
        return

    bot.send_chat_action(chat_id, 'typing')

    # Telegram xabar limiti (4096) dan xavfsiz masofada bo'lish uchun 4000 belgi
    MAX_MSG_LEN = 4000
    # Telegram editMessageText uchun xavfsiz oraliq (sekundlarda).
    # ~1 so'rov/sekund chegarasidan pastroq tutish uchun 0.7s tanlandi.
    EDIT_INTERVAL = 0.7

    chunks = [text[i:i + MAX_MSG_LEN] for i in range(0, len(text), MAX_MSG_LEN)]

    last_typing_action = time.monotonic()

    for chunk_index, chunk_text in enumerate(chunks):
        is_last_chunk = (chunk_index == len(chunks) - 1)

        # Har bir blok uchun alohida "..." xabari boshlanadi
        message = bot.send_message(chat_id, '...')

        if isinstance(message, dict):
            message_id = message.get('message_id')
        elif isinstance(message, int):
            message_id = message
        else:
            message_id = None

        if not message_id:
            # message_id olinmasa, shu blokni oddiy yuborib, keyingi blokka o'tamiz
            bot.send_message(
                chat_id,
                chunk_text,
                reply_markup=reply_markup if is_last_chunk else None,
            )
            continue

        words = chunk_text.split(' ')
        current_text = ''
        last_edit_time = time.monotonic()

        for i, word in enumerate(words):
            current_text += (word if i == 0 else ' ' + word)
            is_last_word = (i == len(words) - 1)

            now = time.monotonic()

            # Typing indicatorni har 4-5 sekunddan keyin qayta yuborish
            if now - last_typing_action > 4.5:
                try:
                    bot.send_chat_action(chat_id, 'typing')
                except Exception:
                    pass
                last_typing_action = now

            # Faqat EDIT_INTERVAL o'tgandan keyin YOKI oxirgi so'zda edit qilamiz —
            # bu Telegram rate-limit'ini buzmaydi va webhook'ni uzoq bloklamaydi.
            if is_last_word or (now - last_edit_time >= EDIT_INTERVAL):
                try:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=current_text,
                    )
                except Exception:
                    # 429 yoki "message is not modified" bo'lishi mumkin — davom etamiz
                    pass
                last_edit_time = now

        # Tugmalarni faqat eng oxirgi blokning oxirgi xabariga qo'shamiz
        if is_last_chunk and reply_markup:
            try:
                bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup,
                )
            except Exception:
                pass


def _handle_lead_status_callback(callback: dict) -> bool:
    """
    Lead statusini o'zgartirish tugmalaridan kelgan callback query'larni qayta ishlaydi.
    data formatlari:
      - st_menu:<lead_type>:<lead_id>
      - st_set:<lead_type>:<lead_id>:<new_status>
      - st_back:<lead_type>:<lead_id>
    """
    data = callback.get('data', '')
    if not (data.startswith('st_menu:') or data.startswith('st_set:') or data.startswith('st_back:')):
        return False

    message = callback.get('message') or {}
    chat_id = message.get('chat', {}).get('id')
    message_id = message.get('message_id')
    callback_id = callback.get('id')
    tg_user = callback.get('from') or {}

    if not chat_id or not message_id:
        return True

    bot = get_bot()

    from apps.crm.models import TourLead, RestaurantLead, ServiceLead
    from apps.crm.tasks import (
        build_lead_status_selection_keyboard,
        format_tour_lead_card,
        format_restaurant_lead_card,
        format_service_lead_card,
    )

    parts = data.split(':')
    action = parts[0]
    lead_type = parts[1] if len(parts) > 1 else ''
    lead_id = parts[2] if len(parts) > 2 else ''

    model_map = {
        'tour': (TourLead, format_tour_lead_card),
        'restaurant': (RestaurantLead, format_restaurant_lead_card),
        'service': (ServiceLead, format_service_lead_card),
        'flight': (ServiceLead, format_service_lead_card),
        'roadside': (ServiceLead, format_service_lead_card),
    }

    item = model_map.get(lead_type)
    if not item:
        bot.answer_callback_query(callback_id, text="Noma'lum lead turi")
        return True

    model_cls, format_fn = item

    try:
        lead = model_cls.objects.get(id=lead_id)
    except (model_cls.DoesNotExist, ValueError):
        bot.answer_callback_query(callback_id, text="Lead topilmadi")
        return True

    if action == 'st_menu':
        markup = build_lead_status_selection_keyboard(lead_type, lead_id)
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=markup)
        bot.answer_callback_query(callback_id, text="Statusni tanlang")
        return True

    elif action == 'st_back':
        _, markup = format_fn(lead)
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=markup)
        bot.answer_callback_query(callback_id)
        return True

    elif action == 'st_set':
        new_status = parts[3] if len(parts) > 3 else 'contacted'
        staff_username = tg_user.get('username') or tg_user.get('first_name') or 'xodim'

        lead.status = new_status
        lead.assigned_staff_name = staff_username
        lead.save(update_fields=['status', 'assigned_staff_name', 'updated_at'])

        new_text, new_markup = format_fn(lead)
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=new_text, parse_mode='HTML', reply_markup=new_markup)

        st_display_names = {
            'new': 'Yangi',
            'contacted': 'Jarayonda',
            'converted': 'Bajarildi',
            'declined': 'Rad etildi',
        }
        bot.answer_callback_query(callback_id, text=f"Status yangilandi: {st_display_names.get(new_status, new_status)}")
        return True

    return True


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