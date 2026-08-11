"""CRM app — barcha URL routes."""

from django.urls import path
from .views import (
    # Mavjud views
    CRMDashboardView,
    CRMAuthView,
    BranchDashboardView,
    BranchBookingListView,
    BookingStatusUpdateView,
    BranchAnalyticsView,
    # Restoran stollari
    RestaurantTableListCreateView,
    RestaurantTableDetailView,
    RestaurantTableStatusView,
    RestaurantTableAvailabilityView,
    RestaurantTablesGroupedView,
    RestaurantBookingsCRMListView,
    RestaurantBookingConfirmView,
    RestaurantBookingCancelView,
    # Xodimlar statistikasi
    StaffListView,
    MyStaffStatsView,
    StaffStatsView,
    StaffLeaderboardView,
    StaffActivityView,
)

urlpatterns = [
    # ─── Bosh sahifa ──────────────────────────────────────────────────────────
    path('dashboard/',                                                     CRMDashboardView.as_view(),          name='crm-home-dashboard'),

    # ─── Mavjud ───────────────────────────────────────────────────────────────
    path('auth/',                                                          CRMAuthView.as_view(),               name='crm-auth'),
    path('branches/<uuid:branch_id>/dashboard/',                           BranchDashboardView.as_view(),       name='crm-dashboard'),
    path('branches/<uuid:branch_id>/bookings/',                            BranchBookingListView.as_view(),     name='crm-bookings'),
    path('branches/<uuid:branch_id>/bookings/<uuid:booking_id>/status/',   BookingStatusUpdateView.as_view(),   name='crm-booking-status'),
    path('branches/<uuid:branch_id>/analytics/',                           BranchAnalyticsView.as_view(),       name='crm-analytics'),

    # ─── Restoran stollari ────────────────────────────────────────────────────
    path('restaurant/tables/',                                             RestaurantTableListCreateView.as_view(),  name='crm-tables'),
    path('restaurant/tables/grouped/',                                     RestaurantTablesGroupedView.as_view(),    name='crm-tables-grouped'),
    path('restaurant/tables/availability/',                                RestaurantTableAvailabilityView.as_view(),name='crm-tables-availability'),
    path('restaurant/tables/<uuid:pk>/',                                   RestaurantTableDetailView.as_view(),      name='crm-table-detail'),
    path('restaurant/tables/<uuid:pk>/status/',                            RestaurantTableStatusView.as_view(),      name='crm-table-status'),
    path('restaurant/bookings/',                                           RestaurantBookingsCRMListView.as_view(),  name='crm-restaurant-bookings'),
    path('restaurant/bookings/<uuid:pk>/confirm/',                         RestaurantBookingConfirmView.as_view(),   name='crm-restaurant-booking-confirm'),
    path('restaurant/bookings/<uuid:pk>/cancel/',                          RestaurantBookingCancelView.as_view(),    name='crm-restaurant-booking-cancel'),

    # ─── Xodimlar statistikasi ────────────────────────────────────────────────
    path('staff/',                                                         StaffListView.as_view(),             name='crm-staff-list'),
    path('staff/me/stats/',                                                MyStaffStatsView.as_view(),          name='crm-staff-me-stats'),
    path('staff/leaderboard/',                                             StaffLeaderboardView.as_view(),      name='crm-staff-leaderboard'),
    path('staff/activity/',                                                StaffActivityView.as_view(),         name='crm-staff-activity'),
    path('staff/<uuid:pk>/stats/',                                         StaffStatsView.as_view(),            name='crm-staff-stats'),
]
