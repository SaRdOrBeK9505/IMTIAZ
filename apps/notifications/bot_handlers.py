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


def _generic_error_message(lang: str) -> str:
    """AI/tarmoq xatosida foydalanuvchiga ko'rsatiladigan umumiy xabar."""
    if lang == 'ru':
        return "Извините, произошла ошибка при обработке вашего запроса. Попробуйте позже."
    if lang == 'en':
        return "Sorry, an error occurred while processing your request. Please try again later."
    return "Kechirasiz, so'rovingizni qayta ishlashda xatolik yuz berdi. Iltimos, bir ozdan so'ng qayta urinib ko'ring."


def _confirmation_note(lang: str) -> str:
    """Amalni tasdiqlash uchun Mini App'ga yo'naltiruvchi qo'shimcha xabar."""
    if lang == 'ru':
        return "📌 <i>Для подтверждения этого действия перейдите в Mini App:</i>"
    if lang == 'en':
        return "📌 <i>To confirm this action, please proceed to the Mini App:</i>"
    return "📌 <i>Ushbu amallarni tasdiqlash uchun Mini App ga o'ting:</i>"

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
        # MUHIM: ai_service.chat() o'rniga chat_stream() ishlatiladi — bu AI'dan
        # matnni TAYYOR BO'LGANDAN KEYIN emas, balki u GENERATSIYA QILINAYOTGAN
        # paytda, chunk-chunk (real vaqtda) beradi. Shu sabab Telegram xabari
        # haqiqiy Mira/Claude uslubidagi streaming bilan yangilanadi.
        event_stream = ai_service.chat_stream(user=user, message=text, for_bot=True)
        result = _send_live_streaming_response(bot, chat_id, event_stream)

        if result and result.get('type') == 'error':
            raise RuntimeError(result.get('message') or 'AI stream xatosi')

        if result and result.get('requires_confirmation'):
            try:
                bot.send_message(chat_id, _confirmation_note(lang), parse_mode='HTML')
            except Exception:
                logger.exception('Tasdiqlash xabarini yuborishda xato: chat_id=%s', chat_id)

    except Exception as e:
        logger.exception('Bot AI message error: %s', e)
        bot.send_message(chat_id, _generic_error_message(lang), reply_markup=None)


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
        event_stream = ai_service.chat_stream(user=user, message=full_message, for_bot=True)
        result = _send_live_streaming_response(bot, chat_id, event_stream)

        if (not result) or result.get('type') == 'error':
            raise RuntimeError((result or {}).get('message') or 'AI stream xatosi')
        if not (result.get('content') or '').strip():
            raise ValueError("AIAssistantService bo'sh javob qaytardi")

    except Exception as e:
        logger.exception('Xizmat callback uchun AI javobida xatolik: data=%s, chat_id=%s, %s', data, chat_id, e)
        try:
            bot.send_message(chat_id, _generic_error_message(lang))
        except Exception:
            pass


def _send_live_streaming_response(
    bot,
    chat_id: int,
    event_stream,
    reply_markup: dict | None = None,
) -> dict | None:
    """
    HAQIQIY (haqiqiy vaqtli) streaming — producer/consumer naqshi bilan.

    MUAMMO: OpenAI ba'zan javobni juda tez (bir necha soniyada butunlay)
    qaytaradi. Avvalgi versiyada throttle (EDIT_INTERVAL) davomida deyarli
    barcha chunk'lar kelib ulguradi va natijada foydalanuvchi "yozilish"ni
    emas, bitta katta matn "dump"ini ko'radi — chunki reveal tezligi
    to'g'ridan-to'g'ri tarmoq/AI tezligiga bog'liq edi.

    YECHIM: ikkita mustaqil oqim.
      1) PRODUCER (fon thread) — event_stream'ni IMKON QADAR TEZ o'qiydi va
         kelgan matnni umumiy `state['full_text']` bufer'iga qo'shib boradi.
         Tarmoq/AI qanchalik tez bo'lmasin, bu yerda hech qanday sun'iy
         kechikish yo'q.
      2) CONSUMER (shu funksiyaning asosiy oqimi) — bufer'dagi matnni
         o'ZINING belgilagan doimiy tezligida (TYPING_CPS — belgi/soniya)
         Telegram xabariga chiqarib boradi. Reveal tezligi endi AI tezligiga
         EMAS, balki shu konstantaga bog'liq — shuning uchun animatsiya
         har doim bir xil, tabiiy "yozilish" tuyg'usini beradi.

    `event_stream` — AIAssistantService.chat_stream() natijasi (generator),
    quyidagi event turlarini beradi:
        {'type': 'chunk', 'text': '...'}
        {'type': 'tool_processing' | 'tool_start' | 'tool_end', ...}
        {'type': 'done', 'content': ..., 'requires_confirmation': ..., ...}
        {'type': 'error', 'message': '...'}

    Qaytaradi: oxirgi 'done' yoki 'error' eventining dict'i — chaqiruvchi kod
    shu orqali `requires_confirmation` yoki xatoni tekshiradi.
    """
    import threading
    import time

    MAX_MSG_LEN = 4000        # Telegram 4096 limitidan xavfsiz masofa
    EDIT_INTERVAL = 0.5        # editMessageText so'rovlari orasidagi minimal oraliq
    TYPING_CPS = 80           # taxminan tezlik — belgi/soniya (faqat animatsiya sur'ati uchun)
    REVEAL_STEP = max(8, int(TYPING_CPS * EDIT_INTERVAL))

    def _safe_boundary(text: str) -> int:
        """
        MUHIM: so'z HECH QACHON o'rtadan kesilmasligi kerak (masalan "platforma"
        -> "plat" keyin "forma" bo'lib chiqmasligi kerak). Buning uchun matnning
        oxiridan orqaga qarab BIRINCHI bo'shliq (probel/qator ko'chirish)
        belgisigacha bo'lgan uzunlikni qaytaramiz — bu "xavfsiz chegara".
        Undan keyingi qism hali TO'LIQ kelmagan so'z bo'lishi mumkin, shuning
        uchun stream tugamaguncha bu chegaradan OSHIB ketish mumkin emas.
        Agar hali birorta ham bo'shliq bo'lmasa (masalan hali bitta uzun so'z
        kelayotgan bo'lsa), 0 qaytariladi — ya'ni hali hech narsa ko'rsatilmaydi.
        """
        for i in range(len(text) - 1, -1, -1):
            if text[i].isspace():
                return i + 1
        return 0

    # --- Producer va consumer o'rtasida ulashiladigan holat ---
    state_lock = threading.Lock()
    state = {
        'full_text': '',       # AI'dan hozirgacha kelgan TO'LIQ (xom) matn
        'done': False,         # stream producer tomonidan tugatildimi
        'final_event': None,   # oxirgi 'done'/'error' eventi
        'producer_error': None,
    }

    def _producer():
        """Fon oqimi: event_stream'ni tezda so'rib, bufer'ga yozadi."""
        try:
            for event in event_stream:
                etype = event.get('type')
                if etype == 'chunk':
                    text = event.get('text') or ''
                    if text:
                        with state_lock:
                            state['full_text'] += text
                elif etype in ('done', 'error'):
                    with state_lock:
                        state['final_event'] = event
                # tool_processing/tool_start/tool_end — hozircha alohida
                # holat sifatida saqlanmaydi, consumer o'zining "typing..."
                # indikatorini mustaqil boshqaradi.
        except Exception as exc:
            logger.exception('AI stream producer xatosi: chat_id=%s, %s', chat_id, exc)
            with state_lock:
                state['producer_error'] = exc
        finally:
            with state_lock:
                state['done'] = True

    producer_thread = threading.Thread(target=_producer, daemon=True)
    producer_thread.start()

    try:
        bot.send_chat_action(chat_id, 'typing')
    except Exception:
        pass

    message_id: int | None = None
    revealed_len = 0          # full_text ichida hozirgacha Telegram'ga "ochilgan" uzunlik (belgi)
    block_start = 0            # joriy Telegram xabari full_text ichida qayerdan boshlanadi
    last_edit_time = 0.0
    last_typing_action = time.monotonic()

    def _finalize_block(text: str) -> None:
        """Joriy xabarni to'liq matn bilan yakunlab, yangi blokka o'tish uchun."""
        if message_id and text:
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
            except Exception:
                pass

    while True:
        with state_lock:
            full_text = state['full_text']
            is_done = state['done']

        # Stream tugagan bo'lsa — endi hech narsani kutishning hojati yo'q,
        # qolgan hammasini (oxirgi so'zi bilan birga) chiqarish mumkin.
        # Tugamagan bo'lsa — faqat OXIRGI TO'LIQ bo'shliqqacha bo'lgan qism
        # "xavfsiz" — undan keyingisi hali kelayotgan so'z bo'lishi mumkin.
        safe_len = len(full_text) if is_done else _safe_boundary(full_text)
        target_len = min(safe_len, revealed_len + REVEAL_STEP)

        # Hali ochiladigan yangi (TO'LIQ) matn yo'q va stream ham tugamagan —
        # faqat "yozyapti..." holatini yangilab, qisqa kutamiz.
        if target_len == revealed_len and not is_done:
            now = time.monotonic()
            if now - last_typing_action > 3.0:
                try:
                    bot.send_chat_action(chat_id, 'typing')
                except Exception:
                    pass
                last_typing_action = now
            time.sleep(0.15)
            continue

        if target_len > revealed_len:
            revealed_len = target_len
            block_text = full_text[block_start:revealed_len]

            # Joriy blok Telegram limitidan oshsa — yakunlab, yangisini boshlaymiz.
            # Bo'lish nuqtasini ham iloji boricha so'z chegarasiga moslashtiramiz
            # (aks holda 4000-belgi chegarasi so'zni o'rtadan kesib yuborishi mumkin).
            if len(block_text) > MAX_MSG_LEN:
                hard_cut = block_start + MAX_MSG_LEN
                nearest_space = full_text.rfind(' ', block_start, hard_cut)
                cut = nearest_space + 1 if nearest_space > block_start else hard_cut
                _finalize_block(full_text[block_start:cut])
                block_start = cut
                message_id = None
                block_text = full_text[block_start:revealed_len]

            if message_id is None:
                if block_text:
                    msg = bot.send_message(chat_id, block_text)
                    message_id = msg.get('message_id') if isinstance(msg, dict) else msg
                    last_edit_time = time.monotonic()
            else:
                now = time.monotonic()
                if now - last_edit_time >= EDIT_INTERVAL:
                    try:
                        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=block_text)
                    except Exception:
                        # 429 yoki "message is not modified" bo'lishi mumkin — davom etamiz
                        pass
                    last_edit_time = now

            now = time.monotonic()
            if now - last_typing_action > 4.5:
                try:
                    bot.send_chat_action(chat_id, 'typing')
                except Exception:
                    pass
                last_typing_action = now

        if is_done and revealed_len >= len(full_text):
            break

        time.sleep(max(0.0, EDIT_INTERVAL - 0.05))

    producer_thread.join(timeout=5.0)

    with state_lock:
        full_text = state['full_text']
        final_event = state['final_event']
        producer_error = state['producer_error']

    # Xavfsizlik uchun — oxirgi blokni albatta to'liq holatda chiqaramiz.
    final_block_text = full_text[block_start:]
    if message_id and final_block_text:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_block_text)
        except Exception:
            pass
        if reply_markup:
            try:
                bot.edit_message_reply_markup(
                    chat_id=chat_id, message_id=message_id, reply_markup=reply_markup,
                )
            except Exception:
                pass

    # MUHIM: agar stream XATO bilan tugagan bo'lsa-yu, foydalanuvchiga
    # allaqachon qisman matn ko'rsatilgan bo'lsa (masalan "...va m" kabi
    # so'z o'rtasida uzilib qolgan) — o'sha xabarni shunday "muzlagan"
    # holda qoldirmaymiz, chunki bu formatlash xatosidek ko'rinadi. Buning
    # o'rniga xabarga aniq ogohlantirish qo'shib qo'yamiz, shunda
    # foydalanuvchi bu tasodifiy uzilish ekanini tushunadi.
    with state_lock:
        stream_errored = state['final_event'] is not None and state['final_event'].get('type') == 'error'
        stream_errored = stream_errored or state['producer_error'] is not None
    if message_id and full_text.strip() and stream_errored:
        note = "\n\n⚠️ <i>Ulanish uzilib qoldi, javob to'liq bo'lmagan bo'lishi mumkin. Iltimos, savolingizni qayta yuboring.</i>"
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=final_block_text + note,
                parse_mode='HTML',
            )
        except Exception:
            logger.exception('Xato ogohlantirish xabarini qo\'shishda muammo: chat_id=%s', chat_id)

    if producer_error and not final_event:
        final_event = {'type': 'error', 'message': str(producer_error)}

    # Agar hech qanday 'chunk' kelmagan bo'lsa (provider chat_stream'ni
    # qo'llab-quvvatlamaydi va faqat yakuniy 'done' kelgan bo'lsa) — done
    # ichidagi 'content'ni to'g'ridan-to'g'ri yuboramiz.
    if message_id is None and final_event and final_event.get('type') == 'done':
        content = final_event.get('content') or ''
        if content:
            _send_split_message(bot, chat_id, content, reply_markup=reply_markup)

    return final_event


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