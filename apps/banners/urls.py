"""Banners app URLs."""

from django.urls import path
from .views import (
    AdminBannerListView,
    AdminBannerDetailView,
    AdminBannerUploadView,
    ClientBannerListView,
    ClientBannerDetailView,
)

urlpatterns = [
    # Admin endpoints (himoyalangan)
    path('admin/', AdminBannerListView.as_view(), name='admin-banner-list'),
    path('admin/<uuid:pk>/', AdminBannerDetailView.as_view(), name='admin-banner-detail'),
    path('admin/upload/', AdminBannerUploadView.as_view(), name='admin-banner-upload'),
    
    # Client endpoints (public)
    path('', ClientBannerListView.as_view(), name='client-banner-list'),
    path('<uuid:pk>/', ClientBannerDetailView.as_view(), name='client-banner-detail'),
]
