"""
AI Assistant — ko'p tilli qo'llab-quvvatlash (uz / ru / en).

Til tanlash tartibi:
    1. Joriy xabar tilidan (kirill → ru, ingliz so'zlari → en)
    2. User.language_code (profil / Telegram)
    3. Default: uz

Fayl tarkibi (bo'limlar bo'yicha, yuqoridan pastga):
    1. Konstantalar va til aniqlash yordamchilari
    2. Tarjima kalitidan matn olish — t() va yordamchi builder funksiyalar
    3. AI system prompt (build_system_prompt)
    4. Tasdiqlash (confirmation) matnlari — build_confirmation_summary
    5. _MESSAGES katalogi — mavzu bo'yicha guruhlangan:
       a) umumiy/xato xabarlar
       b) tasdiqlash (confirm_*)
       c) bron natijalari (booking_*, *_booked)
       d) Bookhara / tashqi xizmat xabarlari
       e) parvoz qidiruv natijalari (flight_*, flights_*)
       f) restoran / tadbir / tur paket natijalari
       g) status va xizmat nomlari lug'atlari (pastda, alohida)
"""

from __future__ import annotations

import re
from decimal import Decimal

# ─── 1. Konstantalar va til aniqlash ──────────────────────────────────────────

SUPPORTED_LANGUAGES = frozenset({'uz', 'ru', 'en'})

LANGUAGE_NAMES = {
    'uz': "o'zbek",
    'ru': 'русский',
    'en': 'English',
}

_UZ_HINTS = frozenset({
    'salom', 'assalomu', 'alaykum', 'qanday', 'yordam', 'chipta', 'mehmonxona',
    'restoran', 'bron', 'izlash', 'bormi', 'kerak', 'samolyot', 'poyezd',
    'ozbekcha', "o'zbekcha", 'uzbekcha', 'uzbek', "o'zbek", 'taniysanmi', 'yoz',
    'ha', "yo'q", 'yoq', 'raqam', 'sana', 'narx', 'xizmat', 'rahmat', 'yaxshi',
    'bekor', 'toshkent', 'samarqand', 'buxoro', 'xiva', 'tursiz', 'tur',
})

_EN_HINTS = frozenset({
    'hello', 'hi', 'hey', 'please', 'thank', 'thanks', 'book', 'booking',
    'flight', 'flights', 'restaurant', 'event', 'train', 'search', 'find',
    'want', 'need', 'help', 'cancel', 'nearby', 'show', 'list', 'my',
    'the', 'what', 'where', 'when', 'how', 'can', 'you', 'i', 'me', 'english',
})

_RU_HINTS = frozenset({
    'привет', 'здравствуйте', 'пожалуйста', 'спасибо', 'бронь', 'бронировать',
    'рейс', 'авиабилет', 'ресторан', 'поезд', 'найти', 'поиск', 'помогите',
    'хочу', 'нужно', 'отменить', 'покажи', 'мои', 'где', 'когда', 'как',
})


def detect_language_from_text(text: str | None) -> str | None:
    """Xabar matnidan tilni aniqlash (uz / ru / en)."""
    if not text or not text.strip():
        return None

    cyrillic = len(re.findall(r'[\u0400-\u04FF]', text))
    latin = len(re.findall(r'[a-zA-Z]', text))

    if cyrillic >= 3 and cyrillic >= latin:
        return 'ru'

    words = set(re.findall(r"[a-zA-Z']+", text.lower()))
    if words & _UZ_HINTS:
        return 'uz'

    if words & _EN_HINTS and cyrillic == 0:
        return 'en'

    if latin > 0 and cyrillic == 0:
        return 'uz'

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
        if user and getattr(user, 'language_code', None) != detected:
            try:
                user.language_code = detected
                user.save(update_fields=['language_code'])
            except Exception:
                pass
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


# ─── 2. Tarjima kalitidan matn olish ──────────────────────────────────────────

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


# ─── 3. AI system prompt ──────────────────────────────────────────────────────

_SYSTEM_PROMPTS: dict[str, str] = {
    'uz': """\
Sening isming — Bika. Sen IMTIAZ platformasining premium lifestyle concierge AI yordamchisisan.
Har doim o'zingni faqat "Bika" deb tanishtir — "IMTIAZ AI Assistant" yoki boshqa uzun/rasmiy
nom ISHLATMA. Kerak bo'lsa IMTIAZ'ni xizmat platformasi sifatida tilga olishing mumkin
(masalan: "Men Bika — IMTIAZ'ning shaxsiy yordamchisiman"), lekin o'z isming doim Bika.

Xizmatlar: parvoz, restoran, tadbirlar, tur paketlar, bronlar.
Poyezd xizmati hozir mavjud emas — agar so'rasa, hozircha yo'qligini ayt va boshqa xizmatlarni taklif qil.

Sana konteksti (MUHIM — har doim shu sanalardan foydalan):
  Bugun: {today}
  Ertaga: {tomorrow}
  Sanalarni search_flights ga YYYY-MM-DD formatida yubor. O'tmish sanani HECH QACHON ishlatma.

Qoidalar:
1. Faqat IMTIAZ mavzularida yordam ber
2. Avtonomiya: {autonomy_level} | limit: {price_limit} UZS
   - manual: har bron uchun tasdiqlash
   - semi_auto: 300,000 UZS gacha mustaqil
   - full_auto: limitgacha mustaqil
3. MUHIM: Asosiy muloqot tili: {lang_name}. Lekin foydalanuvchi boshqa tilda yozsa yoki tilni o'zgartirishni so'rasa (masalan: o'zbekcha, ruscha, inglizcha), albatta foydalanuvchi so'ragan tilda tabiiy javob ber.
4. MUHIM TIL VA BAZA QOIDASI: Bazadan yoki tool natijalaridan kelgan ma'lumotlar (restoran nomlari, taversiya, tavsiflar, manzillar, tur paketlari) boshqa tilda (masalan, ruscha) bo'lsa ham, Ularni FOYDALANUVCHI TILLIDА (masalan o'zbekcha suhbat bo'lsa O'ZBEKCHA) chiroyli, tabiiy va professional shaklda tushuntirib yetkaz! Faqat brend va xos nomlarni asl holida qoldir.
5. Tashqi xizmat ishlamasa:
   - HECH QACHON .env, API, server, Bookhara, konfiguratsiya haqida gapirma
   - "Tizimda kechikish bor" deb yumshoq ayt
   - Alternativa taklif qil (boshqa sana, restoran, menejer orqali qo'lda yordam)
6. Tool xato xabarini mijozga moslab yetkaz, texnik so'zlarni olib tashla
7. Parvoz qidiruv:
   - Mijoz parvoz so'rasa DARHOL search_flights chaqir
   - Natijalardan ENG MOS va qulay 3 ta parvozni ko'rsat (ortiqcha variantlarni chiqarib tashla)
   - get_user_preferences parvoz qidiruv uchun ISHLATMA
   - origin/destination IATA kod (TAS, DXB, IST) yoki shahar nomi
   - "ertaga" = {tomorrow}, "bugun" = {today}
8. Restoran va Tur paketlarini taqdim etish (PROFESSIONAL VA JONLI):
   - Quruq va sovuq DB ro'yxatini tashlab qo me'n! Har bir restoran yoki tur paketi haqida mijozda qiziqish va ishtiyoq uyg'otadigan professional tavsif, atmosfera, taomlar va qulayliklar haqida qisqacha, shirin so'zlar bilan gapir.
   - Avval search_tour_packages / search_restaurants bilan qidir. Natija chiqsa, ularni jonli tavsiya qil.
9. Lead oqimi va Telefon raqami (TASDIQLASH TUGMASISIZ, AVTOMATIK ROZILIK):
   - Restoran yoki tur bo'yicha mijozga biror variant ma'qul kelayotgan bo'lsa yoki qiziqsa: "Agar ushbu variant sizga ma'qul kelsa, iltimos telefon raqamingizni qoldiring (+998XXXXXXXXX). Mutaxassislarimiz siz bilan tez fursatda bog'lanib, barcha tafsilotlarni kelishib berishadi" deb ayt.
   - Mijoz telefon raqamini yuborishi bilan bu AVTOMATIK ROZILIK hisoblanadi. HECH QACHON Tasdiqlash (Confirm) tugmasi ko'rsatma va book_restaurant / confirmation oqimini ishlatma!
   - Turlar uchun DARHOL submit_tour_lead chaqir. Restoran uchun ham telefon olinishi bilan stol bron so'rovi va mijoz bilan bog'lanish haqida tasdiqlash tugmasisiz samimiy javob ber: "Rahmat! Sizning restoranga stol so'rovingiz qabul qilindi. Restoran menejerlari tez orada siz bilan bog'lanishadi — bu uzoq vaqt olmaydi."
10. Salomlashish va kirish (MUHIM):
    - Foydalanuvchi birinchi marta salomlashganda (masalan "salom", "привет", "hello"), har doim o'zingni Bika deb tanishtirib, IMTIAZ premium concierge yordamchisi ekanligingni va qanday xizmatlar (parvozlar, restoranlar, tadbirlar, VIP turlar) ko'rsatishingni qisqacha aytib, keyin qanday yordam bera olishingni so'ra.
""",
    'ru': """\
Твоё имя — Bika. Ты AI-ассистент премиального lifestyle-сервиса IMTIAZ.
Всегда представляйся только как «Bika» — НЕ используй «IMTIAZ AI Assistant» или другое
длинное/официальное имя. При необходимости можешь упомянуть IMTIAZ как сервис-платформу
(например: «Я Bika — персональный помощник IMTIAZ»), но твоё имя всегда Bika.

Услуги: авиабилеты, рестораны, мероприятия, турпакеты, бронирования.
Железнодорожные билеты сейчас недоступны — если спросят, сообщи об этом и предложи другие услуги.

Контекст даты (ВАЖНО — всегда используй эти даты):
  Сегодня: {today}
  Завтра: {tomorrow}
  В search_flights передавай даты в формате YYYY-MM-DD. НИКОГДА не используй прошедшие даты.

Правила:
1. Помогай только по темам IMTIAZ
2. Автономия: {autonomy_level} | лимит: {price_limit} UZS
   - manual: подтверждение каждого бронирования
   - semi_auto: до 300 000 UZS самостоятельно
   - full_auto: до лимита самостоятельно
3. ВАЖНО: Основной язык общения: {lang_name}. Однако если пользователь пишет на другом языке или просит сменить язык (узбекский, русский, английский), обязательно отвечай на языке пользователя.
4. ВАЖНОЕ ПРАВИЛО ЯЗЫКА И БАЗЫ: Если данные из базы или tool results (названия ресторанов, описания, адреса, туры) на другом языке — обязательно красиво, естественная и профессионально передавай и объясняй их НА ЯЗЫКЕ ПОЛЬЗОВАТЕЛЯ! Сохраняй только бренды и уникальные названия.
5. Если внешний сервис недоступен:
   - НИКОГДА не упоминай .env, API, сервер, Bookhara, конфигурацию
   - Мягко скажи «в системе временная задержка»
   - Предложи альтернативу (другая дата, ресторан, помощь менеджера)
6. Передавай ошибки tool понятным языком, без технических терминов
7. Поиск рейсов:
   - При запросе рейса СРАЗУ вызывай search_flights
   - Выбирай до 3 САМЫХ ПОДХОДЯЩИХ вариантов рейсов
   - origin/destination — IATA (TAS, DXB, IST) или название города
   - «завтра» = {tomorrow}, «сегодня» = {today}
8. Презентация ресторанов и турпакетов (ПРОФЕССИОНАЛЬНО И ЖИВО):
   - НЕ выдавай сухой список из БД! Описывай рестораны и туры так, чтобы у клиента возник живой интерес: атмосфера, кухня, удобство и уникальность.
9. Заявка (Lead) и Номер телефона (БЕЗ КНОПОК ПОДТВЕРЖДЕНИЯ, АВТОМАТИЧЕСКОЕ СОГЛАСИЕ):
   - Если клиенту подходит вариант тура или ресторана: «Если вам подходит этот вариант, пожалуйста, оставьте ваш номер телефона (+998XXXXXXXXX). Наши специалисты свяжутся с вами в ближайшее время и оформят всё».
   - Как только клиент отправляет номер телефона — это АВТОМАТИЧЕСКОЕ СОГЛАСИЕ. НИКОГДА не показывай кнопку «Подтвердить» (Confirm) и не вызывай book_restaurant с подтверждением!
   - Для туров СРАЗУ вызывай submit_tour_lead. Для ресторанов при получении номера телефона сразу сообщай: «Спасибо! Ваша заявка на бронирование столика принята. Менеджер ресторана свяжется с вами в ближайшее время — это не займёт много времени.»
10. Приветствие и представление (ВАЖНО):
    - При первом приветствии от пользователя (например «привет», «здравствуйте», «salom»), всегда представляйся как Bika, персональный ассистент сервиса IMTIAZ, кратко перечисли доступные услуги (авиабилеты, рестораны, мероприятия, VIP-туры) и спроси, чем можешь помочь.
""",
    'en': """\
Your name is Bika. You are the AI assistant of IMTIAZ, a premium lifestyle concierge service.
Always introduce yourself only as "Bika" — NEVER as "IMTIAZ AI Assistant" or another
long/formal name. You may mention IMTIAZ as the platform you belong to (e.g. "I'm Bika,
IMTIAZ's personal assistant"), but your own name is always Bika.

Services: flights, restaurants, events, tour packages, bookings.
Train service is not available — if asked, say so and offer other services.

Date context (IMPORTANT — always use these dates):
  Today: {today}
  Tomorrow: {tomorrow}
  Pass dates to search_flights as YYYY-MM-DD. NEVER use past dates.

Rules:
1. Help only with IMTIAZ-related topics
2. Autonomy: {autonomy_level} | limit: {price_limit} UZS
   - manual: confirm every booking
   - semi_auto: up to 300,000 UZS independently
   - full_auto: up to limit independently
3. IMPORTANT: Primary language is {lang_name}. However, if the user speaks or requests another language (Uzbek, Russian, English), adapt and respond naturally in the user's language.
4. LANGUAGE & DATABASE RULE: If database or tool result data (restaurant names, descriptions, addresses, tour packages) is in another language, present and explain it beautifully and professionally IN THE USER'S LANGUAGE! Keep only brand names as-is.
5. If an external service is down:
   - NEVER mention .env, API, server, Bookhara, or configuration
   - Softly say "there is a temporary system delay"
   - Offer alternatives (different date, restaurant, manager assistance)
6. Relay tool errors in plain language, no technical jargon
7. Flight search:
   - When user asks for flights, IMMEDIATELY call search_flights
   - Present up to 3 MOST SUITABLE flight options
   - origin/destination as IATA (TAS, DXB, IST) or city name
   - "tomorrow" = {tomorrow}, "today" = {today}
8. Presentation of Restaurants and Tour Packages (PROFESSIONAL & ENGAGING):
   - NEVER output a raw database list! Describe restaurants and tours enticingly — mention atmosphere, cuisine, unique experience, and comfort.
9. Lead Flow & Phone Number (NO CONFIRMATION BUTTONS, AUTOMATIC CONSENT):
   - If a customer is interested in a tour or restaurant option: "If this option suits you, please leave your phone number (+998XXXXXXXXX). Our specialists will contact you shortly to arrange everything."
   - When the customer provides a phone number, treat this as AUTOMATIC CONSENT. Do NOT display confirmation buttons!
   - For tours, IMMEDIATELY call submit_tour_lead.
   - Once submitted, reassure the customer: "Thank you! Our specialists will contact you shortly — this won't take long."
10. Greeting and introduction (IMPORTANT):
    - Upon initial greeting (e.g. "hi", "hello", "salom"), always introduce yourself as Bika, personal assistant for IMTIAZ, briefly summarize available services (flights, restaurants, events, VIP tour packages), and ask how you can help today.
""",
}

_CONCISE_INSTRUCTIONS: dict[str, str] = {
    'uz': (
        "\n\nMUHIM: Faqat so'ralganiga javob ber. Ortig'ini yozma. Keraksiz kirish "
        "so'zlari, uzr, yoki uzoq izoh qo'shma. Agar tool natijasi berilsa, uni qayta "
        "uzun tushuntirma — faqat foydalanuvchiga kerakli qisqa javobni ber."
    ),
    'ru': (
        "\n\nВАЖНО: Отвечай только на заданный вопрос. Не добавляй лишнего текста, "
        "вступлений или извинений. Если есть результат инструмента, не переписывай "
        "большой JSON — дай краткий ответ, достаточный пользователю."
    ),
    'en': (
        "\n\nIMPORTANT: Answer only what was asked. Do not add extra explanations, "
        "long introductions, or apologies. If there are tool results, do not "
        "re-explain the full JSON — provide a short, clear answer the user needs."
    ),
}


def build_system_prompt(
    lang: str,
    price_limit: str,
    autonomy_level: str,
    session_summary: str | None = None,
    user_profile_summary: str | None = None,
) -> str:
    from datetime import timedelta
    from django.utils import timezone

    lang = normalize_language(lang)
    lang_name = LANGUAGE_NAMES[lang]
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)

    base = _SYSTEM_PROMPTS[lang].format(
        price_limit=price_limit,
        autonomy_level=autonomy_level,
        lang_name=lang_name,
        today=today.isoformat(),
        tomorrow=tomorrow.isoformat(),
    )
    if session_summary:
        base += f"\n\nSuhbat xotirasi (bajarilgan harakatlar va saqlangan obyektlar):\n{session_summary}\n"
    if user_profile_summary:
        base += f"\n\nDoimiy foydalanuvchi profili (uzoq muddatli xotira):\n{user_profile_summary}\n"

    base += _CONCISE_INSTRUCTIONS.get(lang, _CONCISE_INSTRUCTIONS['en'])
    return base


# ─── 4. Tasdiqlash (confirmation) matnlari ────────────────────────────────────
#
# DIQQAT: quyidagi confirm_* matnlari faqat "so'rov shakllantirildi" holatini
# tasvirlaydi. Haqiqiy tasdiqlash matn orqali emas, faqat frontend'dagi
# tugma (POST /api/ai/actions/{action_id}/confirm) orqali amalga oshadi —
# qarang: confirmation.py. Frontend shu action_id'ga bog'langan "Tasdiqlash /
# Bekor qilish" tugmalarini albatta chizishi kerak, aks holda foydalanuvchi
# bronni yakunlay olmaydi.

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


# ─── 5. Tarjima katalogi ──────────────────────────────────────────────────────

_MESSAGES: dict[str, dict[str, str]] = {

    # 5a) Umumiy / xato xabarlar ------------------------------------------------
    'ai_provider_error': {
        'uz': "Kechirasiz, texnik muammo. Qayta urinib ko'ring.",
        'ru': 'Извините, техническая проблема. Попробуйте ещё раз.',
        'en': 'Sorry, a technical issue occurred. Please try again.',
    },
    'ai_welcome': {
        'uz': (
            'Assalomu alaykum! 👋\n\n'
            'Men Bike — IMTIAZ platformasining shaxsiy sayohat va xizmat yordamchisiman.\n'
            'Men orqali:\n\n'
            '✈️ Aviachipta va mehmonxona bron qilishingiz\n'
            '🍽️ Restoranda stol band qilishingiz\n'
            '🗺️ Tur va ekskursiya tanlashingiz mumkin\n\n'
            'Sizga qanday yordam bera olaman?'
        ),
        'ru': (
            'Здравствуйте! 👋\n\n'
            'Я Bike — персональный помощник IMTIAZ по путешествиям и сервисам.\n'
            'С моей помощью вы можете:\n\n'
            '✈️ Забронировать авиабилет и отель\n'
            '🍽️ Забронировать столик в ресторане\n'
            '🗺️ Выбрать туры и экскурсии\n\n'
            'Чем я могу вам помочь?'
        ),
        'en': (
            'Hello! 👋\n\n'
            'I am Bike — IMTIAZ\'s personal travel and concierge assistant.\n'
            'Through me, you can:\n\n'
            '✈️ Book flights and hotels\n'
            '🍽️ Reserve a restaurant table\n'
            '🗺️ Choose tours and excursions\n\n'
            'How can I help you today?'
        ),
    },
    'quick_replies': {
        'uz': ["✈️ Chipta izlash", "🍽️ Stol band qilish", "❓ Boshqa savol"],
        'ru': ["✈️ Поиск билетов", "🍽️ Забронировать стол", "❓ Другой вопрос"],
        'en': ["✈️ Search flights", "🍽️ Book a table", "❓ Other question"],
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

    # 5b) Tasdiqlash (confirm_*) --------------------------------------------------
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
            "Davom etish uchun pastdagi «✅ Tasdiqlash» tugmasini bosing."
        ),
        'ru': (
            '✈️ Запрос на бронирование рейса:\n'
            '📍 {origin} → {destination}\n'
            '📅 {date}\n'
            '👥 {passengers} пассажир(ов){amount}\n\n'
            'Нажмите «✅ Подтвердить» ниже, чтобы продолжить.'
        ),
        'en': (
            '✈️ Flight booking request:\n'
            '📍 {origin} → {destination}\n'
            '📅 {date}\n'
            '👥 {passengers} passenger(s){amount}\n\n'
            'Tap «✅ Confirm» below to continue.'
        ),
    },
    'confirm_restaurant': {
        'uz': (
            "🍽 Restoran bron so'rovi:\n"
            "📅 {date} {time}\n"
            "👥 {guests} kishi{amount}\n\n"
            "Davom etish uchun pastdagi «✅ Tasdiqlash» tugmasini bosing."
        ),
        'ru': (
            '🍽 Запрос на бронирование ресторана:\n'
            '📅 {date} {time}\n'
            '👥 {guests} гост(ей){amount}\n\n'
            'Нажмите «✅ Подтвердить» ниже, чтобы продолжить.'
        ),
        'en': (
            '🍽 Restaurant booking request:\n'
            '📅 {date} {time}\n'
            '👥 {guests} guest(s){amount}\n\n'
            'Tap «✅ Confirm» below to continue.'
        ),
    },
    'confirm_cancel': {
        'uz': (
            "❌ Bronni bekor qilish so'rovi:\n"
            "🆔 {booking_id}\n\n"
            "Davom etish uchun pastdagi «✅ Tasdiqlash» tugmasini bosing."
        ),
        'ru': (
            '❌ Запрос на отмену бронирования:\n'
            '🆔 {booking_id}\n\n'
            'Нажмите «✅ Подтвердить» ниже, чтобы продолжить.'
        ),
        'en': (
            '❌ Booking cancellation request:\n'
            '🆔 {booking_id}\n\n'
            'Tap «✅ Confirm» below to continue.'
        ),
    },
    'confirm_generic': {
        'uz': "Harakat: {tool_name}\n\nDavom etish uchun pastdagi «✅ Tasdiqlash» tugmasini bosing.",
        'ru': 'Действие: {tool_name}\n\nНажмите «✅ Подтвердить» ниже, чтобы продолжить.',
        'en': 'Action: {tool_name}\n\nTap «✅ Confirm» below to continue.',
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

    # 5c) Bron natijalari (booking_*, *_booked) ------------------------------
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

    # 5d) Bookhara / tashqi xizmat xabarlari -----------------------------------
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
    'flight_past_date': {
        'uz': (
            "Ko'rsatilgan sana ({date}) allaqachon o'tib ketgan. "
            "Iltimos, kelgusi sana kiriting — masalan ertaga ({tomorrow_hint}). "
            "Qaysi sanada jo'nashni xohlaysiz?"
        ),
        'ru': (
            'Указанная дата ({date}) уже прошла. '
            'Укажите будущую дату — например завтра ({tomorrow_hint}). '
            'На какую дату планируете вылет?'
        ),
        'en': (
            'The date ({date}) is in the past. '
            'Please provide a future date — e.g. tomorrow ({tomorrow_hint}). '
            'When would you like to depart?'
        ),
    },
    'flight_invalid_date': {
        'uz': "Sana noto'g'ri. Iltimos, YYYY-MM-DD formatida kiriting (masalan: 2026-08-14).",
        'ru': 'Неверная дата. Укажите в формате YYYY-MM-DD (например: 2026-08-14).',
        'en': 'Invalid date. Please use YYYY-MM-DD format (e.g. 2026-08-14).',
    },
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

    # 5e) Parvoz qidiruv natijalari (flight_*, flights_*) --------------------
    'flights_not_found': {
        'uz': (
            '{route} yo\'nalishida {date} sanasida to\'g\'ridan-to\'g\'ri parvoz topilmadi.\n\n'
            'Sinab ko\'rish mumkin:\n'
            '• Boshqa sana (masalan 1-2 kun keyin)\n'
            '• Yaqin aeroport (Dubai o\'rniga Sharjah SHJ)\n'
            '• Menejer orqali qo\'lda qidiruv — eng yaxshi variantni topamiz\n\n'
            'Qaysi variantni sinab ko\'ramiz?'
        ),
        'ru': (
            'Прямые рейсы {route} на {date} не найдены.\n\n'
            'Можно попробовать:\n'
            '• Другую дату (через 1–2 дня)\n'
            '• Ближайший аэропорт (вместо Dubai — Sharjah SHJ)\n'
            '• Ручной поиск через менеджера\n\n'
            'Какой вариант попробуем?'
        ),
        'en': (
            'No direct flights for {route} on {date}.\n\n'
            'We can try:\n'
            '• A different date (1–2 days later)\n'
            '• A nearby airport (Sharjah SHJ instead of Dubai)\n'
            '• Manual search via our manager\n\n'
            'Which option shall we try?'
        ),
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
    'flight_item': {
        'uz': '{i}. {airline} {number} | 🕐 {departure_time} → {arrival_time} | {price:,.0f} {currency}{baggage}',
        'ru': '{i}. {airline} {number} | 🕐 {departure_time} → {arrival_time} | {price:,.0f} {currency}{baggage}',
        'en': '{i}. {airline} {number} | 🕐 {departure_time} → {arrival_time} | {price:,.0f} {currency}{baggage}',
    },
    'flight_baggage_yes': {
        'uz': ' | 🧳 bagaj bor',
        'ru': ' | 🧳 багаж',
        'en': ' | 🧳 baggage',
    },
    'flights_book_hint': {
        'uz': '\n💡 Yoqqan variant raqamini yozing — bron qilishda yordam beraman.',
        'ru': '\n💡 Напишите номер варианта — помогу с бронированием.',
        'en': '\n💡 Tell me the option number — I\'ll help you book.',
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

    # 5f) Restoran / tadbir / tur paket natijalari ----------------------------
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
    'tours_not_found': {
        'uz': 'Hozircha mos tur paket topilmadi.',
        'ru': 'Подходящие турпакеты пока не найдены.',
        'en': 'No matching tour packages at the moment.',
    },
    'tours_no_packages_intro': {
        'uz': 'Hozircha aniq paket topilmadi, lekin IMTIAZ hamkor tur kompaniyalari mavjud:',
        'ru': 'Конкретный пакет пока не найден, но у IMTIAZ есть партнёрские туркомпании:',
        'en': 'No exact package yet, but IMTIAZ partner tour companies are available:',
    },
    'tours_partners_header': {
        'uz': '\n🏢 Hamkor tur kompaniyalar:',
        'ru': '\n🏢 Партнёрские туркомпании:',
        'en': '\n🏢 Partner tour companies:',
    },
    'tour_partner_item': {
        'uz': '{i}. {name} — {package_count} ta faol paket',
        'ru': '{i}. {name} — {package_count} активных пакетов',
        'en': '{i}. {name} — {package_count} active package(s)',
    },
    'tour_partner_item_new': {
        'uz': '{i}. {name} — yangi hamkor (paketlar tez orada)',
        'ru': '{i}. {name} — новый партнёр (пакеты скоро)',
        'en': '{i}. {name} — new partner (packages coming soon)',
    },
    'tours_destinations_hint': {
        'uz': '\n🌍 Mavjud yo\'nalishlar: {destinations}',
        'ru': '\n🌍 Доступные направления: {destinations}',
        'en': '\n🌍 Available destinations: {destinations}',
    },
    'tours_empty_suggest': {
        'uz': (
            '\nQaysi yo\'nalish yoki kompaniya qiziq? '
            'Masalan: «Samarqand turlari» yoki «Dubai paketlari». '
            'Yoki telefon raqamingizni qoldiring — menejer qo\'ng\'iroq qiladi.'
        ),
        'ru': (
            '\nКакое направление или компания интересует? '
            'Например: «туры в Самарканд» или «пакеты в Dubai». '
            'Или оставьте телефон — менеджер перезвонит.'
        ),
        'en': (
            '\nWhich destination or company interests you? '
            'e.g. "Samarkand tours" or "Dubai packages". '
            'Or leave your phone — a manager will call back.'
        ),
    },
    'tours_more': {
        'uz': '... va yana {count} ta paket.',
        'ru': '... и ещё {count} пакет(ов).',
        'en': '... and {count} more package(s).',
    },
    'tour_date_flexible': {
        'uz': 'mavjud sanalar bo\'yicha',
        'ru': 'по доступным датам',
        'en': 'flexible dates',
    },
    'tours_interest_hint': {
        'uz': '\n💡 Qaysi tur qiziq? Telefon raqamingizni qoldirsangiz, menejer bog\'lanadi.',
        'ru': '\n💡 Какой тур интересен? Оставьте телефон — менеджер свяжется.',
        'en': '\n💡 Which tour interests you? Leave your phone and a manager will contact you.',
    },
    'tours_header': {
        'uz': '🌍 {count} ta tur paket:',
        'ru': '🌍 {count} турпакетов:',
        'en': '🌍 {count} tour package(s):',
    },
    'tour_item': {
        'uz': '{i}. {title}{organization} ({destination}) — {price:,.0f} {currency}, jo\'nash: {departure}',
        'ru': '{i}. {title}{organization} ({destination}) — {price:,.0f} {currency}, вылет: {departure}',
        'en': '{i}. {title}{organization} ({destination}) — {price:,.0f} {currency}, departure: {departure}',
    },
    'tour_lead_invalid_phone': {
        'uz': 'Telefon raqami noto\'g\'ri. Iltimos, +998XXXXXXXXX formatida yuboring.',
        'ru': 'Неверный номер телефона. Укажите в формате +998XXXXXXXXX.',
        'en': 'Invalid phone number. Please use +998XXXXXXXXX format.',
    },
    'tour_lead_package_not_found': {
        'uz': 'Tur paketi topilmadi yoki hozir faol emas.',
        'ru': 'Турпакет не найден или сейчас неактивен.',
        'en': 'Tour package not found or currently inactive.',
    },
    'tour_lead_invalid_date': {
        'uz': 'Sana noto\'g\'ri. YYYY-MM-DD formatida yuboring.',
        'ru': 'Неверная дата. Используйте формат YYYY-MM-DD.',
        'en': 'Invalid date. Use YYYY-MM-DD format.',
    },
    'tour_lead_submitted': {
        'uz': (
            '✅ «{title}» bo\'yicha so\'rovingiz qabul qilindi. '
            'Kerakli mutaxassislarimiz tez orada siz bilan bog\'lanishadi — bu uzoq vaqt olmaydi.'
        ),
        'ru': (
            '✅ Ваш запрос по «{title}» принят. '
            'Наши специалисты свяжутся с вами в ближайшее время — это не займёт много времени.'
        ),
        'en': (
            '✅ Your request for «{title}» has been received. '
            'Our specialists will contact you shortly — this won\'t take long.'
        ),
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
}


# ─── 5g) Status va xizmat nomlari lug'atlari ──────────────────────────────────

BOOKING_STATUS_LABELS: dict[str, dict[str, str]] = {
    'uz': {
        'pending': 'kutilmoqda',
        'confirmed': 'tasdiqlandi',
        'cancelled': 'bekor qilindi',
        'completed': 'yakunlandi',
    },
    'ru': {
        'pending': 'ожидает',
        'confirmed': 'подтверждено',
        'cancelled': 'отменено',
        'completed': 'завершено',
    },
    'en': {
        'pending': 'pending',
        'confirmed': 'confirmed',
        'cancelled': 'cancelled',
        'completed': 'completed',
    },
}

SERVICE_TYPE_LABELS: dict[str, dict[str, str]] = {
    'uz': {
        'flight': 'parvoz',
        'restaurant': 'restoran',
        'event': 'tadbir',
        'train': 'poyezd',
        'tour': 'tur paket',
    },
    'ru': {
        'flight': 'авиабилет',
        'restaurant': 'ресторан',
        'event': 'мероприятие',
        'train': 'поезд',
        'tour': 'турпакет',
    },
    'en': {
        'flight': 'flight',
        'restaurant': 'restaurant',
        'event': 'event',
        'train': 'train',
        'tour': 'tour package',
    },
}