"""Destination URLs.

Admin (IsAdminUser):
  GET/POST            /api/destinations/admin/
  GET/PUT/PATCH/DELETE /api/destinations/admin/{id}/

Client (AllowAny):
  GET  /api/destinations/           — ro'yxat (?group=popular|signature)
  GET  /api/destinations/{id}/      — tafsilot
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DestinationDetailView, DestinationListView, DestinationViewSet

router = DefaultRouter()
router.register('', DestinationViewSet, basename='admin-destinations')

urlpatterns = [
    # Admin
    path('admin/', include(router.urls)),

    # Client
    path('', DestinationListView.as_view(), name='destinations-list'),
    path('<uuid:pk>/', DestinationDetailView.as_view(), name='destinations-detail'),
]
