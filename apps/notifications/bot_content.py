"""
Telegram bot matnlari va klaviaturalar (multilingual UZ/RU/EN).
"""

from __future__ import annotations

from django.conf import settings

# Callback data kalitlari
CB_MENU     = 'bot:menu'
CB_ABOUT    = 'bot:about'
CB_SERVICES = 'bot:services'
CB_HELP     = 'bot:help'

# Xizmatlar callback data'lari
CB_SERVICE_TRAVEL        = 'service:travel'
CB_SERVICE_RESTAURANT    = 'service:restaurant'
CB_SERVICE_ROADSIDE      = 'service:roadside'
CB_SERVICE_MEDICAL       = 'service:medical'
CB_SERVICE_INSURANCE     = 'service:insurance'
CB_SERVICE_FAMILY_OFFICE = 'service:family_office'
CB_SERVICE_LEISURE       = 'service:leisure'
CB_SERVICE_DISCOUNTS     = 'service:discounts'


def mini_app_ai_url(start_param: str = 'ai_chat') -> str:
    """
    Telegram botdagi AI Chat tugmasi ochadigan URL-manzilni qaytaradi.
    .env dagi TELEGRAM_MINI_APP_AI_URL ko'rsatilgan bo'lsa, o'sha manzil ishlatiladi.
    Aks holda, default FRONTEND_URL/ai?welcome=1&start_param=... ishlatiladi.
    """
    custom_url = getattr(settings, 'TELEGRAM_MINI_APP_AI_URL', '').strip()
    if custom_url:
        return custom_url

    base = getattr(settings, 'FRONTEND_URL', '') or 'https://imtiaz-crm.vercel.app'
    param = f'&start_param={start_param}' if start_param else ''
    return f'{base.rstrip("/")}/ai?welcome=1{param}'


def welcome_text(first_name: str = '', lang: str = 'uz') -> str:
    name_str = f" <b>{first_name}</b>" if first_name else ""
    if lang == 'ru':
        return (
            f"✨{name_str}, добро пожаловать в IMTIAZ!\n\n"
            "Платформа на базе искусственного интеллекта, объединяющая путешествия, рестораны и туризм в одном месте.\n\n"
            "За несколько секунд:\n"
            "✈️ Забронируйте авиабилет и отель\n"
            "🍽️ Забронируйте столик в любимом ресторане\n"
            "🗺️ Выберите туры и экскурсии\n"
            "🚗 Пользуйтесь помощью в дороге\n\n"
            "Наш AI-помощник поможет вам с выбором и бронированием в реальном времени.\n\n"
            "👇 Выберите одну из кнопок ниже, чтобы начать"
        )
    elif lang == 'en':
        return (
            f"✨ Welcome to IMTIAZ{name_str}!\n\n"
            "An AI-powered platform bringing travel, dining, and tourism services together in one place.\n\n"
            "In just a few seconds:\n"
            "✈️ Book flights and hotels\n"
            "🍽️ Reserve a table at your favorite restaurant\n"
            "🗺️ Choose tours and excursions\n"
            "🚗 Access roadside assistance\n\n"
            "Our AI assistant will help you select and book in real time.\n\n"
            "👇 Select one of the options below to start"
        )
    # default uz
    return (
        f"✨{name_str}, IMTIAZ ga xush kelibsiz!\n\n"
        "Sayohat, restoran va turizm xizmatlarini bitta joyda birlashtirgan "
        "sun'iy intellekt asosidagi platforma.\n\n"
        "Bir necha soniyada:\n"
        "✈️ Aviachipta va mehmonxona bron qiling\n"
        "🍽️ Sevimli restoraningizda stol band qiling\n"
        "🗺️ Turlar va ekskursiyalarni tanlang\n"
        "🚗 Yo'lda yordam xizmatidan foydalaning\n\n"
        "AI-yordamchimiz sizga tanlov va bron qilishda real vaqtda yordam beradi.\n\n"
        "👇 Boshlash uchun quyidagi tugmalardan birini tanlang"
    )


def services_text(lang: str = 'uz') -> str:
    if lang == 'ru':
        return (
            "<b>Сервисы платформы IMTIAZ:</b>\n\n"
            "✈️ <b>Путешествия</b> — бронирование авиабилетов и отелей\n"
            "🍽️ <b>Столики</b> — бронирование мест в ресторанах\n"
            "🗺️ <b>Туры</b> — туристические пакеты и экскурсии\n"
            "🚗 <b>Помощь в дороге</b> — техническая и организационная помощь\n"
            "❤️ <b>Медицина</b> — бронирование медицинских услуг\n"
            "🛡️ <b>Страхование</b> — туристическая и медицинская страховка\n"
            "💼 <b>Семейный офис</b> — персональные финансовые услуги\n"
            "🎭 <b>Отдых</b> — развлечения и досуг\n\n"
            "Для бронирования любых услуг обращайтесь к 🤖 <b>IMTIAZ AI</b>."
        )
    elif lang == 'en':
        return (
            "<b>IMTIAZ Platform Services:</b>\n\n"
            "✈️ <b>Travel</b> — book flights and hotels\n"
            "🍽️ <b>Dining</b> — reserve restaurant tables\n"
            "🗺️ <b>Tours</b> — travel packages and excursions\n"
            "🚗 <b>Roadside Assistance</b> — technical and logistics support\n"
            "❤️ <b>Medical</b> — healthcare service booking\n"
            "🛡️ <b>Insurance</b> — travel and health insurance\n"
            "💼 <b>Family Office</b> — personal financial concierge\n"
            "🎭 <b>Leisure</b> — events and entertainment\n\n"
            "For bookings across all services, contact 🤖 <b>IMTIAZ AI</b>."
        )
    return (
        "<b>IMTIAZ platformasidagi xizmatlar:</b>\n\n"
        "✈️ <b>Sayohatlar</b> — aviachipta va mehmonxona bron qilish\n"
        "🍽️ <b>Stol band qilish</b> — restoranlarda joy band qilish\n"
        "🗺️ <b>Turlar</b> — sayohat va ekskursiya paketlari\n"
        "🚗 <b>Yo'lda yordam</b> — texnik va tashkiliy yordam\n"
        "❤️ <b>Tibbiyot</b> — tibbiy xizmatlar bron qilish\n"
        "🛡️ <b>Sug'urta</b> — sayohat va sog'liq sug'urtasi\n"
        "💼 <b>Oilaviy ofis</b> — shaxsiy moliyaviy xizmatlar\n"
        "🎭 <b>Dam olish</b> — bo'sh vaqt va ko'ngilochar tadbirlar\n\n"
        "Har qanday xizmat bo'yicha bron qilish uchun 🤖 <b>IMTIAZ AI</b> orqali murojaat qiling."
    )


def about_text(lang: str = 'uz') -> str:
    if lang == 'ru':
        return (
            "<b>IMTIAZ</b> — это суперапп на базе искусственного интеллекта, "
            "объединяющий услуги путешествий, ресторанов и туризма в одной платформе.\n\n"
            "Платформа сокращает процесс поиска, сравнения и бронирования до нескольких минут, "
            "предоставляя персональные рекомендации через AI-помощника.\n\n"
            "Наша цель — сделать использование путешествий и сервисов максимально простым и быстрым."
        )
    elif lang == 'en':
        return (
            "<b>IMTIAZ</b> is an AI-powered super-app combining travel, "
            "dining, and lifestyle services into a single platform.\n\n"
            "The platform reduces search, comparison, and booking to just a few minutes, "
            "delivering personalized recommendations via an AI assistant.\n\n"
            "Our goal is to make travel and concierge services as simple and fast as possible."
        )
    return (
        "<b>IMTIAZ</b> — bu sayohat, restoran va turizm xizmatlarini bitta platformada "
        "birlashtirgan sun'iy intellekt asosidagi super-ilova.\n\n"
        "Platforma sizga qidiruv, taqqoslash va bron qilish jarayonlarini "
        "bir necha daqiqaga tushirib, AI-yordamchi orqali shaxsiy tavsiyalar olish "
        "imkonini beradi.\n\n"
        "Bizning maqsadimiz — sayohat va xizmatlardan foydalanishni "
        "imkon qadar sodda va tez qilish."
    )


def help_text(lang: str = 'uz') -> str:
    phone = getattr(settings, 'SUPPORT_PHONE', '+998 71 200 00 00')
    contact = getattr(settings, 'SUPPORT_CONTACT', '@imtiaz_support / support@imtiaz.uz')
    if lang == 'ru':
        return (
            "<b>Нужна помощь?</b>\n\n"
            "🤖 На большинство вопросов IMTIAZ AI ответит мгновенно — нажмите кнопку ниже\n"
            f"📞 Для сложных вопросов: <b>{phone}</b>\n"
            f"✉️ Письменные обращения: <b>{contact}</b>\n\n"
            "Режим работы: ежедневно 09:00 – 21:00"
        )
    elif lang == 'en':
        return (
            "<b>Need help?</b>\n\n"
            "🤖 IMTIAZ AI will answer most questions instantly — tap the button below\n"
            f"📞 For complex inquiries: <b>{phone}</b>\n"
            f"✉️ Support contact: <b>{contact}</b>\n\n"
            "Working hours: daily 09:00 – 21:00"
        )
    return (
        "<b>Yordam kerakmi?</b>\n\n"
        "🤖 Aksariyat savollarga IMTIAZ AI darhol javob beradi — quyidagi tugmani bosing\n"
        f"📞 Murakkab holatlar uchun: <b>{phone}</b>\n"
        f"✉️ Yozma murojaat: <b>{contact}</b>\n\n"
        "Ish vaqti: har kuni 09:00 – 21:00"
    )


SECTION_TEXTS = {
    CB_ABOUT:    about_text,
    CB_SERVICES: services_text,
    CB_HELP:     help_text,
}


def main_menu_keyboard(lang: str = 'uz', start_param: str = 'ai_chat') -> dict:
    """Start xabari ostidagi 2x2 grid inline tugmalar."""
    ai_btn_text = "🤖 IMTIAZ AI"
    services_btn_text = "🧭 Xizmatlar" if lang == 'uz' else ("🧭 Сервисы" if lang == 'ru' else "🧭 Services")
    about_btn_text = "ℹ️ Biz haqimizda" if lang == 'uz' else ("ℹ️ О нас" if lang == 'ru' else "ℹ️ About us")
    help_btn_text = "💬 Yordam" if lang == 'uz' else ("💬 Помощь" if lang == 'ru' else "💬 Help")

    return {
        'inline_keyboard': [
            [
                {'text': ai_btn_text, 'web_app': {'url': mini_app_ai_url(start_param)}},
                {'text': services_btn_text, 'callback_data': CB_SERVICES},
            ],
            [
                {'text': about_btn_text, 'callback_data': CB_ABOUT},
                {'text': help_btn_text, 'callback_data': CB_HELP},
            ],
        ],
    }


def section_keyboard(lang: str = 'uz', start_param: str = 'ai_chat') -> dict:
    """Bo'lim ichidagi AI ga o'tish + Asosiy menyuga qaytish tugmalari."""
    talk_text = (
        "✅ IMTIAZ AI bilan gaplashish" if lang == 'uz'
        else ("✅ Чат с IMTIAZ AI" if lang == 'ru'
              else "✅ Chat with IMTIAZ AI")
    )
    back_text = (
        "← Asosiy menyu" if lang == 'uz'
        else ("← Главное меню" if lang == 'ru'
              else "← Main menu")
    )

    return {
        'inline_keyboard': [
            [
                {'text': talk_text, 'web_app': {'url': mini_app_ai_url(start_param)}},
            ],
            [
                {'text': back_text, 'callback_data': CB_MENU},
            ],
        ],
    }


def services_menu_keyboard(lang: str = 'uz') -> dict:
    """Xizmatlar menyusi - 2x4 grid inline tugmalar."""
    if lang == 'ru':
        return {
            'inline_keyboard': [
                [
                    {'text': '✈️ Путешествия', 'callback_data': CB_SERVICE_TRAVEL},
                    {'text': '🍽️ Столики', 'callback_data': CB_SERVICE_RESTAURANT},
                ],
                [
                    {'text': '🚗 Помощь в дороге', 'callback_data': CB_SERVICE_ROADSIDE},
                    {'text': '❤️ Медицина', 'callback_data': CB_SERVICE_MEDICAL},
                ],
                [
                    {'text': '🛡️ Страхование', 'callback_data': CB_SERVICE_INSURANCE},
                    {'text': '💼 Семейный офис', 'callback_data': CB_SERVICE_FAMILY_OFFICE},
                ],
                [
                    {'text': '🎭 Отдых', 'callback_data': CB_SERVICE_LEISURE},
                    {'text': '🏷️ Мои скидки', 'callback_data': CB_SERVICE_DISCOUNTS},
                ],
                [
                    {'text': '← Главное меню', 'callback_data': CB_MENU},
                ],
            ],
        }
    elif lang == 'en':
        return {
            'inline_keyboard': [
                [
                    {'text': '✈️ Travel', 'callback_data': CB_SERVICE_TRAVEL},
                    {'text': '🍽️ Dining', 'callback_data': CB_SERVICE_RESTAURANT},
                ],
                [
                    {'text': '🚗 Roadside Assist', 'callback_data': CB_SERVICE_ROADSIDE},
                    {'text': '❤️ Medical', 'callback_data': CB_SERVICE_MEDICAL},
                ],
                [
                    {'text': '🛡️ Insurance', 'callback_data': CB_SERVICE_INSURANCE},
                    {'text': '💼 Family Office', 'callback_data': CB_SERVICE_FAMILY_OFFICE},
                ],
                [
                    {'text': '🎭 Leisure', 'callback_data': CB_SERVICE_LEISURE},
                    {'text': '🏷️ My Discounts', 'callback_data': CB_SERVICE_DISCOUNTS},
                ],
                [
                    {'text': '← Main menu', 'callback_data': CB_MENU},
                ],
            ],
        }
    # default uz
    return {
        'inline_keyboard': [
            [
                {'text': '✈️ Sayohatlar', 'callback_data': CB_SERVICE_TRAVEL},
                {'text': '🍽️ Stol band qilish', 'callback_data': CB_SERVICE_RESTAURANT},
            ],
            [
                {'text': '🚗 Yo\'lda yordam', 'callback_data': CB_SERVICE_ROADSIDE},
                {'text': '❤️ Tibbiyot', 'callback_data': CB_SERVICE_MEDICAL},
            ],
            [
                {'text': '🛡️ Sug\'urta', 'callback_data': CB_SERVICE_INSURANCE},
                {'text': '💼 Oilaviy ofis', 'callback_data': CB_SERVICE_FAMILY_OFFICE},
            ],
            [
                {'text': '🎭 Dam olish', 'callback_data': CB_SERVICE_LEISURE},
                {'text': '🏷️ Mening chegirmalarim', 'callback_data': CB_SERVICE_DISCOUNTS},
            ],
            [
                {'text': '← Asosiy menyu', 'callback_data': CB_MENU},
            ],
        ],
    }


def service_selection_text(lang: str = 'uz') -> str:
    """Xizmat tanlash sahifasi matni."""
    if lang == 'ru':
        return (
            "<b>🧭 Выберите интересующую вас услугу:</b>\n\n"
            "Нажмите на кнопку ниже, и я помогу вам с бронированием или консультацией."
        )
    elif lang == 'en':
        return (
            "<b>🧭 Select a service you're interested in:</b>\n\n"
            "Tap a button below and I'll help you with booking or consultation."
        )
    return (
        "<b>🧭 Qiziqqan xizmatingizni tanlang:</b>\n\n"
        "Quyidagi tugmalardan birini bosing va men sizga bron yoki konsultatsiya "
        "bo'yicha yordam beraman."
    )
