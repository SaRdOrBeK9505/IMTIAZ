"""
IMTIAZ — Django Settings
"""

from __future__ import annotations

import logging
import os
import sys

import environ
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

_settings_logger = logging.getLogger('imtiaz.settings')


def _log_dev_notice(message: str) -> None:
    """runserver reloader settings ni ikki marta yuklaydi — faqat workerda log."""
    if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
        return
    _settings_logger.warning(message)

env = environ.Env(DEBUG=(bool, True))
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY    = env('SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG         = env('DEBUG')
ENABLE_API_DOCS = env.bool('ENABLE_API_DOCS', default=DEBUG)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# ─── APPS ─────────────────────────────────────────────────────────────────────
DJANGO_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'django_celery_beat',
    'django_celery_results',
]

LOCAL_APPS = [
    'apps.core',
    'apps.users',
    'apps.membership',
    'apps.booking',
    'apps.ai_assistant',
    'apps.payments',
    'apps.crm',
    'apps.crm_core',
    'apps.crm_restaurant',
    'apps.crm_travel',
    'apps.notifications',
    'apps.events',
    'apps.integrations',
    'apps.tours',       # Tur sayohat tizimi
    'apps.qr_codes',    # QR kod chegirma tizimi
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
AUTH_USER_MODEL = 'users.User'

AUTHENTICATION_BACKENDS = [
    'apps.users.backends.PhoneBackend',          # phone + password (asosiy)
    'django.contrib.auth.backends.ModelBackend', # zaxira
]

# ─── MIDDLEWARE ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'apps.core.logging_middleware.RequestLoggingMiddleware',   # ← Request log
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF      = 'config.urls'
WSGI_APPLICATION  = 'config.wsgi.application'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

# ─── DATABASE ─────────────────────────────────────────────────────────────────
# Alohida parametrlar — DATABASE_URL shart emas
DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     env('DB_NAME',     default='imtiaz_db'),
        'USER':     env('DB_USER',     default='imtiaz_user'),
        'PASSWORD': env('DB_PASSWORD', default=''),
        'HOST':     env('DB_HOST',     default='localhost'),
        'PORT':     env('DB_PORT',     default='5432'),
        'OPTIONS': {
            'connect_timeout': 10,
            'options':         '-c statement_timeout=30000',  # 30s query timeout
        },
        'CONN_MAX_AGE': 60,  # connection pool
    }
}

# Local dev uchun SQLite (DB_USE_SQLITE=True qo'ysangiz)
if env.bool('DB_USE_SQLITE', default=False):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME':   BASE_DIR / 'db.sqlite3',
        }
    }

# ─── CACHE / REDIS ────────────────────────────────────────────────────────────
_redis_url = env('REDIS_URL', default='redis://localhost:6379/0')

# Redis mavjudligini tekshirish — yo'q bo'lsa local-memory cache ishlatiladi
def _redis_available() -> bool:
    if not DEBUG:
        return True  # production'da Redis majburiy
    try:
        import redis as _redis
        r = _redis.from_url(_redis_url, socket_connect_timeout=1)
        r.ping()
        return True
    except Exception:
        return False

_use_redis = _redis_available()

if _use_redis:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': _redis_url,
            'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
        }
    }
    SESSION_ENGINE     = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    _log_dev_notice('Redis ulanmadi — local-memory cache ishlatilmoqda. Celery ishlamaydi.')
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# ─── CELERY ───────────────────────────────────────────────────────────────────
CELERY_BROKER_URL       = env('CELERY_BROKER_URL', default='redis://localhost:6379/1')
CELERY_RESULT_BACKEND   = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/2')
CELERY_ACCEPT_CONTENT   = ['json']
CELERY_TASK_SERIALIZER  = 'json'
CELERY_RESULT_SERIALIZER= 'json'
CELERY_TIMEZONE         = 'Asia/Tashkent'
CELERY_BEAT_SCHEDULER   = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE   = True   # task muvaffaqiyatli tugagandan so'ng ACK

# ─── REST FRAMEWORK ───────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
    # Rate limiting uchun throttle (10k user)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'ai_chat': '60/minute',    # AI chat alohida limit
        'sms_send': '3/hour',      # SMS yuborish limit
    },
}

# ─── JWT ──────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':    timedelta(minutes=env.int('ACCESS_TOKEN_LIFETIME_MINUTES', default=15)),
    'REFRESH_TOKEN_LIFETIME':   timedelta(days=env.int('REFRESH_TOKEN_LIFETIME_DAYS', default=30)),
    'ROTATE_REFRESH_TOKENS':    True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM':                'HS256',
    'SIGNING_KEY':              SECRET_KEY,
    'AUTH_HEADER_TYPES':        ('Bearer',),
    'USER_ID_FIELD':            'id',
    'USER_ID_CLAIM':            'user_id',
    # aud claim tekshiruvi — AudienceJWTAuthentication subklasslari orqali
    # (global AUDIENCE ishlatilmaydi — har panel o'z classida tekshiradi)
    'TOKEN_OBTAIN_SERIALIZER':  'rest_framework_simplejwt.serializers.TokenObtainPairSerializer',
}

# ─── JAZZMIN — Admin panel ────────────────────────────────────────────────────
JAZZMIN_SETTINGS = {
    # ── Brend ─────────────────────────────────────────────────────────────────
    'site_title':       'IMTIAZ Admin',
    'site_header':      'IMTIAZ',
    'site_brand':       'IMTIAZ',
    'site_logo':        None,           # 'img/logo.png' — logo qo'shilganda
    'site_logo_classes':'img-circle',
    'site_icon':        None,
    'welcome_sign':     'IMTIAZ Admin Paneliga Xush Kelibsiz',
    'copyright':        'IMTIAZ Premium Concierge © 2026',

    # ── Login sahifasi ────────────────────────────────────────────────────────
    'login_logo':       None,
    'login_logo_dark':  None,
    'login_screen_size':'col-xs-12 col-sm-8 col-md-4',

    # ── Navigatsiya ───────────────────────────────────────────────────────────
    'topmenu_links': [
        {'name': 'Bosh sahifa', 'url': 'admin:index', 'permissions': ['auth.view_user']},
        {'name': 'API Docs', 'url': '/api/docs/', 'new_window': True},
        {'name': 'Health', 'url': '/health/', 'new_window': True},
    ],

    'usermenu_links': [
        {'name': 'API Docs', 'url': '/api/docs/', 'new_window': True},
        {'model': 'users.user'},
    ],

    # ── Yon menyu ─────────────────────────────────────────────────────────────
    'show_sidebar':                True,
    'navigation_expanded':         True,
    'hide_apps':                   [],
    'hide_models':                 [],

    # Ikonkalar — FontAwesome 5
    'icons': {
        # Users
        'users.user':               'fas fa-users',
        'users.otpcode':            'fas fa-key',
        'users.wallettransaction':  'fas fa-wallet',
        # Membership
        'membership.membershiptier':    'fas fa-crown',
        'membership.usermembership':    'fas fa-id-card',
        'membership.waitlistapplication':'fas fa-list',
        'membership.subscription':      'fas fa-credit-card',
        'membership.promocode':         'fas fa-tags',
        # Booking
        'booking.booking':          'fas fa-calendar-check',
        'booking.flightbooking':    'fas fa-plane',
        'booking.trainbooking':     'fas fa-train',
        'booking.restaurantbooking':'fas fa-utensils',
        'booking.eventbooking':     'fas fa-ticket-alt',
        # AI Assistant
        'ai_assistant.conversationsession':  'fas fa-comments',
        'ai_assistant.conversationmessage':  'fas fa-comment',
        'ai_assistant.aiactionlog':          'fas fa-robot',
        # CRM
        'crm.organization':         'fas fa-building',
        'crm.branch':               'fas fa-store',
        'crm.branchstaff':          'fas fa-user-tie',
        # Payments
        'payments.payment':         'fas fa-money-bill-wave',
        'payments.paymentlog':      'fas fa-receipt',
        # Events
        'events.event':             'fas fa-star',
        'events.eventcategory':     'fas fa-th-list',
        # Notifications
        'notifications.notification':'fas fa-bell',
        # Integrations
        'integrations.externalproviderlog': 'fas fa-plug',
        # Auth
        'auth.user':                'fas fa-user',
        'auth.group':               'fas fa-users-cog',
        # Celery
        'django_celery_beat.periodictask': 'fas fa-clock',
        'django_celery_results.taskresult':'fas fa-tasks',
    },

    'default_icon_parents': 'fas fa-folder',
    'default_icon_children': 'fas fa-circle',

    # Yon menyuni guruhlab ko'rsatish
    'order_with_respect_to': [
        'auth',
        'users',
        'membership',
        'booking',
        'ai_assistant',
        'payments',
        'crm',
        'events',
        'notifications',
        'integrations',
        'django_celery_beat',
        'django_celery_results',
    ],

    # ── Ko'rinish ─────────────────────────────────────────────────────────────
    'default_theme_mode':     'auto',   # light | dark | auto (Jazzmin 3.x)
    'show_ui_builder':        False,   # production'da o'chiq
    'related_modal_active':   True,    # related fieldlar modal'da ochilsin
    'custom_css':             None,
    'custom_js':              None,
    'use_google_fonts_cdn':   False,   # offline uchun
    'show_fieldsets_as_tabs': False,
    'changeform_format':      'horizontal_tabs',
    'changeform_format_overrides': {
        'auth.user':  'collapsible',
        'users.user': 'collapsible',
    },
    'language_chooser': False,
}

JAZZMIN_UI_TWEAKS = {
    # Rang sxemasi — qora/premium ko'rinish
    'navbar_small_text':    False,
    'footer_small_text':    False,
    'body_small_text':      False,
    'brand_small_text':     False,

    # Asosiy rang: yorug' tema
    'brand_colour':         'navbar-light',
    'accent':               'accent-primary',
    'navbar':               'navbar-white navbar-light',
    'no_navbar_border':     False,
    'navbar_fixed':         True,
    'layout_boxed':         False,
    'footer_fixed':         False,
    'sidebar_fixed':        True,
    'sidebar':              'sidebar-light-primary',
    'sidebar_nav_small_text':False,
    'sidebar_disable_expand':False,
    'sidebar_nav_child_indent':True,
    'sidebar_nav_compact_style':False,
    'sidebar_nav_legacy_style':False,
    'sidebar_nav_flat_style':False,

    # Tema (Bootstrap 5 — light/dark data-bs-theme orqali)
    'theme':                'flatly',
    'button_classes': {
        'primary':   'btn-outline-primary',
        'secondary': 'btn-outline-secondary',
        'info':      'btn-info',
        'warning':   'btn-warning',
        'danger':    'btn-danger',
        'success':   'btn-success',
    },
    'actions_sticky_top':   True,
}

# ─── SPECTACULAR ──────────────────────────────────────────────────────────────
from apps.core.openapi import build_spectacular_settings

SPECTACULAR_SETTINGS = build_spectacular_settings()

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    'http://localhost:3000',
    'http://localhost:5173',
    'http://127.0.0.1:3000',
    'https://imtiaz-crm.vercel.app',
    'https://imtiaz-crm-restaurant.vercel.app',
    'https://imtiaz-crm-travel.vercel.app',
])
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[
    'http://localhost:3000',
    'http://localhost:5173',
    'https://imtiaz-crm.vercel.app',
    'https://imtiaz-crm-restaurant.vercel.app',
    'https://imtiaz-crm-travel.vercel.app',
])

# ─── Frontend / QR ────────────────────────────────────────────────────────────
FRONTEND_URL     = env('FRONTEND_URL', default='https://imtiaz-crm.vercel.app')
QR_SCAN_BASE_URL = env('QR_SCAN_BASE_URL', default=f'{FRONTEND_URL.rstrip("/")}/qr/')

# ─── AI PROVIDERS ─────────────────────────────────────────────────────────────
# Faol provider: 'gemini' (default) yoki 'claude'
AI_PROVIDER   = env('AI_PROVIDER', default='gemini')
AI_MAX_TOKENS = env.int('AI_MAX_TOKENS', default=1024)
AI_FOLLOWUP_MAX_TOKENS = env.int('AI_FOLLOWUP_MAX_TOKENS', default=512)
AI_HISTORY_LIMIT = env.int('AI_HISTORY_LIMIT', default=12)
AI_SKIP_SECOND_CALL = env.bool('AI_SKIP_SECOND_CALL', default=True)

# Gemini (Google)
GEMINI_API_KEY = env('GEMINI_API_KEY', default='')
GEMINI_MODEL   = env('GEMINI_MODEL',   default='gemini-2.5-flash')

# Claude (Anthropic) — zaxira provider
ANTHROPIC_API_KEY = env('ANTHROPIC_API_KEY', default='')
AI_MODEL          = env('AI_MODEL', default='claude-opus-4-5')

# ─── TELEGRAM ─────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN  = env('TELEGRAM_BOT_TOKEN',  default='')
TELEGRAM_BOT_SECRET = env('TELEGRAM_BOT_SECRET', default='')

# ─── SMS — DevSMS ─────────────────────────────────────────────────────────────
# https://devsms.uz — Bearer token bilan ishlaydi, login kerak emas
DEVSMS_TOKEN    = env('DEVSMS_TOKEN',    default='')
DEVSMS_BASE_URL = env('DEVSMS_BASE_URL', default='https://devsms.uz/api/send_sms.php')

if not DEVSMS_TOKEN:
    _log_dev_notice('DEVSMS_TOKEN topilmadi — SMS yuborish ishlamaydi. .env ga token qo\'shing.')

# ─── SMS — ESKIZ (o'chirildi, DevSMS ga o'tildi) ──────────────────────────────
# Qayta yoqish uchun: ESKIZ_EMAIL, ESKIZ_PASSWORD, ESKIZ_FROM ni .env ga qaytaring
# ESKIZ_EMAIL    = env('ESKIZ_EMAIL',    default='')
# ESKIZ_PASSWORD = env('ESKIZ_PASSWORD', default='')
# ESKIZ_FROM     = env('ESKIZ_FROM',     default='IMTIAZ')

# ─── PAYMENT PROVIDERS ────────────────────────────────────────────────────────
PAYME_MERCHANT_ID  = env('PAYME_MERCHANT_ID',  default='')
PAYME_SECRET_KEY   = env('PAYME_SECRET_KEY',   default='')
PAYME_TEST_MODE    = env.bool('PAYME_TEST_MODE', default=True)

CLICK_SERVICE_ID   = env('CLICK_SERVICE_ID',   default='')
CLICK_MERCHANT_ID  = env('CLICK_MERCHANT_ID',  default='')
CLICK_SECRET_KEY   = env('CLICK_SECRET_KEY',   default='')

MULTICARD_MERCHANT_ID = env('MULTICARD_MERCHANT_ID', default='')
MULTICARD_SECRET_KEY  = env('MULTICARD_SECRET_KEY',  default='')
MULTICARD_TEST_MODE   = env.bool('MULTICARD_TEST_MODE', default=True)

# ─── EXTERNAL INTEGRATIONS ────────────────────────────────────────────────────
AVIAKASSA_API_KEY  = env('AVIAKASSA_API_KEY',  default='')
AVIAKASSA_BASE_URL = env('AVIAKASSA_BASE_URL', default='')
RAILWAY_API_KEY    = env('RAILWAY_API_KEY',    default='')
RAILWAY_BASE_URL   = env('RAILWAY_BASE_URL',   default='')

# Bookhara avia GDS
BOOKHARA_EMAIL          = env('BOOKHARA_EMAIL',          default='')
BOOKHARA_PASSWORD       = env('BOOKHARA_PASSWORD',       default='')
BOOKHARA_BASE_URL       = env('BOOKHARA_BASE_URL',       default='https://avia-api-dev.bookhara.uz')
BOOKHARA_WEBHOOK_SECRET = env('BOOKHARA_WEBHOOK_SECRET', default='')
# Minimal depozit — pastga tushsa yangi bronlar to'xtatiladi (monitoring task)
BOOKHARA_MIN_DEPOSIT     = env('BOOKHARA_MIN_DEPOSIT',     default='5000000')   # 5 mln UZS
BOOKHARA_DEPOSIT_BUFFER  = env('BOOKHARA_DEPOSIT_BUFFER',  default='500000')    # pre-flight buffer

# AlifPay — mijozdan pul olish (checkout modeli)
ALIFPAY_TOKEN            = env('ALIFPAY_TOKEN',            default='')
ALIFPAY_SECRET_KEY       = env('ALIFPAY_SECRET_KEY',       default='')
ALIFPAY_WEBHOOK_URL      = env('ALIFPAY_WEBHOOK_URL',      default='')
ALIFPAY_TEST_MODE        = env.bool('ALIFPAY_TEST_MODE',    default=True)
ALIFPAY_RECEIPT_ENABLED  = env.bool('ALIFPAY_RECEIPT_ENABLED', default=False)
ALIFPAY_SPIC             = env('ALIFPAY_SPIC',             default='')

# ─── SENTRY (production error tracking) ───────────────────────────────────────
SENTRY_DSN = env('SENTRY_DSN', default='')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration(), RedisIntegration()],
        traces_sample_rate=0.2,     # 20% request'lar trace
        profiles_sample_rate=0.1,   # 10% profiling
        send_default_pii=False,     # PII yuborma
        environment='production' if not DEBUG else 'development',
    )

# ─── I18N ─────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'ru'
TIME_ZONE     = 'Asia/Tashkent'
USE_I18N      = True
USE_TZ        = True

# ─── STATIC / MEDIA ───────────────────────────────────────────────────────────
STATIC_URL  = env('STATIC_URL',  default='/static/')
STATIC_ROOT = BASE_DIR / env('STATIC_ROOT', default='staticfiles')
MEDIA_URL   = env('MEDIA_URL',   default='/media/')
MEDIA_ROOT  = BASE_DIR / env('MEDIA_ROOT',  default='media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── SECURITY (production) ────────────────────────────────────────────────────
if not DEBUG:
    SECURE_HSTS_SECONDS            = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_SSL_REDIRECT            = env.bool('SECURE_SSL_REDIRECT', default=False)
    SESSION_COOKIE_SECURE          = True
    CSRF_COOKIE_SECURE             = True
    SECURE_BROWSER_XSS_FILTER      = True
    SECURE_CONTENT_TYPE_NOSNIFF    = True
    X_FRAME_OPTIONS                = 'DENY'

# ─── LOGGING ──────────────────────────────────────────────────────────────────
_log_level = 'DEBUG' if DEBUG else 'INFO'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        # Development — o'qishga qulay
        'verbose': {
            'format': '[{levelname}] {asctime} {name}:{lineno} — {message}',
            'style':  '{',
        },
        # Production — JSON structured (ELK/Datadog uchun)
        'json': {
            '()': 'apps.core.log_formatters.JSONFormatter',
        },
    },

    'filters': {
        'require_debug_false': {'()': 'django.utils.log.RequireDebugFalse'},
        'require_debug_true':  {'()': 'django.utils.log.RequireDebugTrue'},
    },

    'handlers': {
        'console': {
            'class':     'logging.StreamHandler',
            'formatter': 'verbose' if DEBUG else 'json',
        },
        # Faylga yozish — production
        'file_app': {
            'class':       'logging.handlers.RotatingFileHandler',
            'filename':    str(BASE_DIR / 'logs' / 'app.log'),
            'maxBytes':    10 * 1024 * 1024,   # 10 MB
            'backupCount': 5,
            'formatter':   'json',
            'encoding':    'utf-8',
        },
        'file_errors': {
            'class':       'logging.handlers.RotatingFileHandler',
            'filename':    str(BASE_DIR / 'logs' / 'errors.log'),
            'maxBytes':    10 * 1024 * 1024,
            'backupCount': 10,
            'formatter':   'json',
            'level':       'ERROR',
            'encoding':    'utf-8',
        },
        'file_ai': {
            'class':       'logging.handlers.RotatingFileHandler',
            'filename':    str(BASE_DIR / 'logs' / 'ai.log'),
            'maxBytes':    20 * 1024 * 1024,
            'backupCount': 10,
            'formatter':   'json',
            'encoding':    'utf-8',
        },
    },

    'root': {
        'handlers': ['console'],
        'level': _log_level,
    },

    'loggers': {
        'django': {
            'handlers':  ['console', 'file_errors'],
            'level':     'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers':  ['console', 'file_errors'],
            'level':     'WARNING',
            'propagate': False,
        },
        'apps': {
            'handlers':  ['console', 'file_app', 'file_errors'],
            'level':     _log_level,
            'propagate': False,
        },
        # AI harakatlari alohida log fayl
        'apps.ai_assistant': {
            'handlers':  ['console', 'file_ai', 'file_errors'],
            'level':     _log_level,
            'propagate': False,
        },
        # Request log
        'apps.requests': {
            'handlers':  ['console', 'file_app'],
            'level':     'INFO',
            'propagate': False,
        },
        # Celery
        'celery': {
            'handlers':  ['console', 'file_app'],
            'level':     'INFO',
            'propagate': False,
        },
    },
}
