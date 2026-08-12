"""Lead pipeline URL'lar."""

from django.urls import path

from .lead_views import LeadDetailView, LeadKanbanView, LeadListView, LeadStatsView

urlpatterns = [
    path('stats/', LeadStatsView.as_view(), name='crm-leads-stats'),
    path('kanban/', LeadKanbanView.as_view(), name='crm-leads-kanban'),
    path('', LeadListView.as_view(), name='crm-leads-list'),
    path('<uuid:pk>/', LeadDetailView.as_view(), name='crm-lead-detail'),
]
