"""Restaurant vertikal URL'lar — birlashgan CRM API."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.crm_core.views import (
    RestaurantOwnerDashboardView,
    RestaurantStaffDetailView,
    RestaurantStaffListCreateView,
)

from .analytics_views import RestaurantAnalyticsExportView, RestaurantAnalyticsView
from .booking_views import (
    RestaurantBookingCancelView,
    RestaurantBookingConfirmView,
    RestaurantBookingListCreateView,
)
from .staff_views import (
    RestaurantMyStatsView,
    RestaurantStaffActivityView,
    RestaurantStaffLeaderboardView,
    RestaurantStaffListView,
    RestaurantStaffStatsView,
)
from .table_views import (
    RestaurantTableAvailabilityView,
    RestaurantTableSlotGenerateView,
    RestaurantTableSlotListView,
    RestaurantTableSlotUpdateView,
    RestaurantTablesGroupedView,
    RestaurantTableStatusView,
)
from .views import (
    FeaturedItemViewSet,
    MenuCategoryViewSet,
    MenuItemViewSet,
    RestaurantBranchCreateView,
    RestaurantOrganizationView,
    RestaurantTableViewSet,
)

router = DefaultRouter()
router.register('tables', RestaurantTableViewSet, basename='restaurant-tables')
router.register('menu-categories', MenuCategoryViewSet, basename='restaurant-menu-categories')
router.register('menu-items', MenuItemViewSet, basename='restaurant-menu-items')
router.register('featured-items', FeaturedItemViewSet, basename='restaurant-featured-items')

urlpatterns = [
    path('dashboard/', RestaurantOwnerDashboardView.as_view(), name='restaurant-dashboard'),
    path('organization/', RestaurantOrganizationView.as_view(), name='restaurant-organization'),
    path('branches/', RestaurantBranchCreateView.as_view(), name='restaurant-branch-create'),
    path('analytics/export/', RestaurantAnalyticsExportView.as_view(), name='restaurant-analytics-export'),
    path('analytics/', RestaurantAnalyticsView.as_view(), name='restaurant-analytics'),

    # Xodim statistikasi (aniq pathlar uuid dan oldin)
    path('staff/members/', RestaurantStaffListView.as_view(), name='restaurant-staff-members'),
    path('staff/me/stats/', RestaurantMyStatsView.as_view(), name='restaurant-staff-me-stats'),
    path('staff/leaderboard/', RestaurantStaffLeaderboardView.as_view(), name='restaurant-staff-leaderboard'),
    path('staff/activity/', RestaurantStaffActivityView.as_view(), name='restaurant-staff-activity'),
    path('staff/<uuid:pk>/stats/', RestaurantStaffStatsView.as_view(), name='restaurant-staff-stats'),

    # Owner staff CRUD
    path('staff/', RestaurantStaffListCreateView.as_view(), name='restaurant-staff-list'),
    path('staff/<uuid:pk>/', RestaurantStaffDetailView.as_view(), name='restaurant-staff-detail'),

    # Bronlar
    path('bookings/', RestaurantBookingListCreateView.as_view(), name='restaurant-bookings'),
    path('bookings/<uuid:pk>/confirm/', RestaurantBookingConfirmView.as_view(), name='restaurant-booking-confirm'),
    path('bookings/<uuid:pk>/cancel/', RestaurantBookingCancelView.as_view(), name='restaurant-booking-cancel'),

    # Lead pipeline
    path('leads/', include('apps.crm_core.lead_urls')),

    # Stollar (router dan oldin — grouped/availability/status/slots)
    path('tables/slots/generate/', RestaurantTableSlotGenerateView.as_view(), name='restaurant-table-slots-generate'),
    path('tables/grouped/', RestaurantTablesGroupedView.as_view(), name='restaurant-tables-grouped'),
    path('tables/availability/', RestaurantTableAvailabilityView.as_view(), name='restaurant-tables-availability'),
    path('tables/<uuid:pk>/slots/<uuid:slot_id>/', RestaurantTableSlotUpdateView.as_view(), name='restaurant-table-slot-update'),
    path('tables/<uuid:pk>/slots/', RestaurantTableSlotListView.as_view(), name='restaurant-table-slots'),
    path('tables/<uuid:pk>/status/', RestaurantTableStatusView.as_view(), name='restaurant-table-status'),

    # QR kodlar (owner + staff)
    path('qr/', include('apps.qr_codes.urls.crm_urls')),

    path('', include(router.urls)),
]
