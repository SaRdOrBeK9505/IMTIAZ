from django.urls import path
from .views import ExternalProviderLogListView

urlpatterns = [
    path('logs/', ExternalProviderLogListView.as_view(), name='integration-logs'),
]
