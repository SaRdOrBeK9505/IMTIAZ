from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CancelEventRegistrationView,
    CreateEventRegistrationView,
    EventDetailView,
    EventListView,
    EventRegistrationAdminViewSet,
    EventRegistrationDetailView,
    EventRegistrationListView,
)

router = DefaultRouter()
router.register('admin/registrations', EventRegistrationAdminViewSet, basename='event-registrations-admin')

urlpatterns = [
    # Event listings
    path('', EventListView.as_view(), name='event-list'),
    path('<uuid:pk>/', EventDetailView.as_view(), name='event-detail'),
    
    # User registrations
    path('registrations/', EventRegistrationListView.as_view(), name='event-registrations'),
    path('registrations/<uuid:pk>/', EventRegistrationDetailView.as_view(), name='event-registration-detail'),
    path('<uuid:event_id>/register/', CreateEventRegistrationView.as_view(), name='event-register'),
    path('registrations/<uuid:pk>/cancel/', CancelEventRegistrationView.as_view(), name='event-registration-cancel'),
    
    # Admin endpoints
    path('admin/', include(router.urls)),
]
