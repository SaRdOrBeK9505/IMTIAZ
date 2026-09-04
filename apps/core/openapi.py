"""
IMTIAZ OpenAPI (Swagger) konfiguratsiyasi — drf-spectacular.

Barcha API hujjatlashtirish sozlamalari shu modulda markazlashtirilgan.
"""

from __future__ import annotations

API_DESCRIPTION = """
# IMTIAZ API

Premium lifestyle concierge super-app backend — Django REST Framework.

**Autentifikatsiya:** JWT Bearer. Token yangilash: `POST /api/auth/token/refresh/`
**Paginatsiya:** `?page=2` (default page_size=20)
"""

OPENAPI_TAGS = [
    # ─── TELEGRAM MINI APP ────────────────────────────────────────────────────────
    {
        'name': 'Telegram Mini App — Auth',
        'description': 'Telegram Mini App autentifikatsiya va ro\'yxatdan o\'tish (`aud=mobile`).',
    },
    {
        'name': 'Telegram Mini App — Profile',
        'description': 'Foydalanuvchi profili, AI sozlamalari, hamyon.',
    },
    {
        'name': 'Telegram Mini App — AI Assistant',
        'description': 'Gemini function-calling, chat va tasdiqlash oqimi.',
    },
    {
        'name': 'Telegram Mini App — Tours',
        'description': 'Tur paketlari va bronlar (mijoz-facing).',
    },
    {
        'name': 'Telegram Mini App — Bookings',
        'description': 'Polymorphic bron modeli — barcha xizmat turlari.',
    },
    {
        'name': 'Telegram Mini App — QR Codes',
        'description': 'QR skanerlash va chegirma qo\'llash (mijoz-facing, `/api/qr/`).',
    },
    {
        'name': 'Telegram Mini App — Membership',
        'description': 'A\'zolik, waitlist va tier tizimi.',
    },
    {
        'name': 'Telegram Mini App — Payments',
        'description': 'To\'lovlar va AlifPay integratsiyasi.',
    },
    {
        'name': 'Telegram Mini App — Notifications',
        'description': 'Push va Telegram bildirishnomalar.',
    },
    {
        'name': 'Telegram Mini App — Events',
        'description': 'Tadbirlar va chiptalar.',
    },
    {
        'name': 'Telegram Mini App — Bonuses',
        'description': 'Bonus/rewards tizimi.',
    },
    {
        'name': 'Telegram Mini App — Settings',
        'description': 'Ilova sozlamalari (ommaviy).',
    },
    {
        'name': 'Telegram Mini App — Banners',
        'description': 'Reklama bannerlari (client-facing).',
    },
    {
        'name': 'Telegram Mini App — Destinations',
        'description': 'Manzillar va mamlakatlar (client-facing).',
    },
    {
        'name': 'Telegram Mini App — Travel Content',
        'description': 'Reels va kuratsiyalangan sayohat kontenti (client-facing).',
    },
    {
        'name': 'Telegram Mini App — Support',
        'description': 'Foydalanuvchi so\'rovlari tizimi.',
    },
    # ─── CRM ────────────────────────────────────────────────────────────────────
    {
        'name': 'CRM — Auth',
        'description': (
            'CRM panel autentifikatsiya (`aud=crm`). '
            'Owner va CRM xodimlar kirishi. Rol: owner_restaurant | restaurant_staff | owner_tour | tour_staff.',
        ),
    },
    {
        'name': 'CRM — Restaurant Dashboard',
        'description': 'Restoran vertikali owner statistikasi va feature flags.',
    },
    {
        'name': 'CRM — Restaurant Staff',
        'description': 'Owner tomonidan xodim qo\'shish, yangilash, deaktivatsiya.',
    },
    {
        'name': 'CRM — Restaurant Tables',
        'description': 'Restoran stollari CRUD va holat boshqaruvi (branch_staff).',
    },
    {
        'name': 'CRM — Restaurant Menu',
        'description': 'Menyu kategoriyalari va taomlar (branch_staff).',
    },
    {
        'name': 'CRM — Restaurant Featured',
        'description': '"Nima qiziq" bo\'limi — tavsiya etilgan takliflar.',
    },
    {
        'name': 'CRM — Restaurant Bookings',
        'description': 'Restoran bronlari ro\'yxati va kuzatuvi.',
    },
    {
        'name': 'CRM — Restaurant Leads',
        'description': 'Restoran leadlari boshqaruvi (accept/reject workflow).',
    },
    {
        'name': 'CRM — Restaurant Organization',
        'description': 'Tashkilot va filial profili (ish vaqti, manzil, galereya).',
    },
    {
        'name': 'CRM — Restaurant Analytics',
        'description': 'Bron statistikasi va hisobotlar (owner / view_analytics).',
    },
    {
        'name': 'CRM — Restaurant Staff Analytics',
        'description': 'Xodim faoliyati, reyting va statistika.',
    },
    {
        'name': 'CRM — Travel Dashboard',
        'description': 'Sayohat kompaniyasi owner statistikasi.',
    },
    {
        'name': 'CRM — Travel Staff',
        'description': 'Travel vertikali xodim boshqaruvi (owner).',
    },
    {
        'name': 'CRM — Travel Organization',
        'description': 'Travel tashkilot profili.',
    },
    {
        'name': 'CRM — Travel Tours',
        'description': (
            'Tur kompaniyasi CRM. Asosiy namespace: `/api/crm/tour/`. '
            'Legacy alias: `/api/crm/tours/` (**deprecated**, keyinroq olib tashlanadi).'
        ),
    },
    {
        'name': 'CRM — Travel Destinations',
        'description': 'Tur kompaniyasi yo\'nalishlari va galereyasi.',
    },
    {
        'name': 'CRM — Travel AI Leads',
        'description': 'AI orqali kelgan tur leadlari boshqaruvi.',
    },
    {
        'name': 'CRM — Travel Clients',
        'description': 'Tur kompaniyasi mijozlari tarixi va xaridlar.',
    },
    {
        'name': 'CRM — Travel Packages',
        'description': 'Tur paketlari CRUD va mavjudlik boshqaruvi.',
    },
    {
        'name': 'CRM — Travel Bookings',
        'description': 'Tur bronlari ro\'yxati, tasdiqlash va voaucher generatsiya.',
    },
    {
        'name': 'CRM — Travel Analytics',
        'description': 'Tur kompaniyasi analitikasi va statistikasi.',
    },
    {
        'name': 'CRM — Travel Dashboard',
        'description': 'Tur kompaniyasi dashboard va ko\'rsatkichlar.',
    },
    {
        'name': 'CRM — Notifications',
        'description': 'CRM panel bildirishnomalari — yangi lead (new_lead), in-app.',
    },
    {
        'name': 'CRM — QR Codes',
        'description': 'QR kodlar boshqaruvi va analitika (`/api/crm/qr/`).',
    },
    {
        'name': 'CRM — Promo Discounts',
        'description': 'Bonus kategoriyalari va chegirma tizimi boshqaruvi.',
    },
    # ─── ADMIN PANEL ─────────────────────────────────────────────────────────────
    {
        'name': 'Admin — Auth',
        'description': 'Ichki admin panel autentifikatsiya (`aud=admin`).',
    },
    {
        'name': 'Admin — Settings',
        'description': 'Ilova sozlamalari va konfiguratsiya.',
    },
    {
        'name': 'Admin — Banners',
        'description': 'Reklama bannerlari boshqaruvi.',
    },
    {
        'name': 'Admin — Destinations',
        'description': 'Manzillar boshqaruvi.',
    },
    {
        'name': 'Admin — Travel Content',
        'description': 'Reels va kuratsiyalangan sayohat kontenti.',
    },
    {
        'name': 'Admin — Support',
        'description': 'Foydalanuvchi so\'rovlari tizimi.',
    },
    {
        'name': 'Admin — Integrations',
        'description': 'Tashqi provayderlar API loglari (faqat admin).',
    },
    {
        'name': 'Admin — Music',
        'description': 'Fon musiqasi boshqaruvi.',
    },
    # ─── GENERAL ─────────────────────────────────────────────────────────────────
    {
        'name': 'Health',
        'description': 'Monitoring va load balancer uchun sog\'lik tekshiruvi.',
    },
]

TAG_ORDER = [t['name'] for t in OPENAPI_TAGS]


def spectacular_preprocessors(endpoints):
    """Endpoint'larni tag tartibiga ko'ra saralash."""
    def sort_key(endpoint):
        methods, path, callback, name = endpoint
        tag = getattr(getattr(callback, 'cls', None), 'schema_tags', None)
        if not tag and hasattr(callback, 'view_class'):
            tag = getattr(callback.view_class, 'schema_tags', None)
        first_tag = tag[0] if tag else 'ZZZ'
        try:
            return (TAG_ORDER.index(first_tag), path)
        except ValueError:
            return (len(TAG_ORDER), path)

    return sorted(endpoints, key=sort_key)


def spectacular_postprocess_fix_legacy_operation_ids(result, generator, request, public):
    """Legacy va yangi URL da bir xil view — operationId collision oldini olish."""
    paths = result.get('paths', {})
    for path, methods in paths.items():
        if not path.startswith('/api/crm/qr/') or path.startswith('/api/crm/restaurant/'):
            continue
        for operation in methods.values():
            if not isinstance(operation, dict):
                continue
            op_id = operation.get('operationId')
            if op_id and not op_id.endswith('_legacy'):
                operation['operationId'] = f'{op_id}_legacy'
    return result


def build_spectacular_settings() -> dict:
    """OpenAPI/Swagger sozlamalari.

    Path lar to'liq ko'rinadi (/api/auth/login/) — Swagger joriy host bilan
    birlashtiradi. Alohida SERVERS ro'yxati kerak emas.
    """
    return {
        'TITLE': 'IMTIAZ API',
        'DESCRIPTION': API_DESCRIPTION,
        'VERSION': '1.1.0',
        'CONTACT': {
            'name': 'IMTIAZ Backend Team',
            'email': 'dev@imtiaz.uz',
        },
        'LICENSE': {
            'name': 'Proprietary',
        },
        'SERVE_INCLUDE_SCHEMA': False,
        'COMPONENT_SPLIT_REQUEST': True,
        'SCHEMA_PATH_PREFIX': r'/api/',
        'SCHEMA_PATH_PREFIX_TRIM': False,
        'SORT_OPERATIONS': False,
        'TAGS': OPENAPI_TAGS,
        'PREPROCESSING_HOOKS': [
            'apps.core.openapi.spectacular_preprocessors',
        ],
        'POSTPROCESSING_HOOKS': [
            'apps.core.openapi.spectacular_postprocess_fix_legacy_operation_ids',
        ],
        'ENUM_NAME_OVERRIDES': {
            'AIAutonomyLevelEnum': 'apps.users.models.AIAutonomyLevel',
            'BookingStatusEnum': 'apps.booking.models.BookingStatus',
            'ServiceTypeEnum': 'apps.booking.models.ServiceType',
            'PaymentStatusEnum': 'apps.payments.models.PaymentStatus',
            'WaitlistStatusEnum': 'apps.membership.models.WaitlistApplication.Status',
            'SubscriptionStatusEnum': 'apps.membership.models.Subscription.Status',
            'NotificationStatusEnum': 'apps.notifications.models.Notification.Status',
            'BusinessTypeEnum': 'apps.crm.models.BusinessType',
            'TableStatusEnum': 'apps.crm.models.TableStatus',
            'UserRoleEnum': 'apps.users.models.UserRole',
            'LeadStageEnum': 'apps.crm_core.models.Lead.Stage',
            'HotelPreferenceEnum': 'apps.booking.models.TourBooking.HotelPreference',
            'AvailabilityStatusEnum': 'apps.tours.models.AvailabilityStatus',
            'VoucherStatusEnum': 'apps.tours.models.VoucherStatus',
            'RedemptionStatusEnum': 'apps.qr_codes.models.RedemptionStatus',
            'EventStatusEnum': 'apps.events.models.Event.Status',
            'AIActionStatusEnum': 'apps.ai_assistant.models.AIActionLog.ActionStatus',
        },
        'SWAGGER_UI_SETTINGS': {
            'deepLinking': True,
            'persistAuthorization': True,
            'displayOperationId': True,
            'filter': True,
            'docExpansion': 'none',
            'defaultModelsExpandDepth': 2,
            'defaultModelExpandDepth': 2,
            'syntaxHighlight.theme': 'monokai',
        },
        'REDOC_UI_SETTINGS': {
            'hideDownloadButton': False,
            'expandResponses': '200,201',
            'pathInMiddlePanel': True,
        },
    }
