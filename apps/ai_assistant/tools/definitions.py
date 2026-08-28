"""
Claude function-calling uchun tool ta'riflari.
Barcha tool'lar provayderdan mustaqil — faqat JSON sxema.
"""

FLIGHT_SEARCH_TOOL = {
    'name': 'search_flights',
    'description': 'Parvoz variantlarini qidiradi. Yo\'nalish, sana va yo\'lovchilar soni bo\'yicha.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'origin': {'type': 'string', 'description': 'Jo\'nash shahri yoki IATA kodi (masalan: TAS, DXB)'},
            'destination': {'type': 'string', 'description': 'Boradigan shahar yoki IATA kodi'},
            'departure_date': {'type': 'string', 'description': 'Jo\'nash sanasi YYYY-MM-DD formatida'},
            'return_date': {'type': 'string', 'description': 'Qaytish sanasi (ixtiyoriy, round-trip uchun)'},
            'passengers': {'type': 'integer', 'description': 'Yo\'lovchilar soni', 'default': 1},
            'seat_class': {
                'type': 'string',
                'enum': ['economy', 'business', 'first'],
                'description': 'Kreslo sinfi',
                'default': 'economy',
            },
        },
        'required': ['origin', 'destination', 'departure_date'],
    },
}

TRAIN_SEARCH_TOOL = {
    'name': 'search_trains',
    'description': 'Poyezd yo\'nalishlarini qidiradi.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'origin': {'type': 'string', 'description': 'Jo\'nash stantsiyasi yoki shahri'},
            'destination': {'type': 'string', 'description': 'Boradigan stantsiya yoki shahar'},
            'departure_date': {'type': 'string', 'description': 'Jo\'nash sanasi YYYY-MM-DD formatida'},
            'passengers': {'type': 'integer', 'default': 1},
            'wagon_type': {
                'type': 'string',
                'enum': ['platzkart', 'coupe', 'sv', 'sitting'],
                'default': 'coupe',
            },
        },
        'required': ['origin', 'destination', 'departure_date'],
    },
}

RESTAURANT_SEARCH_TOOL = {
    'name': 'search_restaurants',
    'description': 'Restoran va stol bronlash imkoniyatlarini qidiradi.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'city': {'type': 'string', 'description': 'Shahar nomi'},
            'date': {'type': 'string', 'description': 'Bron sanasi YYYY-MM-DD formatida'},
            'time': {'type': 'string', 'description': 'Bron vaqti HH:MM formatida'},
            'guests': {'type': 'integer', 'description': 'Mehmonlar soni', 'default': 2},
            'cuisine': {'type': 'string', 'description': 'Oshxona turi (ixtiyoriy, masalan: Italian, Uzbek)'},
        },
        'required': ['city', 'date', 'time'],
    },
}

RESTAURANT_BOOK_TOOL = {
    'name': 'book_restaurant',
    'description': 'Tanlangan restoranda stol bronlaydi.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'branch_id': {'type': 'string', 'description': 'Restoran filiali UUID'},
            'date': {'type': 'string', 'description': 'Bron sanasi YYYY-MM-DD'},
            'time': {'type': 'string', 'description': 'Bron vaqti HH:MM'},
            'guests': {'type': 'integer'},
            'special_requests': {'type': 'string', 'description': 'Maxsus so\'rovlar (ixtiyoriy)'},
        },
        'required': ['branch_id', 'date', 'time', 'guests'],
    },
}

FLIGHT_BOOK_TOOL = {
    'name': 'book_flight',
    'description': (
        'Tanlangan parvozni bronlaydi va to\'lovni boshlaydi. '
        'Barcha maydonlarni oldingi search_flights natijasidagi '
        'tegishli parvoz obyektidan (origin, destination, departure_at, price) OL — '
        'o\'ylab topma, faqat natijada ko\'rsatilgan qiymatlarni ishlat.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': {
            'offer_id':     {'type': 'string', 'description': 'search_flights natijasidan offer ID'},
            'origin':       {'type': 'string', 'description': "search_flights natijasidagi 'origin' (IATA kod)"},
            'destination':  {'type': 'string', 'description': "search_flights natijasidagi 'destination' (IATA kod)"},
            'departure_at': {'type': 'string', 'description': "Tanlangan parvozning 'departure_at' qiymati (ISO datetime)"},
            'price':        {'type': 'number', 'description': "Tanlangan parvozning 'price' qiymati — tasdiqlash va limit tekshiruvi uchun MAJBURIY"},
            'currency':     {'type': 'string', 'description': "Tanlangan parvozning 'currency' qiymati (masalan UZS)"},
            'passengers': {'type': 'integer'},
            'payment_method': {
                'type': 'string',
                'enum': ['alifpay'],
                'default': 'alifpay',
                'description': 'Mijoz AlifPay checkout orqali to\'laydi',
            },
        },
        'required': ['offer_id', 'origin', 'destination', 'departure_at', 'price'],
    },
}

EVENT_SEARCH_TOOL = {
    'name': 'search_events',
    'description': 'Mavjud tadbirlarni qidiradi.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'city': {'type': 'string'},
            'date_from': {'type': 'string', 'description': 'YYYY-MM-DD'},
            'date_to': {'type': 'string', 'description': 'YYYY-MM-DD'},
            'category': {'type': 'string'},
        },
        'required': [],
    },
}

BOOKING_CANCEL_TOOL = {
    'name': 'cancel_booking',
    'description': 'Mavjud bronni bekor qiladi.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'booking_id': {'type': 'string', 'description': 'Bron UUID'},
            'reason': {'type': 'string', 'description': 'Bekor qilish sababi'},
        },
        'required': ['booking_id'],
    },
}

USER_BOOKINGS_TOOL = {
    'name': 'get_user_bookings',
    'description': 'Foydalanuvchining bronlar tarixini qaytaradi.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'status': {
                'type': 'string',
                'enum': ['pending', 'confirmed', 'cancelled', 'completed', 'all'],
                'default': 'all',
            },
            'service_type': {'type': 'string'},
            'limit': {'type': 'integer', 'default': 10},
        },
        'required': [],
    },
}

NEARBY_PLACES_TOOL = {
    'name': 'get_nearby_places',
    'description': (
        'Foydalanuvchi joylashuviga yaqin restoran, tadbir yoki boshqa xizmatlarni topadi. '
        'Manzilni tahlil qilib eng yaqin va qulay variantni tanlash uchun ishlatiladi.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': {
            'latitude':     {'type': 'number', 'description': 'Kenglik (latitude)'},
            'longitude':    {'type': 'number', 'description': 'Uzunlik (longitude)'},
            'service_type': {
                'type': 'string',
                'enum': ['restaurant', 'event', 'hotel'],
                'default': 'restaurant',
            },
            'radius_km':    {'type': 'number', 'default': 5, 'description': 'Qidiruv radiusi km da'},
        },
        'required': ['latitude', 'longitude'],
    },
}

USER_PREFERENCES_TOOL = {
    'name': 'get_user_preferences',
    'description': (
        'Foydalanuvchining bron tarixi va afzalliklarini tahlil qiladi. '
        'FAQAT mijoz o\'z tarixi/afzalliklari haqida so\'raganda ishlat. '
        'Parvoz qidiruv uchun ISHLATMA — buning o\'rniga search_flights.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': {},
        'required': [],
    },
}

TOUR_SEARCH_TOOL = {
    'name': 'search_tour_packages',
    'description': (
        'Tur paketlari va hamkor tur kompaniyalarini qidiradi. '
        'Mijoz tur, kompaniya yoki yo\'nalish haqida so\'rasa — chaqir. '
        'Filtrsiz chaqirish mumkin (barcha mavjud paketlar va hamkorlar). '
        'Paket topilmasa ham partners ro\'yxati qaytadi.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': {
            'destination': {
                'type': 'string',
                'description': 'Yo\'nalish nomi yoki shahar (masalan: Dubai, Samarqand)',
            },
            'departure_date_from': {
                'type': 'string',
                'description': 'Jo\'nash sanasi dan (YYYY-MM-DD, ixtiyoriy)',
            },
            'passengers': {
                'type': 'integer',
                'description': 'Sayohatchilar soni',
                'default': 1,
            },
            'query': {
                'type': 'string',
                'description': 'Paket nomi yoki kalit so\'z (ixtiyoriy)',
            },
        },
        'required': [],
    },
}

TOUR_LEAD_TOOL = {
    'name': 'submit_tour_lead',
    'description': (
        'Mijoz tur paketiga qiziqish bildirganda va telefon raqamini bergandan keyin lead yaratadi. '
        'MUHIM: telefon raqamisiz chaqirma — avval mijozdan +998XXXXXXXXX formatida so\'ra.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': {
            'package_id': {
                'type': 'string',
                'description': 'search_tour_packages natijasidagi paket UUID',
            },
            'phone': {
                'type': 'string',
                'description': 'Mijoz telefon raqami (+998XXXXXXXXX)',
            },
            'full_name': {
                'type': 'string',
                'description': 'Mijoz ismi (ixtiyoriy)',
            },
            'preferred_departure_date': {
                'type': 'string',
                'description': 'Afzal jo\'nash sanasi YYYY-MM-DD (ixtiyoriy)',
            },
            'passengers': {
                'type': 'integer',
                'description': 'Sayohatchilar soni',
                'default': 1,
            },
            'note': {
                'type': 'string',
                'description': 'Qo\'shimcha talablar yoki savollar (ixtiyoriy)',
            },
        },
        'required': ['package_id', 'phone'],
    },
}


RESTAURANT_LEAD_TOOL = {
    'name': 'submit_restaurant_lead',
    'description': (
        'Mijoz restoranda stol bron qilishga qiziqish bildirganda va telefon raqamini bergandan keyin lead/so\'rov yaratadi. '
        'MUHIM: telefon raqamisiz chaqirma — avval mijozdan +998XXXXXXXXX formatida so\'ra.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': {
            'branch_id': {
                'type': 'string',
                'description': 'search_restaurants yoki restoranning branch_id UUID kodi',
            },
            'phone': {
                'type': 'string',
                'description': 'Mijoz telefon raqami (+998XXXXXXXXX)',
            },
            'full_name': {
                'type': 'string',
                'description': 'Mijoz ismi (ixtiyoriy)',
            },
            'preferred_date': {
                'type': 'string',
                'description': 'Afzal kelsa sanasi YYYY-MM-DD (ixtiyoriy)',
            },
            'preferred_time': {
                'type': 'string',
                'description': 'Afzal kelish vaqti HH:MM (ixtiyoriy)',
            },
            'guests': {
                'type': 'integer',
                'description': 'Mehmonlar soni',
                'default': 2,
            },
            'note': {
                'type': 'string',
                'description': 'Qo\'shimcha zali, stol turi yoki so\'rovlar (ixtiyoriy)',
            },
        },
        'required': ['branch_id', 'phone'],
    },
}


SERVICE_LEAD_TOOL = {
    'name': 'submit_service_lead',
    'description': (
        "Mijoz Sayohat/Tur (travel), Restoran/stol (restaurant), Yo'lda yordam, Tibbiyot, "
        "Sug'urta, Family Office yoki Dam olish xizmatlaridan biriga (yoki platformada hali "
        "aniq bo'lmagan boshqa har qanday ehtiyojga) qiziqish bildirganda va telefon raqamini "
        "bergandan keyin lead yaratadi. "
        "MUHIM: telefon raqamisiz chaqirma — avval mijozdan +998XXXXXXXXX formatida so'ra. "
        "Tur va restoran so'rovlari uchun bu — YAGONA to'g'ri tool: aniq paket/filial "
        "TANLANMAYDI, faqat mijozning qiziqishlari (yo'nalish/oshxona turi, sana, odam soni, "
        "byudjet va h.k.) customer_analysis/note ichiga yozib, lead sifatida guruhga yuboriladi."
    ),
    'input_schema': {
        'type': 'object',
        'properties': {
            'phone': {
                'type': 'string',
                'description': 'Mijoz telefon raqami (+998XXXXXXXXX)',
            },
            'category': {
                'type': 'string',
                'enum': [
                    'travel', 'restaurant', 'roadside', 'medical',
                    'insurance', 'family_office', 'leisure', 'other',
                ],
                'description': (
                    "Xizmat kategoriyasi (Sayohat/Tur=travel, Restoran/stol=restaurant, "
                    "Yo'lda yordam=roadside, Tibbiyot=medical, Sug'urta=insurance, "
                    "Family Office=family_office, Dam olish=leisure, boshqa=other)"
                ),
            },
            'full_name': {
                'type': 'string',
                'description': 'Mijoz ismi (ixtiyoriy)',
            },
            'service_name': {
                'type': 'string',
                'description': (
                    "Mijoz so'ragan xizmatning qisqa nomi (masalan: 'Dubay turi', "
                    "'Italyan restorani uchun stol', 'Evakuator xizmati')"
                ),
            },
            'customer_analysis': {
                'type': 'string',
                'description': (
                    "Mijoz ehtiyoji haqida AI tomonidan yozilgan qisqa tahliliy izoh. "
                    "Tur/restoran leadlari uchun BU MAJBURIY: yo'nalish yoki oshxona turi, "
                    "sana(lar), odam soni, byudjet/afzalliklar kabi suhbatda yig'ilgan "
                    "barcha ma'lumotni shu yerga qisqa va tushunarli qilib yoz."
                ),
            },
            'note': {
                'type': 'string',
                'description': "Mijozning aniq talablari, tafsilotlar (ixtiyoriy)",
            },
        },
        'required': ['phone', 'category'],
    },
}


FLIGHT_LEAD_TOOL = {
    'name': 'submit_flight_lead',
    'description': (
        "Mijoz parvoz/aviachipta sotib olishga qiziqish bildirganda va telefon raqamini "
        "bergandan keyin lead yaratadi (search_flights/book_flight ishlamagan yoki mijoz "
        "menejer orqali xarid qilishni istagan hollarda ishlatiladi). "
        "MUHIM: telefon raqamisiz chaqirma — avval mijozdan +998XXXXXXXXX formatida so'ra."
    ),
    'input_schema': {
        'type': 'object',
        'properties': {
            'phone': {
                'type': 'string',
                'description': 'Mijoz telefon raqami (+998XXXXXXXXX)',
            },
            'origin': {'type': 'string', 'description': "Jo'nash shahri yoki aeroport"},
            'destination': {'type': 'string', 'description': 'Manzil shahri yoki aeroport'},
            'departure_date': {'type': 'string', 'description': "Jo'nash sanasi YYYY-MM-DD (ixtiyoriy)"},
            'passengers': {'type': 'integer', 'description': "Yo'lovchilar soni", 'default': 1},
            'seat_class': {
                'type': 'string',
                'enum': ['economy', 'business', 'first'],
                'default': 'economy',
            },
            'full_name': {'type': 'string', 'description': 'Mijoz ismi (ixtiyoriy)'},
            'customer_analysis': {'type': 'string', 'description': 'AI tahliliy izohi (ixtiyoriy)'},
            'note': {'type': 'string', 'description': "Qo'shimcha talablar (ixtiyoriy)"},
        },
        'required': ['phone', 'origin', 'destination'],
    },
}


def get_all_tools() -> list[dict]:
    """
    Barcha mavjud tool'lar ro'yxatini qaytaradi (AI chatga taqdim etiladigan tool'lar).

    MUHIM — OWNER TALABI (tur/restoran oqimi o'zgardi):
    Tur paketlari va restoranlar uchun AI endi aniq variantlar (narx/tarif) ro'yxatini
    KO'RSATMAYDI va mijozdan biror raqamni "tanlashini" SO'RAMAYDI. Buning o'rniga faqat
    mijozning qiziqishlarini (yo'nalish, sana, odam soni, byudjet va h.k.) suhbat orqali
    yig'ib, submit_service_lead (category='travel' yoki 'restaurant') orqali guruhga
    yuboradi — aniq paket/filial ID'siz.
    Shu sababli RESTAURANT_SEARCH_TOOL, RESTAURANT_BOOK_TOOL, TOUR_SEARCH_TOOL,
    TOUR_LEAD_TOOL va RESTAURANT_LEAD_TOOL ataylab AI'ga TAQDIM ETILMAYDI (AI ularni
    chaqira olmaydi) — shu bilan "variantlarni ko'rsatish" imkoniyati texnik jihatdan
    ham yopiladi. Parvoz oqimi (search_flights/book_flight/submit_flight_lead)
    o'zgarishsiz qoladi.
    """
    return [
        FLIGHT_SEARCH_TOOL,
        FLIGHT_BOOK_TOOL,
        EVENT_SEARCH_TOOL,
        BOOKING_CANCEL_TOOL,
        USER_BOOKINGS_TOOL,
        NEARBY_PLACES_TOOL,
        USER_PREFERENCES_TOOL,
        SERVICE_LEAD_TOOL,
        FLIGHT_LEAD_TOOL,
    ]


def get_all_tools_for_bot() -> list[dict]:
    """
    Telegram bot uchun barcha tool'lar ro'yxatini qaytaradi.
    Botda AI chat bilan bir xil ishlashi uchun barcha tool'larni (shu jumladan
    olib tashlangan RESTAURANT_SEARCH_TOOL, RESTAURANT_BOOK_TOOL, TOUR_SEARCH_TOOL,
    TOUR_LEAD_TOOL, RESTAURANT_LEAD_TOOL va TRAIN_SEARCH_TOOL) qaytaradi.
    """
    return [
        FLIGHT_SEARCH_TOOL,
        TRAIN_SEARCH_TOOL,
        RESTAURANT_SEARCH_TOOL,
        RESTAURANT_BOOK_TOOL,
        FLIGHT_BOOK_TOOL,
        EVENT_SEARCH_TOOL,
        BOOKING_CANCEL_TOOL,
        USER_BOOKINGS_TOOL,
        NEARBY_PLACES_TOOL,
        USER_PREFERENCES_TOOL,
        TOUR_SEARCH_TOOL,
        TOUR_LEAD_TOOL,
        RESTAURANT_LEAD_TOOL,
        SERVICE_LEAD_TOOL,
        FLIGHT_LEAD_TOOL,
    ]