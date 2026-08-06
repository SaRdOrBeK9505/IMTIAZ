"""Booking app views."""

from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Booking
from .serializers import BookingSerializer


class BookingListView(generics.ListAPIView):
    """GET /api/bookings/"""
    permission_classes = [IsAuthenticated]
    serializer_class = BookingSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'service_type']
    ordering_fields = ['created_at', 'booking_date', 'final_price']
    ordering = ['-created_at']
    queryset = Booking.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()
        return Booking.objects.filter(user=self.request.user).select_related(
            'flight_detail', 'train_detail',
            'restaurant_detail__branch',
            'event_detail__event',
        )


class BookingDetailView(generics.RetrieveAPIView):
    """GET /api/bookings/{id}/"""
    permission_classes = [IsAuthenticated]
    serializer_class = BookingSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()
        return Booking.objects.filter(user=self.request.user)
