"""Tur kompaniyasi vertikal URL'lar — birlashgan CRM API."""

from django.urls import include, path

from apps.crm_core.views import (
    TourOwnerDashboardView,
    TourStaffDetailView,
    TourStaffListCreateView,
)

from .views import TourBranchCreateView, TourOrganizationView
from .tour_lead_views import TourLeadDetailView, TourLeadListView

urlpatterns = [
    path('dashboard/', TourOwnerDashboardView.as_view(), name='tour-owner-dashboard'),
    path('organization/', TourOrganizationView.as_view(), name='tour-organization'),
    path('branches/', TourBranchCreateView.as_view(), name='tour-branch-create'),

    path('staff/', TourStaffListCreateView.as_view(), name='tour-staff-list'),
    path('staff/<uuid:pk>/', TourStaffDetailView.as_view(), name='tour-staff-detail'),

    path('leads/', include('apps.crm_core.lead_urls')),
    path('ai-leads/', TourLeadListView.as_view(), name='tour-ai-leads-list'),
    path('ai-leads/<uuid:pk>/', TourLeadDetailView.as_view(), name='tour-ai-lead-detail'),

    path('', include('apps.crm_travel.tour_crm_urls')),
]
