"""
IMTIAZ OpenAPI (Swagger) konfiguratsiyasi — drf-spectacular.

Barcha API hujjatlashtirish sozlamalari shu modulda markazlashtirilgan.
"""

from __future__ import annotations

API_DESCRIPTION = """
# IMTIAZ API

Premium lifestyle concierge super-app backend — **Django REST Framework**.

---

## Autentifikatsiya

Tizim **JWT Bearer** autentifikatsiyasidan foydalanadi. Har bir kanal o'z **audience (`aud`)** claimiga ega:

| Kanal | Login endpoint | `aud` | Rollar |
|-------|----------------|-------|--------|
| **Mobile / Telegram** | `POST /api/auth/login/` | `mobile` | `customer` |
| **CRM** | `POST /api/crm/auth/login/` | `crm` | `owner_restaurant`, `restaurant_staff`, `owner_tour`, `tour_staff` |
| **Admin** | `POST /api/admin/auth/login/` | `admin` | `admin` |

Frontend **`user.role`** asosida qaysi CRM panelga yo'naltiradi.

**Token yangilash (barcha kanallar):** `POST /api/auth/token/refresh/` — login dan olingan `refresh` token yuboriladi.

**Swagger'da test qilish:** yuqoridagi tegishli **Authorize** tugmasidan token kiriting.

---

## CRM rollar

| Rol | Staff qo'shish endpoint |
|-----|------------------------|
| `owner_restaurant` | `POST /api/crm/restaurant/staff/` → yaratiladi `restaurant_staff` |
| `owner_tour` | `POST /api/crm/tour/staff/` → yaratiladi `tour_staff` |

Har bir kompaniya alohida `Organization`. Bir owner = bir kompaniya.

```
/api/crm/restaurant/   → Restoran CRM
/api/crm/tour/         → Tur kompaniyasi CRM
/api/crm/              → Legacy (restoran operatorlari)
/api/crm/tours/        → Legacy tur CRM
```

---

## Xatoliklar

Standart DRF format:

```json
{"detail": "Xato xabari"}
```

Validatsiya xatolari:

```json
{"phone": ["Bu maydon majburiy."], "password": ["Parol juda qisqa."]}
```

---

## Paginatsiya

Default: **PageNumberPagination**, `page_size=20`.

Query param: `?page=2`

---

## Rate limiting

| Scope | Limit |
|-------|-------|
| Anonim | 100/soat |
| Autentifikatsiya qilingan | 1000/soat |
| SMS OTP | 3/soat |
| AI chat | 60/daqiqa |
"""

OPENAPI_TAGS = [
    {
        'name': 'Health',
        'description': 'Monitoring va load balancer uchun sog\'lik tekshiruvi.',
    },
    {
        'name': 'Register',
        'description': 'Ro\'yxatdan o\'tish oqimi (4 qadam): OTP → verify → complete.',
    },
    {
        'name': 'Auth — Mobile',
        'description': 'Telegram Mini App va Flutter mobile autentifikatsiya (`aud=mobile`).',
    },
    {
        'name': 'Auth — CRM',
        'description': (
            'CRM panel autentifikatsiya (`aud=crm`). '
            'Owner va CRM xodimlar kirishi. Rol: owner_restaurant | restaurant_staff | owner_tour | tour_staff.',
        ),
    },
    {
        'name': 'Auth — CRM (O\'chirilgan)',
        'description': (
            '**410 Gone** — ishlatilmaydi, faqat hujjatlashtirish uchun ko\'rsatilgan. '
            'Owner Django admin orqali yaratiladi. Keyinroq URL lar olib tashlanadi.'
        ),
    },
    {
        'name': 'Auth — Admin',
        'description': 'Ichki admin panel autentifikatsiya (`aud=admin`).',
    },
    {
        'name': 'Users',
        'description': 'Foydalanuvchi profili, AI sozlamalari, hamyon.',
    },
    {
        'name': 'CRM Restaurant — Dashboard',
        'description': 'Restoran vertikali owner statistikasi va feature flags.',
    },
    {
        'name': 'CRM Restaurant — Staff',
        'description': 'Owner tomonidan xodim qo\'shish, yangilash, deaktivatsiya.',
    },
    {
        'name': 'CRM Restaurant — Tables',
        'description': 'Restoran stollari CRUD va holat boshqaruvi (branch_staff).',
    },
    {
        'name': 'CRM Restaurant — Menu',
        'description': 'Menyu kategoriyalari va taomlar (branch_staff).',
    },
    {
        'name': 'CRM Restaurant — Featured',
        'description': '"Nima qiziq" bo\'limi — tavsiya etilgan takliflar.',
    },
    {
        'name': 'CRM Restaurant — Bookings',
        'description': 'Restoran bronlari ro\'yxati va kuzatuvi.',
    },
    {
        'name': 'CRM Restaurant — Organization',
        'description': 'Tashkilot va filial profili (ish vaqti, manzil, galereya).',
    },
    {
        'name': 'CRM Restaurant — Analytics',
        'description': 'Bron statistikasi va hisobotlar (owner / view_analytics).',
    },
    {
        'name': 'CRM Restaurant — Staff Analytics',
        'description': 'Xodim faoliyati, reyting va statistika.',
    },
    {
        'name': 'CRM Travel — Dashboard',
        'description': 'Sayohat kompaniyasi owner statistikasi.',
    },
    {
        'name': 'CRM Travel — Staff',
        'description': 'Travel vertikali xodim boshqaruvi (owner).',
    },
    {
        'name': 'CRM Travel — Organization',
        'description': 'Travel tashkilot profili.',
    },
    {
        'name': 'CRM — Notifications',
        'description': 'CRM panel bildirishnomalari — yangi lead (new_lead), in-app.',
    },
    {
        'name': 'CRM Legacy',
        'description': (
            'Eski umumiy CRM endpointlar (`/api/crm/`). **Deprecated** — yangi integratsiya uchun '
            '`/api/crm/restaurant/` yoki `/api/crm/tour/` ishlating. Keyinroq olib tashlanadi.'
        ),
    },
    {
        'name': 'Bookings',
        'description': 'Polymorphic bron modeli — barcha xizmat turlari.',
    },
    {
        'name': 'AI Assistant',
        'description': 'Gemini function-calling, chat va tasdiqlash oqimi.',
    },
    {
        'name': 'Tours — User',
        'description': 'Tur paketlari va bronlar (mijoz-facing).',
    },
    {
        'name': 'Tours — CRM',
        'description': (
            'Tur kompaniyasi CRM. Asosiy namespace: `/api/crm/tour/`. '
            'Legacy alias: `/api/crm/tours/` (**deprecated**, keyinroq olib tashlanadi).'
        ),
    },
    {
        'name': 'Payments',
        'description': 'To\'lovlar va AlifPay integratsiyasi.',
    },
    {
        'name': 'Membership',
        'description': 'A\'zolik, waitlist va tier tizimi.',
    },
    {
        'name': 'QR Codes — User',
        'description': 'QR skanerlash va chegirma qo\'llash (mijoz-facing, `/api/qr/`).',
    },
    {
        'name': 'QR Codes — CRM',
        'description': 'QR kodlar boshqaruvi va analitika (`/api/crm/qr/`).',
    },
    {
        'name': 'Notifications',
        'description': 'Push va Telegram bildirishnomalar.',
    },
    {
        'name': 'Events',
        'description': 'Tadbirlar va chiptalar.',
    },
    {
        'name': 'Integrations',
        'description': 'Tashqi provayderlar API loglari (faqat admin).',
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
        if not path.startswith('/crm/qr/') or path.startswith('/crm/restaurant/'):
            continue
        for operation in methods.values():
            if not isinstance(operation, dict):
                continue
            op_id = operation.get('operationId')
            if op_id and not op_id.endswith('_legacy'):
                operation['operationId'] = f'{op_id}_legacy'
    return result


def build_openapi_servers(*, api_base_url: str = '', debug: bool = True) -> list[dict]:
    """Swagger UI uchun server ro'yxati.

    Production: API_BASE_URL birinchi (masalan https://api.medhomee.uz).
    DEBUG=True: localhost serverlar ham qo'shiladi.
    Production va API_BASE_URL bo'sh bo'lsa — SERVERS qo'shilmaydi; Swagger joriy
    domenni (api.medhomee.uz) ishlatadi.
    """
    servers: list[dict] = []
    if api_base_url:
        servers.append({'url': api_base_url.rstrip('/'), 'description': 'Production'})
    if debug:
        servers.extend([
            {'url': 'http://127.0.0.1:8000', 'description': 'Local development'},
            {'url': 'http://localhost:8000', 'description': 'Local development (alt)'},
        ])
    return servers


def build_spectacular_settings(*, api_base_url: str = '', debug: bool = True) -> dict:
    settings = {
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
        'SCHEMA_PATH_PREFIX_TRIM': True,
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
    servers = build_openapi_servers(api_base_url=api_base_url, debug=debug)
    if servers:
        settings['SERVERS'] = servers
    return settings
