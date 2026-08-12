from django.urls import path

from .crm_views import (
    CRMNotificationListView,
    CRMNotificationReadAllView,
    CRMNotificationReadView,
)

urlpatterns = [
    path('', CRMNotificationListView.as_view(), name='crm-notification-list'),
    path('read-all/', CRMNotificationReadAllView.as_view(), name='crm-notification-read-all'),
    path('<uuid:pk>/read/', CRMNotificationReadView.as_view(), name='crm-notification-read'),
]
