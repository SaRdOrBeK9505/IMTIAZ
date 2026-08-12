"""Tours — User-facing URL routes."""

from django.urls import path
from apps.tours.views.destination_views import (
    TourDestinationDetailView,
    TourDestinationFiltersView,
    TourDestinationListView,
    TourDestinationPackagesView,
)
from apps.tours.views.user_views import (
    TourCategoryListView,
    TourPackageListView,
    TourPackageDetailView,
    TourAvailabilityListView,
    TourReviewListCreateView,
    TourBookView,
    MyTourBookingsView,
    MyTourBookingDetailView,
    TourBookingVoucherView,
)

urlpatterns = [
    path('categories/',                      TourCategoryListView.as_view(),    name='tour-categories'),

    # Yo'nalishlar — filter pathlari uuid dan oldin
    path('destinations/filters/',            TourDestinationFiltersView.as_view(), name='tour-destination-filters'),
    path('destinations/<uuid:pk>/packages/', TourDestinationPackagesView.as_view(), name='tour-destination-packages'),
    path('destinations/<uuid:pk>/',          TourDestinationDetailView.as_view(), name='tour-destination-detail'),
    path('destinations/',                    TourDestinationListView.as_view(), name='tour-destinations'),

    # Paketlar
    path('',                                 TourPackageListView.as_view(),     name='tour-list'),
    path('<uuid:pk>/',                       TourPackageDetailView.as_view(),   name='tour-detail'),
    path('<uuid:package_id>/availability/',  TourAvailabilityListView.as_view(), name='tour-availability'),
    path('<uuid:package_id>/reviews/',       TourReviewListCreateView.as_view(), name='tour-reviews'),

    # Bron qilish
    path('<uuid:package_id>/book/',          TourBookView.as_view(),            name='tour-book'),

    # Mijoz bronlari
    path('my-bookings/',                     MyTourBookingsView.as_view(),      name='my-tour-bookings'),
    path('my-bookings/<uuid:pk>/',           MyTourBookingDetailView.as_view(), name='my-tour-booking-detail'),
    path('my-bookings/<uuid:pk>/voucher/',   TourBookingVoucherView.as_view(),  name='my-tour-voucher'),
]
