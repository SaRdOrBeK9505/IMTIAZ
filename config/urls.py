"""
IMTIAZ — Asosiy URL konfiguratsiyasi.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import HealthCheckView
from apps.core.doc_views import (
    GuardedSpectacularAPIView,
    GuardedSpectacularSwaggerView,
)

urlpatterns = [
    # Health check — load balancer uchun (auth talab qilmaydi)
    path('health/', HealthCheckView.as_view(), name='health-check'),

    # Admin
    path('admin/', admin.site.urls),

    # API v1
    path('api/', include([
        # Auth & Users (login, telegram, sms, profile, wallet)
        path('', include('apps.users.urls')),

        # AI Assistant
        path('ai/', include('apps.ai_assistant.urls')),

        # Bronlar (umumiy)
        path('bookings/', include('apps.booking.urls')),

        # ─── Tur sayohat (user-facing) ────────────────────────────────────────
        path('tours/', include('apps.tours.urls.user_urls')),

        # ─── QR Kod (user-facing / web scanner) ──────────────────────────────
        path('qr/', include('apps.qr_codes.urls.user_urls')),

        # A'zolik
        path('membership/', include('apps.membership.urls')),

        # CRM — vertikal namespace (rol asosida)
        path('crm/restaurant/', include('apps.crm_restaurant.urls')),
        path('crm/travel/',     include('apps.crm_travel.urls')),

        # CRM — bildirishnomalar (lead, yangilanishlar)
        path('crm/notifications/', include('apps.notifications.crm_urls')),

        # Tadbirlar
        path('events/', include('apps.events.urls')),

        # To'lovlar
        path('payments/', include('apps.payments.urls')),

        # Bildirishnomalar
        path('notifications/', include('apps.notifications.urls')),

        # Bonus/Rewards system
        path('bonuses/', include('apps.bonuses.urls')),

        # Background Music (admin only)
        path('music/', include('apps.music.urls')),

        # Destinations (admin + client)
        path('destinations/', include('apps.destinations.urls')),

        # Travel Content — Reels va IMTIAZ Travels (admin + client)
        path('travel-content/', include('apps.travel_content.urls')),

        # User Support/Inquiries
        path('support/', include('apps.support.urls')),

        # App Settings (admin + public)
        path('settings/', include('apps.settings_app.urls')),

        # Banners (admin + client)
        path('banners/', include('apps.banners.urls')),

        # Services — ServiceIcon, ServiceColor, Service (admin + client)
        path('services/', include('apps.services.urls')),

        # Integrations logs (admin only)
        path('integrations/', include('apps.integrations.urls')),
    ])),

    # Swagger UI — subdomain root (https://api.medhomee.uz/)
    # schema faqat UI ichida ishlatiladi (/schema/)
    path('schema/', GuardedSpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', RedirectView.as_view(url='/', permanent=False)),
    path('api/docs', RedirectView.as_view(url='/', permanent=False)),
    path('', GuardedSpectacularSwaggerView.as_view(url_name='schema'), name='root'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
