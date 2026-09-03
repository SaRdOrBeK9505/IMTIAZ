"""Travel Content URL configuration."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    TravelReelViewSet, CuratedTripViewSet, CuratedTripImageViewSet,
    TravelReelListView, TravelReelDetailView,
    CuratedTripListView, CuratedTripDetailView,
)

router = DefaultRouter()
router.register('reels', TravelReelViewSet, basename='admin-travel-reels')
router.register('curated-trips', CuratedTripViewSet, basename='admin-curated-trips')
router.register('curated-trip-images', CuratedTripImageViewSet, basename='admin-curated-trip-images')

urlpatterns = [
    # Admin CRUD
    path('admin/', include(router.urls)),

    # Client — Reels
    path('reels/', TravelReelListView.as_view(), name='travel-reels-list'),
    path('reels/<uuid:pk>/', TravelReelDetailView.as_view(), name='travel-reels-detail'),

    # Client — IMTIAZ Travels
    path('curated-trips/', CuratedTripListView.as_view(), name='curated-trips-list'),
    path('curated-trips/<uuid:pk>/', CuratedTripDetailView.as_view(), name='curated-trips-detail'),
]
