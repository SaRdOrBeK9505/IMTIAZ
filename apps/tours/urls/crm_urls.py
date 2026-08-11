"""Tours — CRM URL routes."""

from django.urls import path
from apps.tours.views.crm_views import (
    TourPackageCRMListCreateView,
    TourPackageCRMDetailView,
    TourAvailabilityCRMView,
    TourAvailabilityCRMDetailView,
    TourBookingCRMListView,
    TourBookingCRMDetailView,
    TourBookingConfirmView,
    TourBookingRejectView,
    TourBookingProcessView,
    TourVoucherGenerateView,
    TourVoucherCRMDetailView,
    TourDashboardView,
    TourAnalyticsView,
    TourApplicationsView,
    TourConfirmedListView,
    TourClientsView,
)

urlpatterns = [
    # Dashboard & Analytics
    path('dashboard/',                                              TourDashboardView.as_view(),                 name='crm-tour-dashboard'),
    path('analytics/',                                              TourAnalyticsView.as_view(),                 name='crm-tour-analytics'),

    # UI sahifalari (screenshot mos)
    path('applications/',                                           TourApplicationsView.as_view(),              name='crm-tour-applications'),
    path('confirmed/',                                              TourConfirmedListView.as_view(),             name='crm-tour-confirmed'),
    path('clients/',                                                TourClientsView.as_view(),                   name='crm-tour-clients'),

    # Paketlar CRUD
    path('packages/',                                               TourPackageCRMListCreateView.as_view(),      name='crm-tour-packages'),
    path('packages/<uuid:pk>/',                                     TourPackageCRMDetailView.as_view(),          name='crm-tour-package-detail'),

    # Mavjudlik boshqaruvi
    path('packages/<uuid:package_id>/availability/',                TourAvailabilityCRMView.as_view(),           name='crm-tour-availability'),
    path('packages/<uuid:package_id>/availability/<uuid:pk>/',      TourAvailabilityCRMDetailView.as_view(),     name='crm-tour-availability-detail'),

    # Bronlar
    path('bookings/',                                               TourBookingCRMListView.as_view(),            name='crm-tour-bookings'),
    path('bookings/<uuid:pk>/',                                     TourBookingCRMDetailView.as_view(),          name='crm-tour-booking-detail'),
    path('bookings/<uuid:pk>/confirm/',                             TourBookingConfirmView.as_view(),            name='crm-tour-booking-confirm'),
    path('bookings/<uuid:pk>/reject/',                              TourBookingRejectView.as_view(),             name='crm-tour-booking-reject'),
    path('bookings/<uuid:pk>/process/',                             TourBookingProcessView.as_view(),            name='crm-tour-booking-process'),
    path('bookings/<uuid:pk>/voucher/generate/',                    TourVoucherGenerateView.as_view(),           name='crm-tour-voucher-generate'),
    path('bookings/<uuid:pk>/voucher/',                             TourVoucherCRMDetailView.as_view(),          name='crm-tour-voucher-detail'),
]
