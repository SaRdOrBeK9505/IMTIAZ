"""CRM app — legacy URL routes (restoran endpointlar crm_restaurant ga ko'chirildi)."""

from django.urls import path
from .views import (
    CRMDashboardView,
    BranchDashboardView,
    BranchBookingListView,
    BookingStatusUpdateView,
    BranchAnalyticsView,
)

# Legacy staff URL — crm_restaurant ga yo'naltirish (backward compatibility)
from apps.crm_restaurant.staff_views import (
    RestaurantMyStatsView,
    RestaurantStaffActivityView,
    RestaurantStaffLeaderboardView,
    RestaurantStaffListView,
    RestaurantStaffStatsView,
)

urlpatterns = [
    path('dashboard/', CRMDashboardView.as_view(), name='crm-home-dashboard'),

    path('branches/<uuid:branch_id>/dashboard/', BranchDashboardView.as_view(), name='crm-dashboard'),
    path('branches/<uuid:branch_id>/bookings/', BranchBookingListView.as_view(), name='crm-bookings'),
    path(
        'branches/<uuid:branch_id>/bookings/<uuid:booking_id>/status/',
        BookingStatusUpdateView.as_view(),
        name='crm-booking-status',
    ),
    path('branches/<uuid:branch_id>/analytics/', BranchAnalyticsView.as_view(), name='crm-analytics'),

    # Legacy aliases → /api/crm/restaurant/ ga ko'chirilgan
    path('staff/', RestaurantStaffListView.as_view(), name='crm-staff-list'),
    path('staff/me/stats/', RestaurantMyStatsView.as_view(), name='crm-staff-me-stats'),
    path('staff/leaderboard/', RestaurantStaffLeaderboardView.as_view(), name='crm-staff-leaderboard'),
    path('staff/activity/', RestaurantStaffActivityView.as_view(), name='crm-staff-activity'),
    path('staff/<uuid:pk>/stats/', RestaurantStaffStatsView.as_view(), name='crm-staff-stats'),
]
