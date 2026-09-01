"""Background Music URLs."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ActiveMusicView,
    BackgroundMusicViewSet,
    ControlMusicView,
)

router = DefaultRouter()
router.register('', BackgroundMusicViewSet, basename='background-music')

urlpatterns = [
    path('admin/', include(router.urls)),
    path('admin/active/', ActiveMusicView.as_view(), name='music-active'),
    path('admin/<uuid:pk>/control/', ControlMusicView.as_view(), name='music-control'),
]
