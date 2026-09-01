"""Bonuses app URLs."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    BonusCategoryViewSet,
    BonusByCategoryView,
    GenerateQRCodeView,
    ScanBonusQRView,
    UserBonusListView,
)

router = DefaultRouter()
router.register('categories', BonusCategoryViewSet, basename='bonus-categories')

urlpatterns = [
    # Admin endpoints
    path('admin/', include(router.urls)),
    path('admin/scan/', ScanBonusQRView.as_view(), name='bonus-scan'),
    
    # User endpoints
    path('', UserBonusListView.as_view(), name='user-bonuses'),
    path('by-category/<str:service_type>/', BonusByCategoryView.as_view(), name='bonuses-by-category'),
    path('<uuid:pk>/qr/', GenerateQRCodeView.as_view(), name='bonus-generate-qr'),
]
