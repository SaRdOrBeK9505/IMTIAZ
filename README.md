# IMTIAZ — Premium Lifestyle Concierge Super-App

AI-yordamchi asosidagi premium xizmatlar platformasi.
Parvoz, poyezd, restoran, sport va eksklyuziv tadbirlar — bitta ilovada.

---

## Texnologiyalar

| Qatlam | Texnologiya |
|--------|-------------|
| Backend | Django 6 + DRF |
| AI | Google Gemini 2.5 Flash (asosiy) / Claude (zaxira) |
| SMS | Eskiz.uz gateway |
| Vazifalar | Celery + Redis |
| Hujjat | drf-spectacular (Swagger/ReDoc) |
| Deploy | Ubuntu + Nginx + Gunicorn |

---

## Tezkor boshlash

```bash
# 1. Virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# 2. Paketlar
pip install -r requirements.txt

# 3. .env sozlash
cp .env.example .env
# .env faylini to'ldiring (Gemini API key, Eskiz login va h.k.)

# 4. DB
python manage.py migrate
python manage.py setup_periodic_tasks   # Celery Beat tasklar

# 5. Superuser
python manage.py createsuperuser

# 6. Server
python manage.py runserver
```

API docs: http://localhost:8000/api/docs/

---

## Arxitektura

```
config/
├── settings.py          # Barcha sozlamalar
├── urls.py              # Asosiy routing
└── celery.py            # Celery konfiguratsiyasi

apps/
├── core/                # Abstract modellar, permissions, logging
├── users/               # Auth (Telegram + SMS OTP), hamyon
├── membership/          # Tier, Waitlist, Subscription
├── ai_assistant/        # Chat, tool-calling, AI logs
│   ├── providers/       # Claude + Gemini (settings.AI_PROVIDER)
│   └── tools/           # Function-calling definitsiyalar
├── booking/             # Polymorphic: parvoz, poyezd, restoran, tadbir
├── payments/            # Abstract provider, stub → haqiqiy (TBD)
├── crm/                 # Organization → Branch, xodimlar, analytics
├── events/              # Eksklyuziv tadbirlar katalogi
├── notifications/       # Telegram bot, Celery tasks
└── integrations/        # Tashqi API adapter (aviakassa, temir yo'l)
```

---

## Auth oqimi

```
Telegram Mini App:
  POST /api/auth/telegram/   { init_data } → { access, refresh, user }

SMS OTP (Eskiz):
  POST /api/auth/sms/send/   { phone }           → SMS yuboriladi
  POST /api/auth/sms/verify/ { phone, code }     → { access, refresh, user }

JWT yangilash:
  POST /api/auth/token/refresh/ { refresh }      → { access }
```

---

## AI Provider

`settings.AI_PROVIDER` orqali boshqariladi:

```env
AI_PROVIDER=gemini      # Google Gemini 2.5 Flash (default)
AI_PROVIDER=claude      # Anthropic Claude
```

Provider almashtirish uchun faqat `.env` ni o'zgartirish kifoya.

---

## To'lov tizimi

Provayder hali tanlanmagan. Hozir **stub** rejimida ishlaydi.

Yangi provider qo'shish:
1. `apps/payments/providers/<name>.py` — `BasePaymentProvider` implement qiling
2. `apps/payments/services.py` → `registry` ga qo'shing
3. `.env` ga kalitlarni yozing

---

## Deploy

```bash
# Birinchi marta
bash deploy/deploy.sh --setup

# Yangilanish
bash deploy/deploy.sh
```

Nginx config: `deploy/nginx.conf`
Systemd services: `deploy/gunicorn.service`, `deploy/celery_worker.service`

---

## API Endpoints xulosa

| Method | URL | Tavsif |
|--------|-----|--------|
| POST | `/api/auth/telegram/` | Telegram kirish |
| POST | `/api/auth/sms/send/` | OTP SMS yuborish |
| POST | `/api/auth/sms/verify/` | OTP tasdiqlash |
| GET/PATCH | `/api/users/me/` | Profil |
| GET | `/api/wallet/` | Hamyon |
| POST | `/api/ai/chat/` | AI suhbat |
| GET | `/api/ai/sessions/` | Sessiyalar |
| GET | `/api/bookings/` | Bronlar tarixi |
| GET | `/api/membership/tiers/` | A'zolik darajalari |
| POST | `/api/membership/waitlist/` | Ariza topshirish |
| GET | `/api/payments/` | To'lovlar tarixi |
| POST | `/api/payments/wallet/` | Hamyon to'lov |
| GET | `/api/events/` | Tadbirlar |
| GET | `/api/notifications/` | Bildirishnomalar |
| GET | `/health/` | Sog'lik tekshiruvi |

To'liq hujjat: `/api/docs/` (Swagger UI)
