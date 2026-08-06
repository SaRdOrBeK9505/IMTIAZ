from django.urls import path
from .views import (
    CRMAuthView,
    BranchDashboardView,
    BranchBookingListView,
    BookingStatusUpdateView,
    BranchAnalyticsView,
)

urlpatterns = [
    path('auth/', CRMAuthView.as_view(), name='crm-auth'),
    path('branches/<uuid:branch_id>/dashboard/', BranchDashboardView.as_view(), name='crm-dashboard'),
    path('branches/<uuid:branch_id>/bookings/', BranchBookingListView.as_view(), name='crm-bookings'),
    path('branches/<uuid:branch_id>/bookings/<uuid:booking_id>/status/', BookingStatusUpdateView.as_view(), name='crm-booking-status'),
    path('branches/<uuid:branch_id>/analytics/', BranchAnalyticsView.as_view(), name='crm-analytics'),
]
