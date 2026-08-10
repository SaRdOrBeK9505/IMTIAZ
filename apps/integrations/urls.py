from django.urls import path
from .views import ExternalProviderLogListView
from .webhooks import bookhara_status_webhook

urlpatterns = [
    path('logs/', ExternalProviderLogListView.as_view(), name='integration-logs'),
    path('webhooks/bookhara/status/', bookhara_status_webhook, name='bookhara-webhook'),
]
