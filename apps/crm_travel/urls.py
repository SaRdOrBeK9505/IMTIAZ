"""Tur kompaniyasi vertikal URL'lar — birlashgan CRM API."""

from django.urls import include, path

from apps.crm_core.views import (
    TourOwnerDashboardView,
    TourStaffDetailView,
    TourStaffListCreateView,
)

from .views import TourBranchCreateView, TourOrganizationView

urlpatterns = [
    path('dashboard/', TourOwnerDashboardView.as_view(), name='tour-owner-dashboard'),
    path('organization/', TourOrganizationView.as_view(), name='tour-organization'),
    path('branches/', TourBranchCreateView.as_view(), name='tour-branch-create'),

    path('staff/', TourStaffListCreateView.as_view(), name='tour-staff-list'),
    path('staff/<uuid:pk>/', TourStaffDetailView.as_view(), name='tour-staff-detail'),

    path('leads/', include('apps.crm_core.lead_urls')),

    path('', include('apps.crm_travel.tour_crm_urls')),
]
