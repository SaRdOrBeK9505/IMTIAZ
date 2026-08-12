"""Restoran bronlari — to'liq lifecycle (list, create, confirm, cancel)."""

from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.booking.models import Booking, BookingStatus, RestaurantBooking, ServiceType
from apps.core.authentication import CRMJWTAuthentication
from apps.core.openapi_schemas import ErrorResponseSerializer
from apps.core.permissions import IsRestaurantCRMUser
from apps.crm.models import RestaurantTable, StaffActivityLog
from apps.crm.serializers import (
    RestaurantBookingCRMSerializer,
    RestaurantBookingCreateSerializer,
)
from apps.crm_core.mixins import LeadTrackingMixin

from .helpers import log_staff_activity, require_restaurant_permission, resolve_branch

_BOOKINGS_TAG = 'CRM Restaurant — Bookings'


class RestaurantBookingListCreateView(LeadTrackingMixin, generics.ListCreateAPIView):
    """
    GET/POST /api/crm/restaurant/bookings/
    Owner — barcha filiallar. Staff — o'z filiali (view_bookings / manage_bookings).
    """
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]
    serializer_class = RestaurantBookingCRMSerializer

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return RestaurantBookingCreateSerializer
        return RestaurantBookingCRMSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()

        qs = Booking.objects.filter(
            restaurant_detail__isnull=False,
        ).select_related('user', 'restaurant_detail', 'restaurant_detail__branch')
        qs = self.filter_bookings_for_user(qs).order_by('-created_at')

        if s := self.request.query_params.get('status'):
            qs = qs.filter(status=s)
        if d := self.request.query_params.get('date'):
            qs = qs.filter(restaurant_detail__reservation_at__date=d)
        if branch_id := self.request.query_params.get('branch_id'):
            qs = qs.filter(restaurant_detail__branch_id=branch_id)
        return qs

    @extend_schema(
        tags=[_BOOKINGS_TAG],
        summary='Restoran bronlari ro\'yxati',
        parameters=[
            OpenApiParameter('status', str, required=False),
            OpenApiParameter('date', str, description='YYYY-MM-DD', required=False),
            OpenApiParameter('branch_id', str, required=False),
        ],
        responses={200: RestaurantBookingCRMSerializer(many=True), 403: ErrorResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        require_restaurant_permission(request.user, 'view_bookings')
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=[_BOOKINGS_TAG],
        summary='Yangi restoran bron (CRM)',
        request=RestaurantBookingCreateSerializer,
        responses={201: RestaurantBookingCRMSerializer, 403: ErrorResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        require_restaurant_permission(request.user, 'manage_bookings')

        branch = resolve_branch(request.user)
        if not branch:
            return Response({'message': 'Filial topilmadi.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RestaurantBookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from django.contrib.auth import get_user_model
        from apps.users.models import UserRole

        User = get_user_model()
        phone = data['customer_phone'].strip()
        user, _ = User.objects.get_or_create(
            phone=phone,
            defaults={
                'first_name': data['customer_name'].split()[0] if data['customer_name'] else '',
                'last_name': ' '.join(data['customer_name'].split()[1:]) if data['customer_name'] else '',
                'role': UserRole.CUSTOMER,
            },
        )

        table = None
        table_number = data.get('table_number', '')
        if table_id := data.get('table_id'):
            try:
                table = RestaurantTable.objects.get(id=table_id, branch=branch)
                table_number = table.table_number
            except RestaurantTable.DoesNotExist:
                return Response({'message': 'Stol topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        booking = Booking.objects.create(
            user=user,
            service_type=ServiceType.RESTAURANT,
            status=BookingStatus.PENDING,
            title=f'Stol #{table_number}' if table_number else 'Restoran broni',
            booking_date=data['reservation_at'],
        )
        rb = RestaurantBooking.objects.create(
            booking=booking,
            branch=branch,
            reservation_at=data['reservation_at'],
            guest_count=data['guest_count'],
            duration_minutes=data['duration_minutes'],
            special_requests=data.get('special_requests', ''),
            table_number=table_number or None,
        )

        if table:
            from .services.table_slots import reserve_slots_for_booking

            try:
                reserve_slots_for_booking(rb, table=table)
            except ValueError as exc:
                booking.delete()
                return Response({'message': str(exc)}, status=status.HTTP_409_CONFLICT)

        from apps.crm_core.services.leads import create_lead_from_restaurant_booking
        create_lead_from_restaurant_booking(booking, rb)

        log_staff_activity(
            request.user,
            action_type=StaffActivityLog.ActionType.CONFIRM_TABLE_BOOKING,
            entity_type='RestaurantBooking',
            entity_id=booking.id,
            description=f'Yangi bron yaratildi: {data["customer_name"]}',
            request=request,
        )

        booking = Booking.objects.select_related('user', 'restaurant_detail').get(id=booking.id)
        return Response(RestaurantBookingCRMSerializer(booking).data, status=status.HTTP_201_CREATED)


class _RestaurantBookingActionMixin:
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    def _get_booking(self, request, pk):
        qs = Booking.objects.select_related('user', 'restaurant_detail').filter(
            id=pk,
            restaurant_detail__isnull=False,
        )
        user = request.user
        organization = user.organization
        if not organization:
            return None

        from apps.users.models import UserRole

        if user.role == UserRole.RESTAURANT_STAFF:
            branch = user.branch_staff_profile.branch
            qs = qs.filter(restaurant_detail__branch=branch)
        else:
            branch_ids = organization.branches.filter(is_active=True).values_list('id', flat=True)
            qs = qs.filter(restaurant_detail__branch_id__in=branch_ids)
        return qs.first()


@extend_schema_view(
    post=extend_schema(
        tags=[_BOOKINGS_TAG],
        summary='Restoran bronini tasdiqlash',
        request=None,
        responses={200: RestaurantBookingCRMSerializer, 404: ErrorResponseSerializer},
    ),
)
class RestaurantBookingConfirmView(_RestaurantBookingActionMixin, APIView):
    def post(self, request, pk):
        require_restaurant_permission(request.user, 'manage_bookings')
        booking = self._get_booking(request, pk)
        if not booking:
            return Response({'message': 'Bron topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        if booking.status == BookingStatus.CONFIRMED:
            return Response({'message': 'Bron allaqachon tasdiqlangan.'}, status=status.HTTP_400_BAD_REQUEST)

        booking.status = BookingStatus.CONFIRMED
        booking.save(update_fields=['status', 'updated_at'])

        if hasattr(booking, 'restaurant_detail') and booking.restaurant_detail:
            booking.restaurant_detail.confirmed_by_staff = True
            booking.restaurant_detail.save(update_fields=['confirmed_by_staff', 'updated_at'])

        from apps.crm_core.models import Lead
        from apps.crm_core.services.leads import sync_lead_stage_for_booking
        sync_lead_stage_for_booking(booking, Lead.Stage.WON)

        log_staff_activity(
            request.user,
            action_type=StaffActivityLog.ActionType.CONFIRM_TABLE_BOOKING,
            entity_type='RestaurantBooking',
            entity_id=booking.id,
            description=f'Bron tasdiqlandi: {booking.user.full_name}',
            request=request,
        )

        from apps.notifications.crm import notify_customer_booking_confirmed, schedule_lead_notification

        rd = booking.restaurant_detail
        schedule_lead_notification(
            lambda b=booking: notify_customer_booking_confirmed(
                b,
                message=(
                    f'{rd.branch.name if rd and rd.branch else "Restoran"} — '
                    f'{rd.reservation_at.strftime("%d.%m.%Y %H:%M") if rd else ""} '
                    f'bron tasdiqlandi.'
                ),
            )
        )

        return Response(RestaurantBookingCRMSerializer(booking).data)


@extend_schema_view(
    post=extend_schema(
        tags=[_BOOKINGS_TAG],
        summary='Restoran bronini bekor qilish',
        responses={200: RestaurantBookingCRMSerializer, 404: ErrorResponseSerializer},
    ),
)
class RestaurantBookingCancelView(_RestaurantBookingActionMixin, APIView):
    serializer_class = RestaurantBookingCRMSerializer

    def post(self, request, pk):
        require_restaurant_permission(request.user, 'manage_bookings')
        booking = self._get_booking(request, pk)
        if not booking:
            return Response({'message': 'Bron topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        if booking.status == BookingStatus.CANCELLED:
            return Response({'message': 'Bron allaqachon bekor qilingan.'}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get('reason', '')
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.cancellation_reason = reason
        booking.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'updated_at'])

        if hasattr(booking, 'restaurant_detail') and booking.restaurant_detail:
            from .services.table_slots import release_slots_for_booking
            release_slots_for_booking(booking.restaurant_detail)

        from apps.crm_core.models import Lead
        from apps.crm_core.services.leads import sync_lead_stage_for_booking
        sync_lead_stage_for_booking(booking, Lead.Stage.LOST)

        log_staff_activity(
            request.user,
            action_type=StaffActivityLog.ActionType.CANCEL_TABLE_BOOKING,
            entity_type='RestaurantBooking',
            entity_id=booking.id,
            description=f'Bron bekor qilindi: {booking.user.full_name}',
            request=request,
        )

        from apps.notifications.crm import notify_customer_booking_rejected, schedule_lead_notification

        schedule_lead_notification(
            lambda b=booking, r=reason: notify_customer_booking_rejected(b, reason=r)
        )

        return Response(RestaurantBookingCRMSerializer(booking).data)
