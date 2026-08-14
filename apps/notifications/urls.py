from django.urls import path
from .views import (
    NotificationListView,
    NotificationReadView,
    NotificationReadAllView,
    TelegramWebhookView,
)

urlpatterns = [
    path('',              NotificationListView.as_view(),  name='notification-list'),
    path('read-all/',     NotificationReadAllView.as_view(), name='notification-read-all'),
    path('<uuid:pk>/read/', NotificationReadView.as_view(), name='notification-read'),
    path('telegram/webhook/', TelegramWebhookView.as_view(), name='telegram-webhook'),
]
