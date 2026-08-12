"""Legacy /api/crm/tours/ alias — backward compatibility."""

from django.urls import path

from apps.tours.views.crm_views import TourDashboardView

from . import tour_crm_urls

urlpatterns = [
    path('dashboard/', TourDashboardView.as_view(), name='crm-tour-dashboard-legacy'),
    *tour_crm_urls.urlpatterns,
]
