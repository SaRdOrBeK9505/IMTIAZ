"""
AI Assistant — ko'p tilli qo'llab-quvvatlash (uz / ru / en).

Til tanlash tartibi:
    1. Joriy xabar tilidan (kirill → ru, ingliz so'zlari → en)
    2. User.language_code (profil / Telegram)
    3. Default: uz
"""

from __future__ import annotations

import re
from decimal import Decimal

SUPPORTED_LANGUAGES = frozenset({'uz', 'ru', 'en'})

LANGUAGE_NAMES = {
    'uz': "o'zbek",
    'ru': 'русский',
    'en': 'English',
}

# Inglizcha kalit so'zlar (oddiy til aniqlash)
_EN_HINTS = frozenset({
    'hello', 'hi', 'hey', 'please', 'thank', 'thanks', 'book', 'booking',
    'flight', 'flights', 'restaurant', 'event', 'train', 'search', 'find',
    'want', 'need', 'help', 'cancel', 'nearby', 'show', 'list', 'my',
    'the', 'what', 'where', 'when', 'how', 'can', 'you', 'i', 'me',
})

# Ruscha kalit so'zlar
_RU_HINTS = frozenset({
    'привет', 'здравствуйте', 'пожалуйста', 'спасибо', 'бронь', 'бронировать',
    'рейс', 'авиабилет', 'ресторан', 'поезд', 'найти', 'поиск', 'помогите',
    'хочу', 'нужно', 'отменить', 'покажи', 'мои', 'где', 'когда', 'как',
})

BOOKING_STATUS_LABELS = {
    'uz': {
        'pending': 'kutilmoqda',
        'confirmed': 'tasdiqlangan',
        'cancelled': 'bekor qilingan',
        'completed': 'yakunlangan',
        'in_progress': 'jarayonda',
    },
    'ru': {
        'pending': 'ожидает',
        'confirmed': 'подтверждён',
        'cancelled': 'отменён',
        'completed': 'завершён',
        'in_progress': 'в процессе',
    },
    'en': {
        'pending': 'pending',
        'confirmed': 'confirmed',
        'cancelled': 'cancelled',
        'completed': 'completed',
        'in_progress': 'in progress',
    },
}

SERVICE_TYPE_LABELS = {
    'uz': {
        'flight': 'parvoz',
        'restaurant': 'restoran',
        'train': 'poyezd',
        'event': 'tadbir',
        'tour': 'tur',
        'hotel': 'mehmonxona',
    },
    'ru': {
        'flight': 'авиабилет',
        'restaurant': 'ресторан',
        'train': 'поезд',
        'event': 'мероприятие',
        'tour': 'тур',
        'hotel': 'отель',
    },
    'en': {
        'flight': 'flight',
        'restaurant': 'restaurant',
        'train': 'train',
        'event': 'event',
        'tour': 'tour',
        'hotel': 'hotel',
    },
}


def detect_language_from_text(text: str | None) -> str | None:
    """Xabar matnidan tilni taxmin qilish."""
    if not text or not text.strip():
        return None

    cyrillic = len(re.findall(r'[\u0400-\u04FF]', text))
    latin = len(re.findall(r'[a-zA-Z]', text))

    if cyrillic >= 3 and cyrillic >= latin:
        words = set(re.findall(r'[\u0400-\u04FF]+', text.lower()))
        if words & _RU_HINTS:
            return 'ru'
        return 'ru'

    words = set(re.findall(r"[a-zA-Z']+", text.lower()))
    if words & _EN_HINTS and cyrillic == 0:
        return 'en'

    return None


def normalize_language(code: str | None) -> str:
    if not code:
        return 'uz'
    lang = code.split('-')[0].lower()
    return lang if lang in SUPPORTED_LANGUAGES else 'uz'


def resolve_language(user, message: str | None = None) -> str:
    """
    Joriy suhbat uchun tilni aniqlash.
    Xabar tilini profil tilidan ustun qo'yadi — mijoz qaysi tilda yozsa shu til.
    """
    detected = detect_language_from_text(message)
    if detected:
        return detected
    return normalize_language(getattr(user, 'language_code', None))


def localized_field(obj, field: str, lang: str) -> str:
    """
    DB obyektidan tilga mos maydon olish.
    Kelajakda {field}_translations JSON yoki {field}_ru maydonlari qo'shilishi mumkin.
    """
    translations = getattr(obj, f'{field}_translations', None)
    if isinstance(translations, dict):
        value = translations.get(lang) or translations.get('uz')
        if value:
            return str(value)

    for code in (lang, 'uz', 'en', 'ru'):
        alt = getattr(obj, f'{field}_{code}', None)
        if alt:
            return str(alt)

    value = getattr(obj, field, None)
    return str(value) if value is not None else ''


def t(key: str, lang: str, **kwargs) -> str:
    """Tarjima kalitidan matn olish."""
    lang = normalize_language(lang)
    catalog = _MESSAGES.get(key, {})
    template = catalog.get(lang) or catalog.get('uz') or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    return template


def build_system_prompt(lang: str, price_limit: str, autonomy_level: str) -> str:
    lang = normalize_language(lang)
    lang_name = LANGUAGE_NAMES[lang]

    prompts = {
        'uz': """\
Sen IMTIAZ premium lifestyle concierge AI assistantsan.
Xizmatlar: parvoz, poyezd, restoran, tadbirlar, bronlar.

Qoidalar:
1. Faqat IMTIAZ mavzularida yordam ber
2. Avtonomiya: {autonomy_level} | limit: {price_limit} UZS
   - manual: har bron uchun tasdiqlash
   - semi_auto: 300,000 UZS gacha mustaqil
   - full_auto: limitgacha mustaqil
3. MUHIM: Foydalanuvchi bilan FAQAT {lang_name} tilida gapir. Barcha javoblaring shu tilida bo'lsin.
4. Tool natijalaridagi ma'lumotlar (restoran nomlari, tadbir sarlavhalari, manzillar) \
boshqa tilda bo'lsa ham, ularni {lang_name} tilida tushunarli tarzda yetkaz. \
Brend va o'ziga xos joy nomlarini saqlab qol.
5. Tashqi xizmat ishlamasa:
   - HECH QACHON .env, API, server, Bookhara, konfiguratsiya haqida gapirma
   - "Tizimda kechikish bor" deb yumshoq ayt
   - Alternativa taklif qil (boshqa sana, restoran, menejer orqali qo'lda yordam)
6. Tool xato xabarini mijozga moslab yetkaz, texnik so'zlarni olib tashla
""",
        'ru': """\
Ты — AI-ассистент премиального lifestyle-сервиса IMTIAZ.
Услуги: авиабилеты, поезда, рестораны, мероприятия, бронирования.

Правила:
1. Помогай только по темам IMTIAZ
2. Автономия: {autonomy_level} | лимит: {price_limit} UZS
   - manual: подтверждение каждого бронирования
   - semi_auto: до 300 000 UZS самостоятельно
   - full_auto: до лимита самостоятельно
3. ВАЖНО: Общайся с пользователем ТОЛЬКО на {lang_name} языке. Все ответы — на этом языке.
4. Данные из tool results (названия ресторанов, событий, адреса) могут быть на другом языке — \
представляй их понятно на {lang_name}. Сохраняй бренды и уникальные названия мест.
5. Если внешний сервис недоступен:
   - НИКОГДА не упоминай .env, API, сервер, Bookhara, конфигурацию
   - Мягко скажи «в системе временная задержка»
   - Предложи альтернативу (другая дата, ресторан, помощь менеджера)
6. Передавай ошибки tool понятным языком, без технических терминов
""",
        'en': """\
You are the IMTIAZ premium lifestyle concierge AI assistant.
Services: flights, trains, restaurants, events, bookings.

Rules:
1. Help only with IMTIAZ-related topics
2. Autonomy: {autonomy_level} | limit: {price_limit} UZS
   - manual: confirm every booking
   - semi_auto: up to 300,000 UZS independently
   - full_auto: up to limit independently
3. IMPORTANT: Communicate with the user ONLY in {lang_name}. All responses must be in this language.
4. Tool result data (restaurant names, event titles, addresses) may be in another language — \
present it clearly in {lang_name}. Keep brand names and unique venue names as-is.
5. If an external service is down:
   - NEVER mention .env, API, server, Bookhara, or configuration
   - Softly say "there is a temporary system delay"
   - Offer alternatives (different date, restaurant, manager assistance)
6. Relay tool errors in plain language, no technical jargon
""",
    }

    return prompts[lang].format(
        price_limit=price_limit,
        autonomy_level=autonomy_level,
        lang_name=lang_name,
    )


def build_confirmation_summary(
    tool_name: str,
    tool_input: dict,
    amount: Decimal | None,
    lang: str,
) -> str:
    lang = normalize_language(lang)
    amount_str = t('confirm_amount', lang, amount=f'{amount:,.0f}') if amount else ''

    if tool_name == 'book_flight':
        return t(
            'confirm_flight', lang,
            origin=tool_input.get('origin', '?'),
            destination=tool_input.get('destination', '?'),
            date=tool_input.get('departure_at', tool_input.get('departure_date', '?')),
            passengers=tool_input.get('passengers', 1),
            amount=amount_str,
        )
    if tool_name == 'book_restaurant':
        return t(
            'confirm_restaurant', lang,
            date=tool_input.get('date', '?'),
            time=tool_input.get('time', '?'),
            guests=tool_input.get('guests', '?'),
            amount=amount_str,
        )
    if tool_name == 'cancel_booking':
        return t(
            'confirm_cancel', lang,
            booking_id=tool_input.get('booking_id', '?'),
        )
    return t('confirm_generic', lang, tool_name=tool_name)


def booking_title_restaurant(lang: str, date: str, time: str, guests: int) -> str:
    return t('booking_title_restaurant', lang, date=date, time=time, guests=guests)


def booking_title_flight(lang: str, origin: str, destination: str) -> str:
    return t('booking_title_flight', lang, origin=origin, destination=destination)


def status_label(status: str, lang: str) -> str:
    lang = normalize_language(lang)
    return BOOKING_STATUS_LABELS.get(lang, {}).get(status, status)


def service_label(service: str | None, lang: str) -> str:
    if not service:
        return t('service_unknown', lang)
    lang = normalize_language(lang)
    return SERVICE_TYPE_LABELS.get(lang, {}).get(service, service)


# ─── Tarjima katalogi ─────────────────────────────────────────────────────────

_MESSAGES: dict[str, dict[str, str]] = {
    'ai_provider_error': {
        'uz': "Kechirasiz, texnik muammo. Qayta urinib ko'ring.",
        'ru': 'Извините, техническая проблема. Попробуйте ещё раз.',
        'en': 'Sorry, a technical issue occurred. Please try again.',
    },
    'reply_format_error': {
        'uz': "Ma'lumot olindi, lekin javobni shakllantirishda muammo bo'ldi. Qayta urinib ko'ring.",
        'ru': 'Данные получены, но возникла проблема с формированием ответа. Попробуйте снова.',
        'en': 'Data received, but there was a problem formatting the reply. Please try again.',
    },
    'default_tool_reply': {
        'uz': "So'rovingiz bo'yicha ma'lumot topildi.",
        'ru': 'По вашему запросу найдена информация.',
        'en': 'Information found for your request.',
    },
    'service_unavailable': {
        'uz': 'Xizmat vaqtincha ishlamayapti.',
        'ru': 'Сервис временно недоступен.',
        'en': 'Service is temporarily unavailable.',
    },
    'action_done': {
        'uz': 'Amal bajarildi.',
        'ru': 'Действие выполнено.',
        'en': 'Action completed.',
    },
    'service_unknown': {
        'uz': 'aniqlanmadi',
        'ru': 'не определено',
        'en': 'unknown',
    },
    'confirm_amount': {
        'uz': '\n💰 Taxminiy narx: {amount} UZS',
        'ru': '\n💰 Примерная стоимость: {amount} UZS',
        'en': '\n💰 Estimated price: {amount} UZS',
    },
    'confirm_flight': {
        'uz': (
            "✈️ Parvoz bron so'rovi:\n"
            "📍 {origin} → {destination}\n"
            "📅 {date}\n"
            "👥 {passengers} yo'lovchi{amount}\n\n"
            "Tasdiqlash uchun ilovadagi «✅ Tasdiqlash» tugmasini bosing."
        ),
        'ru': (
            '✈️ Запрос на бронирование рейса:\n'
            '📍 {origin} → {destination}\n'
            '📅 {date}\n'
            '👥 {passengers} пассажир(ов){amount}\n\n'
            'Нажмите «✅ Подтвердить» в приложении для подтверждения.'
        ),
        'en': (
            '✈️ Flight booking request:\n'
            '📍 {origin} → {destination}\n'
            '📅 {date}\n'
            '👥 {passengers} passenger(s){amount}\n\n'
            'Tap «✅ Confirm» in the app to confirm.'
        ),
    },
    'confirm_restaurant': {
        'uz': (
            "🍽 Restoran bron so'rovi:\n"
            "📅 {date} {time}\n"
            "👥 {guests} kishi{amount}\n\n"
            "Tasdiqlash uchun ilovadagi «✅ Tasdiqlash» tugmasini bosing."
        ),
        'ru': (
            '🍽 Запрос на бронирование ресторана:\n'
            '📅 {date} {time}\n'
            '👥 {guests} гост(ей){amount}\n\n'
            'Нажмите «✅ Подтвердить» в приложении для подтверждения.'
        ),
        'en': (
            '🍽 Restaurant booking request:\n'
            '📅 {date} {time}\n'
            '👥 {guests} guest(s){amount}\n\n'
            'Tap «✅ Confirm» in the app to confirm.'
        ),
    },
    'confirm_cancel': {
        'uz': (
            "❌ Bronni bekor qilish so'rovi:\n"
            "🆔 {booking_id}\n\n"
            "Tasdiqlash uchun ilovadagi «✅ Tasdiqlash» tugmasini bosing."
        ),
        'ru': (
            '❌ Запрос на отмену бронирования:\n'
            '🆔 {booking_id}\n\n'
            'Нажмите «✅ Подтвердить» в приложении для подтверждения.'
        ),
        'en': (
            '❌ Booking cancellation request:\n'
            '🆔 {booking_id}\n\n'
            'Tap «✅ Confirm» in the app to confirm.'
        ),
    },
    'confirm_generic': {
        'uz': "Harakat: {tool_name}\n\nTasdiqlash uchun «✅ Tasdiqlash» tugmasini bosing.",
        'ru': 'Действие: {tool_name}\n\nНажмите «✅ Подтвердить» для подтверждения.',
        'en': 'Action: {tool_name}\n\nTap «✅ Confirm» to confirm.',
    },
    'booking_title_restaurant': {
        'uz': 'Restoran — {date} {time}, {guests} kishi',
        'ru': 'Ресторан — {date} {time}, {guests} гост(ей)',
        'en': 'Restaurant — {date} {time}, {guests} guest(s)',
    },
    'booking_title_flight': {
        'uz': 'Parvoz broni — {origin}→{destination}',
        'ru': 'Бронирование рейса — {origin}→{destination}',
        'en': 'Flight booking — {origin}→{destination}',
    },
    'restaurant_booked': {
        'uz': 'Restoran stoli muvaffaqiyatli band qilindi. Bron ID: {booking_id}',
        'ru': 'Стол в ресторане успешно забронирован. ID бронирования: {booking_id}',
        'en': 'Restaurant table successfully booked. Booking ID: {booking_id}',
    },
    'flight_booked': {
        'uz': 'Parvoz broni yaratildi. Bron ID: {booking_id}',
        'ru': 'Бронирование рейса создано. ID бронирования: {booking_id}',
        'en': 'Flight booking created. Booking ID: {booking_id}',
    },
    'bookhara_no_response': {
        'uz': (
            "Aviachipta tizimi hozir javob bermadi — "
            "bron saqlandi, menejer qo'lda tekshiradi."
        ),
        'ru': (
            'Система авиабилетов сейчас не отвечает — '
            'бронирование сохранено, менеджер проверит вручную.'
        ),
        'en': (
            'The flight booking system is not responding — '
            'booking saved, a manager will verify manually.'
        ),
    },
    'bookhara_delay': {
        'uz': (
            "Aviachipta tizimi bilan bog'lanishda kechikish — "
            'bron qayd etildi, menejer tez orada chiptani tasdiqlaydi.'
        ),
        'ru': (
            'Задержка при связи с системой авиабилетов — '
            'бронирование записано, менеджер скоро подтвердит билет.'
        ),
        'en': (
            'Delay connecting to the flight system — '
            'booking recorded, a manager will confirm the ticket shortly.'
        ),
    },
    'bookhara_unavailable': {
        'uz': (
            "Aviachipta tizimi vaqtincha ishlamayapti — "
            'bron saqlandi, menejer siz bilan bog\'lanadi.'
        ),
        'ru': (
            'Система авиабилетов временно недоступна — '
            'бронирование сохранено, менеджер свяжется с вами.'
        ),
        'en': (
            'Flight system temporarily unavailable — '
            'booking saved, a manager will contact you.'
        ),
    },
    'booking_not_found': {
        'uz': 'Bron topilmadi.',
        'ru': 'Бронирование не найдено.',
        'en': 'Booking not found.',
    },
    'booking_already_status': {
        'uz': 'Bron allaqachon {status}.',
        'ru': 'Бронирование уже {status}.',
        'en': 'Booking is already {status}.',
    },
    'booking_cancelled': {
        'uz': 'Bron bekor qilindi.',
        'ru': 'Бронирование отменено.',
        'en': 'Booking cancelled.',
    },
    'action_confirmed': {
        'uz': 'Harakat muvaffaqiyatli bajarildi.',
        'ru': 'Действие успешно выполнено.',
        'en': 'Action completed successfully.',
    },
    'action_rejected': {
        'uz': 'Harakat bekor qilindi.',
        'ru': 'Действие отменено.',
        'en': 'Action cancelled.',
    },
    'confirm_expired': {
        'uz': "Tasdiqlash muddati o'tib ketdi. Iltimos, qaytadan so'rang.",
        'ru': 'Срок подтверждения истёк. Пожалуйста, запросите снова.',
        'en': 'Confirmation expired. Please request again.',
    },
    # response_builder
    'flights_not_found': {
        'uz': '{route} yo\'nalishida {date} sanasida parvoz topilmadi.',
        'ru': 'Рейсы по маршруту {route} на {date} не найдены.',
        'en': 'No flights found for {route} on {date}.',
    },
    'flights_header': {
        'uz': '✈️ {origin} → {destination} ({date}) — {count} ta variant:',
        'ru': '✈️ {origin} → {destination} ({date}) — {count} вариант(ов):',
        'en': '✈️ {origin} → {destination} ({date}) — {count} option(s):',
    },
    'flights_more': {
        'uz': '... va yana {count} ta variant.',
        'ru': '... и ещё {count} вариант(ов).',
        'en': '... and {count} more option(s).',
    },
    'trains_not_found': {
        'uz': 'Poyezd reyslari topilmadi.',
        'ru': 'Поезда не найдены.',
        'en': 'No trains found.',
    },
    'trains_header': {
        'uz': '🚂 {count} ta poyezd varianti:',
        'ru': '🚂 {count} вариант(ов) поезда:',
        'en': '🚂 {count} train option(s):',
    },
    'train_item': {
        'uz': '{i}. Poyezd {number} — {price:,.0f} UZS',
        'ru': '{i}. Поезд {number} — {price:,.0f} UZS',
        'en': '{i}. Train {number} — {price:,.0f} UZS',
    },
    'flight_item': {
        'uz': '{i}. {airline} {number} — {price:,.0f} {currency}',
        'ru': '{i}. {airline} {number} — {price:,.0f} {currency}',
        'en': '{i}. {airline} {number} — {price:,.0f} {currency}',
    },
    'restaurants_not_found': {
        'uz': 'Restoran topilmadi.',
        'ru': 'Рестораны не найдены.',
        'en': 'No restaurants found.',
    },
    'restaurants_header': {
        'uz': '🍽 {count} ta restoran:',
        'ru': '🍽 {count} ресторан(ов):',
        'en': '🍽 {count} restaurant(s):',
    },
    'events_not_found': {
        'uz': 'Tadbir topilmadi.',
        'ru': 'Мероприятия не найдены.',
        'en': 'No events found.',
    },
    'events_header': {
        'uz': '🎭 {count} ta tadbir:',
        'ru': '🎭 {count} мероприятий:',
        'en': '🎭 {count} event(s):',
    },
    'bookings_empty': {
        'uz': "Sizda hozircha bronlar yo'q.",
        'ru': 'У вас пока нет бронирований.',
        'en': 'You have no bookings yet.',
    },
    'bookings_header': {
        'uz': '📋 {count} ta bron:',
        'ru': '📋 {count} бронирований:',
        'en': '📋 {count} booking(s):',
    },
    'booking_item': {
        'uz': '• {title} — {status} ({price:,.0f} UZS)',
        'ru': '• {title} — {status} ({price:,.0f} UZS)',
        'en': '• {title} — {status} ({price:,.0f} UZS)',
    },
    'nearby_not_found': {
        'uz': 'Yaqin atrofda xizmat topilmadi.',
        'ru': 'Поблизости ничего не найдено.',
        'en': 'No nearby places found.',
    },
    'nearby_header': {
        'uz': '📍 Yaqin atrofda {count} ta joy:',
        'ru': '📍 {count} мест(а) поблизости:',
        'en': '📍 {count} nearby place(s):',
    },
    'nearby_item': {
        'uz': '• {name} — {distance} km',
        'ru': '• {name} — {distance} km',
        'en': '• {name} — {distance} km',
    },
    'preferences_summary': {
        'uz': 'Sizda {total} ta bron, jami {spent:,.0f} UZS. Afzal xizmat: {preferred}.',
        'ru': 'У вас {total} бронирований, всего {spent:,.0f} UZS. Предпочитаемый сервис: {preferred}.',
        'en': 'You have {total} bookings, total {spent:,.0f} UZS. Preferred service: {preferred}.',
    },
    'origin_default': {
        'uz': "jo'nash shahri",
        'ru': 'город вылета',
        'en': 'departure city',
    },
    'destination_default': {
        'uz': 'manzil',
        'ru': 'назначение',
        'en': 'destination',
    },
    'origin_train_default': {
        'uz': "jo'nash punkti",
        'ru': 'станция отправления',
        'en': 'departure station',
    },
    # integrations/errors
    'flight_unavailable': {
        'uz': (
            "Hozir {origin} → {destination}{date_line} bo'yicha onlayn parvoz "
            "qidiruv vaqtincha mavjud emas — aviachiptalar tizimi bilan bog'lanishda "
            "biroz kechikish bor.\n\n"
            "Shu bilan birga sizga yordam bera olaman:\n"
            "• Boshqa sana yoki yaqin aeroport bo'yicha variant ko'rib chiqish\n"
            "• Sayohatingiz uchun restoran yoki tadbir bronlash\n"
            "• Menejerimiz orqali chipta — biz siz uchun qo'lda tekshirib, "
            "eng qulay variantni topamiz\n\n"
            "Bir ozdan keyin avtomatik qidiruvni yana sinab ko'ramiz. "
            "Hozir qaysi yo'nalish sizga qulayroq?"
        ),
        'ru': (
            'Сейчас онлайн-поиск рейсов {origin} → {destination}{date_line} '
            'временно недоступен — небольшая задержка при связи с системой авиабилетов.\n\n'
            'При этом я могу помочь:\n'
            '• Рассмотреть другую дату или ближайший аэропорт\n'
            '• Забронировать ресторан или мероприятие для поездки\n'
            '• Оформить билет через менеджера — мы вручную подберём лучший вариант\n\n'
            'Через некоторое время попробуем поиск снова. Какое направление вам удобнее?'
        ),
        'en': (
            'Online flight search for {origin} → {destination}{date_line} is temporarily '
            'unavailable — slight delay connecting to the ticketing system.\n\n'
            'I can still help you with:\n'
            '• Alternative dates or nearby airports\n'
            '• Restaurant or event bookings for your trip\n'
            '• Ticket via our manager — we\'ll find the best option manually\n\n'
            'We\'ll retry search shortly. Which direction works better for you?'
        ),
    },
    'train_unavailable': {
        'uz': (
            "Hozir {origin} → {destination} yo'nalishida poyezd qidiruv "
            "vaqtincha ishlamayapti — bu xizmat tez orada ulab qo'yiladi.\n\n"
            "Ayni paytda parvoz qidiruv, restoran bron yoki boshqa "
            "IMTIAZ xizmatlari bilan yordam bera olaman. Nima qidiramiz?"
        ),
        'ru': (
            'Поиск поездов по маршруту {origin} → {destination} временно недоступен — '
            'сервис скоро будет подключён.\n\n'
            'Сейчас могу помочь с авиабилетами, ресторанами или другими '
            'услугами IMTIAZ. Что ищем?'
        ),
        'en': (
            'Train search for {origin} → {destination} is temporarily unavailable — '
            'this service will be connected soon.\n\n'
            'I can help with flights, restaurants, or other IMTIAZ services. What shall we look for?'
        ),
    },
    'integration_generic': {
        'uz': (
            "So'rovingizni hozir to'liq bajara olmadim — xizmat vaqtincha band "
            "yoki bog'lanishda kechikish bor.\n\n"
            "Boshqa yo'nalish, sana yoki xizmat turini sinab ko'ramizmi? "
            "Yoki menejerimiz siz bilan bog'lanishini tashkil qilay?"
        ),
        'ru': (
            'Сейчас не удалось полностью выполнить запрос — сервис временно занят '
            'или есть задержка связи.\n\n'
            'Попробуем другой маршрут, дату или тип услуги? '
            'Или организовать звонок менеджера?'
        ),
        'en': (
            'I couldn\'t fully complete your request — the service is temporarily busy '
            'or there\'s a connection delay.\n\n'
            'Shall we try another route, date, or service type? '
            'Or arrange a callback from our manager?'
        ),
    },
}
