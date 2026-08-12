"""
CRM legacy views — /api/crm/ (filial paneli, backward compatibility).

Yangi API:
    /api/crm/restaurant/  — restoran CRM
    /api/crm/tour/        — tur CRM
"""

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.booking.models import Booking, BookingStatus
from apps.core.authentication import CRMJWTAuthentication
from apps.core.permissions import IsRestaurantStaff

from .models import RestaurantTable
from .serializers import (
    BookingCRMSerializer,
    BookingStatusUpdateSerializer,
    BranchSerializer,
)


class LegacyCRMViewMixin:
    """Legacy CRM — faqat CRM JWT (aud=crm)."""
    authentication_classes = [CRMJWTAuthentication]


class CRMAuthView(APIView):
    """POST /api/crm/auth/ — deprecated."""
    permission_classes = []

    @extend_schema(
        tags=['Auth — CRM (O\'chirilgan)'],
        summary='CRM kirish — eskirgan URL (410)',
        description=(
            'Eski login endpoint. **O\'rniga:** `POST /api/crm/auth/login/` dan foydalaning.\n\n'
            'Endpoint keyinroq butunlay olib tashlanadi.'
        ),
        request=None,
        responses={410: OpenApiResponse(description='Eskirgan endpoint')},
        deprecated=True,
    )
    def post(self, request):
        return Response({
            'message': 'Bu endpoint eskirgan. POST /api/crm/auth/login/ dan foydalaning.',
            'login_url': '/api/crm/auth/login/',
        }, status=status.HTTP_410_GONE)


class CRMDashboardView(LegacyCRMViewMixin, APIView):
    """GET /api/crm/dashboard/ — legacy bosh sahifa."""
    permission_classes = [IsAuthenticated, IsRestaurantStaff]

    @extend_schema(
        responses={200: OpenApiResponse(description='CRM bosh sahifa statistikasi')},
        summary='CRM bosh sahifa (legacy)',
        tags=['CRM Legacy'],
        deprecated=True,
    )
    def get(self, request):
        staff = request.user.branch_staff_profile
        org = staff.branch.organization
        today = timezone.now().date()

        data = {
            'deprecated': True,
            'migrate_to': '/api/crm/restaurant/dashboard/',
            'organization': {
                'id': str(org.id),
                'name': org.name,
                'type': org.org_type,
            },
            'branch': BranchSerializer(staff.branch).data,
            'staff': {
                'name': staff.user.full_name,
                'role': staff.role,
            },
        }

        if org.org_type in ('restaurant', 'other'):
            tables = RestaurantTable.objects.filter(branch=staff.branch, is_active=True)
            bookings_today = Booking.objects.filter(
                restaurant_detail__branch=staff.branch,
                restaurant_detail__reservation_at__date=today,
            )
            data['restaurant'] = {
                'tables_total': tables.count(),
                'tables_available': tables.filter(current_status='available').count(),
                'tables_occupied': tables.filter(current_status='occupied').count(),
                'bookings_today': bookings_today.count(),
                'pending_bookings': bookings_today.filter(status=BookingStatus.PENDING).count(),
                'confirmed_bookings': bookings_today.filter(status=BookingStatus.CONFIRMED).count(),
            }

        return Response(data)


class BranchDashboardView(LegacyCRMViewMixin, APIView):
    """GET /api/crm/branches/{branch_id}/dashboard/"""
    permission_classes = [IsAuthenticated, IsRestaurantStaff]

    @extend_schema(
        responses={200: OpenApiResponse(description='Filial dashboard')},
        summary='Filial dashboard (legacy)',
        tags=['CRM Legacy'],
        deprecated=True,
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
            'deprecated': True,
            'migrate_to': '/api/crm/restaurant/dashboard/',
            'branch': BranchSerializer(staff.branch).data,
            'total_bookings_today': qs.count(),
            'pending_bookings': qs.filter(status=BookingStatus.PENDING).count(),
            'confirmed_bookings': qs.filter(status=BookingStatus.CONFIRMED).count(),
            'revenue_today': qs.filter(
                status=BookingStatus.CONFIRMED,
            ).aggregate(total=Sum('final_price'))['total'] or 0,
        })


class BranchBookingListView(LegacyCRMViewMixin, generics.ListAPIView):
    """GET /api/crm/branches/{branch_id}/bookings/"""
    permission_classes = [IsAuthenticated, IsRestaurantStaff]
    serializer_class = BookingCRMSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()
        staff = self.request.user.branch_staff_profile
        branch_id = self.kwargs['branch_id']
        if str(staff.branch_id) != str(branch_id) or not staff.has_permission('view_bookings'):
            return Booking.objects.none()

        qs = Booking.objects.filter(
            restaurant_detail__branch_id=branch_id,
        ).select_related('user').order_by('-created_at')

        if s := self.request.query_params.get('status'):
            qs = qs.filter(status=s)
        if d := self.request.query_params.get('date'):
            qs = qs.filter(booking_date__date=d)
        return qs

    @extend_schema(
        tags=['CRM Legacy'],
        deprecated=True,
        summary='Filial bronlari (legacy)',
        parameters=[
            OpenApiParameter('status', str),
            OpenApiParameter('date', str, description='YYYY-MM-DD'),
        ],
        responses={200: BookingCRMSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BookingStatusUpdateView(LegacyCRMViewMixin, APIView):
    """PATCH /api/crm/branches/{branch_id}/bookings/{booking_id}/status/"""
    permission_classes = [IsAuthenticated, IsRestaurantStaff]

    @extend_schema(
        request=BookingStatusUpdateSerializer,
        responses={200: OpenApiResponse(description='Yangilangan holat')},
        summary='Bron holati (legacy)',
        tags=['CRM Legacy'],
        deprecated=True,
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


class BranchAnalyticsView(LegacyCRMViewMixin, APIView):
    """GET /api/crm/branches/{branch_id}/analytics/"""
    permission_classes = [IsAuthenticated, IsRestaurantStaff]

    @extend_schema(
        responses={200: OpenApiResponse(description='Analitika')},
        summary='Filial analitika (legacy)',
        tags=['CRM Legacy'],
        deprecated=True,
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

        now = timezone.now()
        if period == 'daily':
            qs = qs.filter(created_at__date=now.date())
        elif period == 'weekly':
            qs = qs.filter(created_at__gte=now - timedelta(days=7))
        elif period == 'monthly':
            qs = qs.filter(created_at__year=now.year, created_at__month=now.month)

        aggregated = qs.aggregate(total_revenue=Sum('final_price'))

        return Response({
            'deprecated': True,
            'migrate_to': '/api/crm/restaurant/analytics/',
            'period': period,
            'total_confirmed': qs.count(),
            'total_revenue': aggregated['total_revenue'] or 0,
        })
