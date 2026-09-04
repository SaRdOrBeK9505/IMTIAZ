"""Booking app views."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.openapi_schemas import ErrorResponseSerializer

from .models import Booking, RestaurantBooking
from .serializers import BookingSerializer, RestaurantBookingSerializer

_TAG = 'Telegram Mini App — Bookings'


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


class CreateRestaurantBookingFromAIView(APIView):
    """POST /api/booking/restaurant/create-from-ai/ — AI orqali restoran bron yaratish."""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=[_TAG],
        summary='AI orqali restoran bron yaratish',
        description='AI tomonidan yig\'ilgan strukturalangan ma\'lumotlar asosida bron yaratish.',
        request=RestaurantBookingSerializer,
        responses={
            201: BookingSerializer,
            400: ErrorResponseSerializer,
        },
    )
    def post(self, request):
        serializer = RestaurantBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create base Booking
        booking_data = {
            'user': request.user,
            'service_type': 'restaurant',
            'status': 'pending',
            'title': f"Restoran bron - {serializer.validated_data.get('branch')}",
            'description': serializer.validated_data.get('special_requests', ''),
            'created_by_ai': True,
        }
        
        booking = Booking.objects.create(**booking_data)
        
        # Create RestaurantBooking
        restaurant_booking = RestaurantBooking.objects.create(
            booking=booking,
            **serializer.validated_data
        )
        
        # Send Telegram notification to restaurant staff
        from apps.notifications.tasks import send_telegram_notification
        send_telegram_notification.delay(
            chat_id=serializer.validated_data.get('branch').phone if serializer.validated_data.get('branch') else None,
            message=f"🍽️ Yangi restoran bron so'rovi!\n"
                   f"Mijoz: {request.user.get_full_name()}\n"
                   f"Vaqt: {serializer.validated_data.get('preferred_time')}\n"
                   f"Kishilar: {serializer.validated_data.get('guest_count')}\n"
                   f"Tur: {serializer.validated_data.get('restaurant_type')}"
        )
        
        return Response(
            BookingSerializer(booking).data,
            status=status.HTTP_201_CREATED
        )
