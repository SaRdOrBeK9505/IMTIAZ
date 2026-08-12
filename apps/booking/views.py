"""Booking app views."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.openapi_schemas import ErrorResponseSerializer

from .models import Booking
from .serializers import BookingSerializer

_TAG = 'Bookings'


class BookingListView(generics.ListAPIView):
    """GET /api/bookings/ — foydalanuvchining barcha bronlari."""
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

    @extend_schema(
        tags=[_TAG],
        summary='Mening bronlarim',
        description=(
            'Polymorphic bronlar: flight, train, restaurant, event, tour. '
            'Faqat joriy foydalanuvchining yozuvlari.'
        ),
        parameters=[
            OpenApiParameter('status', str, description='pending|confirmed|cancelled|...'),
            OpenApiParameter('service_type', str, description='flight|restaurant|tour|...'),
            OpenApiParameter('ordering', str, description='created_at, -final_price, ...'),
            OpenApiParameter('page', int, description='Sahifa raqami (paginatsiya)'),
        ],
        responses={200: BookingSerializer(many=True), 401: ErrorResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BookingDetailView(generics.RetrieveAPIView):
    """GET /api/bookings/{id}/"""
    permission_classes = [IsAuthenticated]
    serializer_class = BookingSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()
        return Booking.objects.filter(user=self.request.user)

    @extend_schema(
        tags=[_TAG],
        summary='Bron tafsilotlari',
        description='Xizmat turiga qarab nested detail (restaurant_detail, tour_detail, ...).',
        responses={200: BookingSerializer, 404: ErrorResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
