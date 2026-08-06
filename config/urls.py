"""
IMTIAZ — Asosiy URL konfiguratsiyasi.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework_simplejwt.views import TokenRefreshView
from apps.core.views import HealthCheckView

urlpatterns = [
    # Health check — load balancer uchun (auth talab qilmaydi)
    path('health/', HealthCheckView.as_view(), name='health-check'),

    # Admin
    path('admin/', admin.site.urls),

    # API v1
    path('api/', include([
        # Auth & Users
        path('', include('apps.users.urls')),
        path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

        # AI Assistant
        path('ai/', include('apps.ai_assistant.urls')),

        # Bronlar
        path('bookings/', include('apps.booking.urls')),

        # A'zolik
        path('membership/', include('apps.membership.urls')),

        # CRM (filial paneli)
        path('crm/', include('apps.crm.urls')),

        # Tadbirlar
        path('events/', include('apps.events.urls')),

        # To'lovlar
        path('payments/', include('apps.payments.urls')),

        # Bildirishnomalar
        path('notifications/', include('apps.notifications.urls')),

        # Integrations logs (admin only)
        path('integrations/', include('apps.integrations.urls')),
    ])),

    # API Docs (faqat DEBUG yoki ichki network)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/',   SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/',  SpectacularRedocView.as_view(url_name='schema'),   name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
