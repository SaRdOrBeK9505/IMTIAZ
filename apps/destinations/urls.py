"""Destination URLs."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CountryListView,
    CountryViewSet,
    DestinationDetailView,
    DestinationImageViewSet,
    DestinationListView,
    DestinationViewSet,
)

router = DefaultRouter()
router.register('countries', CountryViewSet, basename='destination-countries')
router.register('', DestinationViewSet, basename='destinations')
router.register('images', DestinationImageViewSet, basename='destination-images')

urlpatterns = [
    # Admin endpoints
    path('admin/', include(router.urls)),
    
    # Client endpoints
    path('countries/', CountryListView.as_view(), name='destinations-countries'),
    path('', DestinationListView.as_view(), name='destinations-list'),
    path('<uuid:pk>/', DestinationDetailView.as_view(), name='destinations-detail'),
]
