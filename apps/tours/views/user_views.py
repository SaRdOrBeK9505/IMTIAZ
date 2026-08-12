"""
Tours — User-facing views.

Endpointlar:
    GET  /api/tours/categories/
    GET  /api/tours/destinations/              — filter, qidiruv, pagination
    GET  /api/tours/destinations/filters/      — filter metadata
    GET  /api/tours/destinations/<id>/         — yo'nalish tafsiloti
    GET  /api/tours/destinations/<id>/packages/ — yo'nalishdagi turlar
    GET  /api/tours/                    — qidiruv, filter, pagination
    GET  /api/tours/<id>/               — to'liq detail
    GET  /api/tours/<id>/availability/  — bo'sh sanalar
    GET  /api/tours/<id>/reviews/
    POST /api/tours/<id>/reviews/       — faqat haqiqiy bronchilar
    POST /api/tours/<id>/book/          — bron yaratish
    GET  /api/tours/my-bookings/        — mijozning tur bronlari
    GET  /api/tours/my-bookings/<id>/   — bron detail
    GET  /api/tours/my-bookings/<id>/voucher/ — voaucher
"""

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework import generics, status, filters
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from apps.booking.models import TourBooking, BookingStatus
from ..models import TourCategory, TourPackage, TourAvailability, TourReview
from ..serializers import (
    TourCategorySerializer, TourDestinationSerializer,
    TourPackageListSerializer, TourPackageDetailSerializer,
    TourAvailabilitySerializer,
    TourReviewSerializer, TourReviewCreateSerializer,
    TourBookingCreateSerializer, TourBookingDetailSerializer,
    TourVoucherSerializer,
)
from ..services import TourSearchService, TourBookingService, TourVoucherService


# ─── Kategoriyalar ────────────────────────────────────────────────────────────

class TourCategoryListView(generics.ListAPIView):
    """GET /api/tours/categories/"""
    permission_classes = [AllowAny]
    serializer_class   = TourCategorySerializer
    queryset           = TourCategory.objects.filter(is_active=True)

    @extend_schema(summary='Tur kategoriyalari', tags=['Tours — User'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)



# ─── Tur Paketlari ────────────────────────────────────────────────────────────

class TourPackageListView(generics.ListAPIView):
    """
    GET /api/tours/
    Qidiruv parametrlari: destination_id, category_id, departure_from,
    departure_to, min_price, max_price, min_days, max_days,
    difficulty, guests, q (full-text), is_featured
    """
    permission_classes = [AllowAny]
    serializer_class   = TourPackageListSerializer
    queryset           = TourPackage.objects.none()

    @extend_schema(
        summary   = 'Tur paketlari ro\'yxati (qidiruv)',
        tags      = ['Tours — User'],
        responses = {200: TourPackageListSerializer(many=True)},
        parameters = [
            OpenApiParameter('destination_id', str, description='Yo\'nalish ID'),
            OpenApiParameter('category_id',    str, description='Kategoriya ID'),
            OpenApiParameter('departure_from', str, description='Jo\'nash sanasidan (YYYY-MM-DD)'),
            OpenApiParameter('departure_to',   str, description='Jo\'nash sanasigacha (YYYY-MM-DD)'),
            OpenApiParameter('min_price',      float, description='Minimal narx'),
            OpenApiParameter('max_price',      float, description='Maksimal narx'),
            OpenApiParameter('min_days',       int, description='Minimal kunlar'),
            OpenApiParameter('max_days',       int, description='Maksimal kunlar'),
            OpenApiParameter('difficulty',     str, description='Qiyinlik: easy/moderate/hard/extreme'),
            OpenApiParameter('guests',         int, description='Necha kishi'),
            OpenApiParameter('q',              str, description='Qidiruv so\'zi'),
            OpenApiParameter('is_featured',    bool, description='Faqat tanlangan turlar'),
        ]
    )
    def get(self, request, *args, **kwargs):
        params = request.query_params
        qs = TourSearchService.search(
            destination_id  = params.get('destination_id'),
            category_id     = params.get('category_id'),
            departure_from  = params.get('departure_from'),
            departure_to    = params.get('departure_to'),
            min_price       = params.get('min_price'),
            max_price       = params.get('max_price'),
            min_days        = params.get('min_days'),
            max_days        = params.get('max_days'),
            difficulty      = params.get('difficulty'),
            guests          = params.get('guests'),
            query           = params.get('q'),
            is_featured     = params.get('is_featured', '').lower() == 'true',
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(
                TourPackageListSerializer(page, many=True, context={'request': request}).data
            )
        return Response(
            TourPackageListSerializer(qs, many=True, context={'request': request}).data
        )


class TourPackageDetailView(generics.RetrieveAPIView):
    """GET /api/tours/<id>/"""
    permission_classes = [AllowAny]
    serializer_class   = TourPackageDetailSerializer
    queryset           = TourPackage.objects.filter(is_active=True).select_related(
        'destination', 'category', 'organization'
    ).prefetch_related('itinerary_days', 'availabilities')

    @extend_schema(summary='Tur paketi tafsiloti', tags=['Tours — User'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class TourAvailabilityListView(generics.ListAPIView):
    """GET /api/tours/<package_id>/availability/"""
    permission_classes = [AllowAny]
    serializer_class   = TourAvailabilitySerializer
    queryset           = TourAvailability.objects.none()

    @extend_schema(
        summary    = 'Tur mavjud sanalari',
        tags       = ['Tours — User'],
        responses  = {200: TourAvailabilitySerializer(many=True)},
        parameters = [OpenApiParameter('month', str, description='YYYY-MM formatida oy')]
    )
    def get(self, request, package_id=None, *args, **kwargs):
        qs = TourSearchService.get_available_dates(
            str(package_id), month=request.query_params.get('month')
        )
        return Response(TourAvailabilitySerializer(qs, many=True).data)


# ─── Sharhlar ─────────────────────────────────────────────────────────────────

class TourReviewListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/tours/<package_id>/reviews/ — barcha publish qilingan sharhlar
    POST /api/tours/<package_id>/reviews/ — sharh qoldirish (faqat bronchilar)
    """
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'rating']
    ordering        = ['-created_at']

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TourReviewCreateSerializer
        return TourReviewSerializer

    def get_queryset(self):
        return TourReview.objects.filter(
            package_id=self.kwargs['package_id'],
            is_published=True,
        ).select_related('user')

    @extend_schema(summary='Tur sharhlari', tags=['Tours — User'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary='Sharh qoldirish', tags=['Tours — User'])
    def post(self, request, package_id=None, *args, **kwargs):
        # Faqat haqiqiy bronchilar sharh yozishi mumkin
        has_booking = TourBooking.objects.filter(
            booking__user     = request.user,
            package_id        = package_id,
            booking__status__in = [BookingStatus.CONFIRMED, BookingStatus.COMPLETED],
        ).exists()

        serializer = TourReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = TourReview.objects.create(
            package_id   = package_id,
            user         = request.user,
            is_verified  = has_booking,
            is_published = has_booking,  # Haqiqiy bronchilar avtomatik publish
            **serializer.validated_data,
        )
        # Paket statistikasini yangilash
        from ..services import TourAvailabilityService
        TourAvailabilityService.update_package_stats(str(package_id))

        return Response(TourReviewSerializer(review).data, status=status.HTTP_201_CREATED)


# ─── Bron Yaratish ────────────────────────────────────────────────────────────

class TourBookView(APIView):
    """POST /api/tours/<package_id>/book/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request   = TourBookingCreateSerializer,
        responses = {201: TourBookingDetailSerializer},
        summary   = 'Tur bron qilish',
        tags      = ['Tours — User'],
    )
    def post(self, request, package_id=None):
        serializer = TourBookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # package_id URL dan keladi — tekshiramiz
        if str(data['package_id']) != str(package_id):
            return Response(
                {'message': 'package_id mos kelmadi.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            booking, tour_booking = TourBookingService.create_booking(
                user             = request.user,
                package_id       = str(data['package_id']),
                availability_id  = str(data['availability_id']),
                tourist_count    = data['tourist_count'],
                tourists_info    = data['tourists_info'],
                special_requests = data.get('special_requests', ''),
                hotel_preference = data.get('hotel_preference', 'any'),
            )
        except ValueError as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            TourBookingDetailSerializer(tour_booking).data,
            status=status.HTTP_201_CREATED,
        )


# ─── Mijoz Bronlari ───────────────────────────────────────────────────────────

class MyTourBookingsView(generics.ListAPIView):
    """GET /api/tours/my-bookings/"""
    permission_classes = [IsAuthenticated]
    serializer_class   = TourBookingDetailSerializer
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['booking__status']
    ordering           = ['-booking__created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TourBooking.objects.none()
        return TourBooking.objects.filter(
            booking__user=self.request.user
        ).select_related(
            'booking', 'package__destination', 'availability'
        ).prefetch_related('voucher')

    @extend_schema(summary='Mening tur bronlarim', tags=['Tours — User'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class MyTourBookingDetailView(generics.RetrieveAPIView):
    """GET /api/tours/my-bookings/<id>/"""
    permission_classes = [IsAuthenticated]
    serializer_class   = TourBookingDetailSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TourBooking.objects.none()
        return TourBooking.objects.filter(
            booking__user=self.request.user
        ).select_related('booking', 'package__destination', 'availability')

    @extend_schema(summary='Tur bron tafsiloti', tags=['Tours — User'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class TourBookingVoucherView(APIView):
    """GET /api/tours/my-bookings/<id>/voucher/ — voaucher yuklab olish."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses = {200: TourVoucherSerializer},
        summary   = 'Tur voaucheri',
        tags      = ['Tours — User'],
    )
    def get(self, request, pk=None):
        try:
            tour_booking = TourBooking.objects.get(
                id=pk, booking__user=request.user
            )
        except TourBooking.DoesNotExist:
            return Response({'message': 'Bron topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        if not tour_booking.voucher_generated:
            return Response(
                {'message': 'Voaucher hali yaratilmagan. Operator tasdiqlashini kuting.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            voucher = tour_booking.voucher
        except Exception:
            return Response({'message': 'Voaucher topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        TourVoucherService.increment_download(str(voucher.id))
        return Response(TourVoucherSerializer(voucher).data)
