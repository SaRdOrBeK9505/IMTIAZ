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
    'description': 'Tanlangan parvozni bronlaydi va to\'lovni boshlaydi.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'offer_id': {'type': 'string', 'description': 'search_flights natijasidan offer ID'},
            'passengers': {'type': 'integer'},
            'payment_method': {
                'type': 'string',
                'enum': ['payme', 'click', 'multicard', 'wallet'],
                'default': 'wallet',
            },
        },
        'required': ['offer_id'],
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
        'Yaxshi takliflar berish uchun ishlatiladi.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': {},
        'required': [],
    },
}


def get_all_tools() -> list[dict]:
    """Barcha mavjud tool'lar ro'yxatini qaytaradi."""
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
    ]
