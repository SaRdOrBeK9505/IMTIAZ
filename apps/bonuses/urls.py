"""Bonuses app URLs — shablon boshqaruvi + birlashtirilgan client ro'yxati."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BonusCategoryViewSet, MyBonusesView

router = DefaultRouter()
router.register('categories', BonusCategoryViewSet, basename='bonus-categories')

urlpatterns = [
    path('admin/', include(router.urls)),   # /publish/ va /assign/ shu ichida, DefaultRouter avtomatik ulaydi
    path('', MyBonusesView.as_view(), name='my-bonuses'),
]
