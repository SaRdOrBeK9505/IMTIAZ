"""App Settings URLs."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AppSettingViewSet, PublicSettingsView

router = DefaultRouter()
router.register('admin', AppSettingViewSet, basename='app-settings')

urlpatterns = [
    # Public endpoints
    path('public/', PublicSettingsView.as_view(), name='public-settings'),
    
    # Admin endpoints
    path('', include(router.urls)),
]
