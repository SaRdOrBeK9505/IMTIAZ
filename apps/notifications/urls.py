from django.urls import path
from .views import (
    NotificationListView,
    NotificationReadView,
    NotificationReadAllView,
    TelegramWebhookView,
)
from .promo_views import PromoDiscountListView, PromoDiscountDetailView

urlpatterns = [
    path('',              NotificationListView.as_view(),  name='notification-list'),
    path('read-all/',     NotificationReadAllView.as_view(), name='notification-read-all'),
    path('<uuid:pk>/read/', NotificationReadView.as_view(), name='notification-read'),
    path('telegram/webhook/', TelegramWebhookView.as_view(), name='telegram-webhook'),
    path('promo-discounts/', PromoDiscountListView.as_view(), name='promo-discounts-list'),
    path('promo-discounts/<uuid:pk>/', PromoDiscountDetailView.as_view(), name='promo-discounts-detail'),
]
