"""Tur operatsion CRM URL'lar — paketlar, bronlar, analitika."""

from django.urls import path

from apps.tours.views.crm_views import (
    TourAnalyticsView,
    TourApplicationsView,
    TourAvailabilityCRMDetailView,
    TourAvailabilityCRMView,
    TourBookingConfirmView,
    TourBookingCRMDetailView,
    TourBookingCRMListView,
    TourBookingProcessView,
    TourBookingRejectView,
    TourClientsView,
    TourConfirmedListView,
    TourDashboardView,
    TourPackageCRMDetailView,
    TourPackageCRMListCreateView,
    TourVoucherCRMDetailView,
    TourVoucherGenerateView,
)

from .destination_views import (
    TourDestinationCRMDetailView,
    TourDestinationCRMListCreateView,
    TourDestinationGridView,
    TourDestinationImageDetailView,
    TourDestinationImageListCreateView,
)

urlpatterns = [
    # Yo'nalishlar (aniq pathlar uuid dan oldin)
    path('destinations/grid/', TourDestinationGridView.as_view(), name='tour-crm-destinations-grid'),
    path('destinations/', TourDestinationCRMListCreateView.as_view(), name='tour-crm-destinations'),
    path('destinations/<uuid:pk>/', TourDestinationCRMDetailView.as_view(), name='tour-crm-destination-detail'),
    path(
        'destinations/<uuid:pk>/images/',
        TourDestinationImageListCreateView.as_view(),
        name='tour-crm-destination-images',
    ),
    path(
        'destinations/<uuid:pk>/images/<uuid:image_id>/',
        TourDestinationImageDetailView.as_view(),
        name='tour-crm-destination-image-detail',
    ),

    # Operatsion dashboard — /api/crm/tour/overview/ (owner + staff)
    path('overview/', TourDashboardView.as_view(), name='tour-crm-overview'),

    path('analytics/', TourAnalyticsView.as_view(), name='tour-crm-analytics'),
    path('applications/', TourApplicationsView.as_view(), name='tour-crm-applications'),
    path('confirmed/', TourConfirmedListView.as_view(), name='tour-crm-confirmed'),
    path('clients/', TourClientsView.as_view(), name='tour-crm-clients'),

    path('packages/', TourPackageCRMListCreateView.as_view(), name='tour-crm-packages'),
    path('packages/<uuid:pk>/', TourPackageCRMDetailView.as_view(), name='tour-crm-package-detail'),
    path(
        'packages/<uuid:package_id>/availability/',
        TourAvailabilityCRMView.as_view(),
        name='tour-crm-availability',
    ),
    path(
        'packages/<uuid:package_id>/availability/<uuid:pk>/',
        TourAvailabilityCRMDetailView.as_view(),
        name='tour-crm-availability-detail',
    ),

    path('bookings/', TourBookingCRMListView.as_view(), name='tour-crm-bookings'),
    path('bookings/<uuid:pk>/', TourBookingCRMDetailView.as_view(), name='tour-crm-booking-detail'),
    path('bookings/<uuid:pk>/confirm/', TourBookingConfirmView.as_view(), name='tour-crm-booking-confirm'),
    path('bookings/<uuid:pk>/reject/', TourBookingRejectView.as_view(), name='tour-crm-booking-reject'),
    path('bookings/<uuid:pk>/process/', TourBookingProcessView.as_view(), name='tour-crm-booking-process'),
    path(
        'bookings/<uuid:pk>/voucher/generate/',
        TourVoucherGenerateView.as_view(),
        name='tour-crm-voucher-generate',
    ),
    path('bookings/<uuid:pk>/voucher/', TourVoucherCRMDetailView.as_view(), name='tour-crm-voucher-detail'),
]
