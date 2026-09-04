"""Tur kompaniyasi vertikal URL'lar — birlashgan CRM API."""

from django.urls import include, path

from apps.crm_core.views import (
    TourOwnerDashboardView,
    TourStaffDetailView,
    TourStaffListCreateView,
)

from .views import TourBranchCreateView, TourOrganizationView
from .tour_lead_views import TourLeadListView, TourLeadDetailView, TourLeadStatsView, TourLeadConfirmedListView
from .client_views import TourClientListView, TourClientDetailView, TourClientPurchasesView

urlpatterns = [
    path('dashboard/', TourOwnerDashboardView.as_view(), name='tour-owner-dashboard'),
    path('organization/', TourOrganizationView.as_view(), name='tour-organization'),
    path('branches/', TourBranchCreateView.as_view(), name='tour-branch-create'),

    path('staff/', TourStaffListCreateView.as_view(), name='tour-staff-list'),
    path('staff/<uuid:pk>/', TourStaffDetailView.as_view(), name='tour-staff-detail'),

    path('leads/', include('apps.crm_core.lead_urls')),
    path('ai-leads/', TourLeadListView.as_view(), name='tour-ai-leads-list'),
    path('ai-leads/stats/', TourLeadStatsView.as_view(), name='tour-ai-leads-stats'),
    path('ai-leads/confirmed/', TourLeadConfirmedListView.as_view(), name='tour-ai-leads-confirmed'),
    path('ai-leads/<uuid:pk>/', TourLeadDetailView.as_view(), name='tour-ai-lead-detail'),

    path('clients/', TourClientListView.as_view(), name='tour-clients-list'),
    path('clients/<uuid:pk>/', TourClientDetailView.as_view(), name='tour-client-detail'),
    path('clients/<uuid:pk>/purchases/', TourClientPurchasesView.as_view(), name='tour-client-purchases'),

    path('', include('apps.crm_travel.tour_crm_urls')),
]
