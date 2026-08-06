"""
CRM app views — filial xodimlari uchun panel.
Queryset darajasida filtrlash + permission tekshiruvi.
TZ 3.6 bo'limiga mos.
"""

from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsBranchStaff
from apps.booking.models import Booking, BookingStatus
from .serializers import (
    DashboardSerializer,
    BookingCRMSerializer,
    BookingStatusUpdateSerializer,
    BranchSerializer,
)


class CRMAuthView(APIView):
    """POST /api/crm/auth/"""
    permission_classes = []

    @extend_schema(
        request=None,
        responses={501: OpenApiResponse(description='TBD')},
        summary='CRM xodim kirishi',
        tags=['CRM'],
    )
    def post(self, request):
        return Response({'message': 'CRM auth TBD'}, status=status.HTTP_501_NOT_IMPLEMENTED)


class BranchDashboardView(APIView):
    """GET /api/crm/branches/{branch_id}/dashboard/"""
    permission_classes = [IsAuthenticated, IsBranchStaff]

    @extend_schema(
        responses={200: OpenApiResponse(description='Dashboard ma\'lumotlari')},
        summary='Filial dashboard',
        tags=['CRM'],
    )
    def get(self, request, branch_id):
        staff = request.user.branch_staff_profile
        if str(staff.branch_id) != str(branch_id):
            return Response({'message': 'Kirish taqiqlangan.'}, status=status.HTTP_403_FORBIDDEN)
        if not (staff.has_permission('view_bookings') or staff.has_permission('view_analytics')):
            return Response({'message': 'Kirish taqiqlangan.'}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.now().date()
        qs = Booking.objects.filter(
            restaurant_detail__branch_id=branch_id,
            created_at__date=today,
        )
        return Response({
            'branch': BranchSerializer(staff.branch).data,
            'total_bookings_today': qs.count(),
            'pending_bookings': qs.filter(status=BookingStatus.PENDING).count(),
            'confirmed_bookings': qs.filter(status=BookingStatus.CONFIRMED).count(),
            'revenue_today': qs.filter(
                status=BookingStatus.CONFIRMED
            ).aggregate(total=Sum('final_price'))['total'] or 0,
        })


class BranchBookingListView(generics.ListAPIView):
    """GET /api/crm/branches/{branch_id}/bookings/"""
    permission_classes = [IsAuthenticated, IsBranchStaff]
    serializer_class = BookingCRMSerializer
    queryset = Booking.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()
        staff = self.request.user.branch_staff_profile
        branch_id = self.kwargs['branch_id']
        if str(staff.branch_id) != str(branch_id) or not staff.has_permission('view_bookings'):
            return Booking.objects.none()

        qs = Booking.objects.filter(
            restaurant_detail__branch_id=branch_id
        ).select_related('user').order_by('-created_at')

        if s := self.request.query_params.get('status'):
            qs = qs.filter(status=s)
        if d := self.request.query_params.get('date'):
            qs = qs.filter(booking_date__date=d)
        return qs


class BookingStatusUpdateView(APIView):
    """PATCH /api/crm/branches/{branch_id}/bookings/{booking_id}/status/"""
    permission_classes = [IsAuthenticated, IsBranchStaff]

    @extend_schema(
        request=BookingStatusUpdateSerializer,
        responses={200: OpenApiResponse(description='Yangilangan holat')},
        summary='Bron holatini yangilash',
        tags=['CRM'],
    )
    def patch(self, request, branch_id, booking_id):
        staff = request.user.branch_staff_profile
        if str(staff.branch_id) != str(branch_id):
            return Response({'message': 'Kirish taqiqlangan.'}, status=status.HTTP_403_FORBIDDEN)
        if not staff.has_permission('manage_bookings'):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            booking = Booking.objects.get(
                id=booking_id,
                restaurant_detail__branch_id=branch_id,
            )
        except Booking.DoesNotExist:
            return Response({'message': 'Bron topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = BookingStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking.status = serializer.validated_data['status']
        booking.save(update_fields=['status', 'updated_at'])
        return Response({'status': booking.status, 'message': 'Yangilandi.'})


class BranchAnalyticsView(APIView):
    """GET /api/crm/branches/{branch_id}/analytics/"""
    permission_classes = [IsAuthenticated, IsBranchStaff]

    @extend_schema(
        responses={200: OpenApiResponse(description='Analitika ma\'lumotlari')},
        summary='Filial analitika',
        tags=['CRM'],
    )
    def get(self, request, branch_id):
        staff = request.user.branch_staff_profile
        if str(staff.branch_id) != str(branch_id):
            return Response({'message': 'Kirish taqiqlangan.'}, status=status.HTTP_403_FORBIDDEN)
        if not staff.has_permission('view_analytics'):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)

        period = request.query_params.get('period', 'daily')
        qs = Booking.objects.filter(
            restaurant_detail__branch_id=branch_id,
            status=BookingStatus.CONFIRMED,
        )

        # Davr bo'yicha filtrlash
        now = timezone.now()
        if period == 'daily':
            qs = qs.filter(created_at__date=now.date())
        elif period == 'weekly':
            from datetime import timedelta
            qs = qs.filter(created_at__gte=now - timedelta(days=7))
        elif period == 'monthly':
            qs = qs.filter(created_at__year=now.year, created_at__month=now.month)

        aggregated = qs.aggregate(
            total_revenue=Sum('final_price'),
            total_confirmed=Sum('id'),
        )

        return Response({
            'period': period,
            'total_confirmed': qs.count(),
            'total_revenue': aggregated['total_revenue'] or 0,
        })
