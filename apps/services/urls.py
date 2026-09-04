"""
Services URLs.

Admin (IsAdminUser):
  GET/POST              /api/services/admin/                  — Service CRUD
  GET/PUT/PATCH/DELETE  /api/services/admin/{id}/
  GET/POST              /api/services/admin/icons/            — ServiceIcon CRUD
  GET/PUT/PATCH/DELETE  /api/services/admin/icons/{id}/
  GET/POST              /api/services/admin/colors/           — ServiceColor CRUD
  GET/PUT/PATCH/DELETE  /api/services/admin/colors/{id}/

Client (IsAuthenticated):
  GET  /api/services/                 — aktiv xizmatlar ro'yxati
  GET  /api/services/{id}/            — xizmat tafsiloti
  GET  /api/services/icons/           — iconlar ro'yxati (tanlash uchun)
  GET  /api/services/icons/{id}/      — icon tafsiloti
  GET  /api/services/colors/          — ranglar ro'yxati (tanlash uchun)
  GET  /api/services/colors/{id}/     — rang tafsiloti
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ServiceAdminViewSet,
    ServiceColorAdminViewSet,
    ServiceColorDetailView,
    ServiceColorListView,
    ServiceDetailView,
    ServiceIconAdminViewSet,
    ServiceIconDetailView,
    ServiceIconListView,
    ServiceListView,
)

# ── Admin router ──────────────────────────────────────────────────────────────
admin_router = DefaultRouter()
admin_router.register('icons',  ServiceIconAdminViewSet,  basename='admin-service-icons')
admin_router.register('colors', ServiceColorAdminViewSet, basename='admin-service-colors')
admin_router.register('',       ServiceAdminViewSet,      basename='admin-services')

urlpatterns = [
    # Admin CRUD
    path('admin/', include(admin_router.urls)),

    # Client — icons
    path('icons/',        ServiceIconListView.as_view(),   name='service-icons-list'),
    path('icons/<uuid:pk>/', ServiceIconDetailView.as_view(), name='service-icons-detail'),

    # Client — colors
    path('colors/',        ServiceColorListView.as_view(),   name='service-colors-list'),
    path('colors/<uuid:pk>/', ServiceColorDetailView.as_view(), name='service-colors-detail'),

    # Client — services
    path('',           ServiceListView.as_view(),   name='services-list'),
    path('<uuid:pk>/', ServiceDetailView.as_view(), name='services-detail'),
]
