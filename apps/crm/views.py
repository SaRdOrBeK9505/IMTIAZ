"""
CRM app views — filial xodimlari uchun panel.
Queryset darajasida filtrlash + permission tekshiruvi.
TZ 3.6 bo'limiga mos.

Qo'shimcha (yangi):
  - RestaurantTable CRUD (restoran CRM)
  - TableTimeSlot boshqaruvi
  - StaffActivityLog / StaffPerformanceSummary (xodimlar statistikasi)
"""

from datetime import timedelta

from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework import generics, status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsBranchStaff
from apps.booking.models import Booking, BookingStatus, RestaurantBooking, ServiceType
from .models import (
    RestaurantTable, TableTimeSlot, TableStatus,
    StaffActivityLog, StaffPerformanceSummary, BranchStaff,
)
from .serializers import (
    DashboardSerializer,
    BookingCRMSerializer,
    RestaurantBookingCRMSerializer,
    RestaurantBookingCreateSerializer,
    BookingStatusUpdateSerializer,
    BranchSerializer,
    RestaurantTableSerializer, RestaurantTableWriteSerializer,
    TableTimeSlotSerializer,
    StaffActivityLogSerializer,
    StaffPerformanceSummarySerializer,
    StaffLeaderboardSerializer,
)


class CRMAuthView(APIView):
    """POST /api/crm/auth/ — eski endpoint, login /api/crm/auth/login/ ga yo'naltiriladi."""
    permission_classes = []

    @extend_schema(
        request=None,
        responses={301: OpenApiResponse(description='Login endpointiga yo\'naltirish')},
        summary='CRM xodim kirishi (deprecated)',
        tags=['CRM'],
    )
    def post(self, request):
        return Response({
            'message': 'Bu endpoint eskirgan. POST /api/crm/auth/login/ dan foydalaning.',
            'login_url': '/api/crm/auth/login/',
        }, status=status.HTTP_410_GONE)


class CRMDashboardView(APIView):
    """
    GET /api/crm/dashboard/
    UI: Bosh sahifa — barcha modullar bo'yicha qisqa statistika.
    """
    permission_classes = [IsAuthenticated, IsBranchStaff]

    @extend_schema(
        responses={200: OpenApiResponse(description='CRM bosh sahifa statistikasi')},
        summary='CRM bosh sahifa (Dashboard)',
        tags=['CRM'],
    )
    def get(self, request):
        staff = request.user.branch_staff_profile
        org   = staff.branch.organization
        today = timezone.now().date()

        data = {
            'organization': {
                'id':   str(org.id),
                'name': org.name,
                'type': org.org_type,
            },
            'branch': BranchSerializer(staff.branch).data,
            'staff': {
                'name': staff.user.full_name,
                'role': staff.role,
            },
        }

        # Restoran moduli
        if org.org_type in ('restaurant', 'other'):
            tables = RestaurantTable.objects.filter(branch=staff.branch, is_active=True)
            bookings_today = Booking.objects.filter(
                restaurant_detail__branch=staff.branch,
                restaurant_detail__reservation_at__date=today,
            )
            data['restaurant'] = {
                'tables_total':    tables.count(),
                'tables_available': tables.filter(current_status='available').count(),
                'tables_occupied':  tables.filter(current_status='occupied').count(),
                'bookings_today':   bookings_today.count(),
                'pending_bookings': bookings_today.filter(status=BookingStatus.PENDING).count(),
                'confirmed_bookings': bookings_today.filter(status=BookingStatus.CONFIRMED).count(),
            }

        # Tur moduli
        if org.org_type == 'tour_company':
            from apps.booking.models import TourBooking
            from apps.tours.models import TourPackage
            tour_qs = TourBooking.objects.filter(package__organization=org)
            data['tours'] = {
                'active_packages':  TourPackage.objects.filter(organization=org, is_active=True).count(),
                'pending_applications': tour_qs.filter(booking__status=BookingStatus.PENDING).count(),
                'in_progress':        tour_qs.filter(booking__status=BookingStatus.IN_PROGRESS).count(),
                'confirmed_today':      tour_qs.filter(
                    booking__status=BookingStatus.CONFIRMED,
                    confirmed_at__date=today,
                ).count(),
            }

        # QR moduli (barcha tashkilot turlari uchun)
        try:
            from apps.qr_codes.models import QRCode, QRCodeRedemption
            qr_org = org
            qr_codes = QRCode.objects.filter(organization=qr_org, is_active=True)
            redemptions_today = QRCodeRedemption.objects.filter(
                qr_code__organization=qr_org,
                status='applied',
                scanned_at__date=today,
            )
            data['qr'] = {
                'active_bonuses':  qr_codes.count(),
                'scans_today':     redemptions_today.count(),
                'discount_today':  str(
                    redemptions_today.aggregate(t=Sum('discount_applied'))['t'] or 0
                ),
            }
        except Exception:
            pass

        return Response(data)


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
            qs = qs.filter(created_at__gte=now - timedelta(days=7))
        elif period == 'monthly':
            qs = qs.filter(created_at__year=now.year, created_at__month=now.month)

        aggregated = qs.aggregate(
            total_revenue=Sum('final_price'),
        )

        return Response({
            'period': period,
            'total_confirmed': qs.count(),
            'total_revenue': aggregated['total_revenue'] or 0,
        })


# ═══════════════════════════════════════════════════════════════════════════════
# RESTORAN STOL BOSHQARUVI
# ═══════════════════════════════════════════════════════════════════════════════

class RestaurantTableListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/crm/restaurant/tables/     — filial stollari
    POST /api/crm/restaurant/tables/     — yangi stol qo'shish
    """
    permission_classes = [IsAuthenticated, IsBranchStaff]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ['table_number', 'section']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return RestaurantTableWriteSerializer
        return RestaurantTableSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return RestaurantTable.objects.none()
        staff = self.request.user.branch_staff_profile
        qs = RestaurantTable.objects.filter(branch=staff.branch).order_by('section', 'table_number')

        # Filterlar
        params = self.request.query_params
        if section := params.get('section'):
            qs = qs.filter(section=section)
        if is_active := params.get('is_active'):
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        if current_status := params.get('status'):
            qs = qs.filter(current_status=current_status)
        if is_vip := params.get('is_vip'):
            qs = qs.filter(is_vip=(is_vip.lower() == 'true'))
        return qs

    @extend_schema(
        summary    = 'Restoran stollar ro\'yxati (CRM)',
        tags       = ['CRM Restaurant'],
        parameters = [
            OpenApiParameter('section',    str,  description='Stol bo\'limi'),
            OpenApiParameter('is_active',  bool, description='Faol/faol emas'),
            OpenApiParameter('status',     str,  description='available|reserved|occupied|maintenance'),
            OpenApiParameter('is_vip',     bool, description='VIP stollar'),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request   = RestaurantTableWriteSerializer,
        responses = {201: RestaurantTableSerializer},
        summary   = 'Yangi stol qo\'shish (CRM)',
        tags      = ['CRM Restaurant'],
    )
    def post(self, request, *args, **kwargs):
        staff = request.user.branch_staff_profile
        if not staff.has_permission('manage_bookings'):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = RestaurantTableWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        table = RestaurantTable.objects.create(
            branch=staff.branch, **serializer.validated_data
        )
        StaffActivityLog.objects.create(
            staff=staff,
            action_type=StaffActivityLog.ActionType.ADD_TABLE,
            entity_type='RestaurantTable', entity_id=table.id,
            description=f'Yangi stol qo\'shildi: {table.table_number}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return Response(RestaurantTableSerializer(table).data, status=status.HTTP_201_CREATED)


class RestaurantTableDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/PATCH/DELETE /api/crm/restaurant/tables/<id>/"""
    permission_classes = [IsAuthenticated, IsBranchStaff]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return RestaurantTableWriteSerializer
        return RestaurantTableSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return RestaurantTable.objects.none()
        staff = self.request.user.branch_staff_profile
        return RestaurantTable.objects.filter(branch=staff.branch)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])

    @extend_schema(summary='Stol tafsiloti (CRM)', tags=['CRM Restaurant'])
    def get(self, request, *args, **kwargs): return super().get(request, *args, **kwargs)

    @extend_schema(summary='Stolni yangilash (CRM)', tags=['CRM Restaurant'])
    def patch(self, request, *args, **kwargs): return super().patch(request, *args, **kwargs)

    @extend_schema(summary='Stolni o\'chirish (soft, CRM)', tags=['CRM Restaurant'])
    def delete(self, request, *args, **kwargs): return super().delete(request, *args, **kwargs)


class RestaurantTableStatusView(APIView):
    """PATCH /api/crm/restaurant/tables/<id>/status/ — stol holatini yangilash."""
    permission_classes = [IsAuthenticated, IsBranchStaff]

    @extend_schema(
        request   = None,
        responses = {200: RestaurantTableSerializer},
        summary   = 'Stol holati yangilash (CRM)',
        tags      = ['CRM Restaurant'],
        parameters = [OpenApiParameter('current_status', str, description='available|reserved|occupied|maintenance')]
    )
    def patch(self, request, pk=None):
        staff = request.user.branch_staff_profile
        if not staff.has_permission('manage_bookings'):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get('current_status')
        if new_status not in [s.value for s in TableStatus]:
            return Response({'message': 'Noto\'g\'ri holat.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            table = RestaurantTable.objects.get(id=pk, branch=staff.branch)
        except RestaurantTable.DoesNotExist:
            return Response({'message': 'Stol topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        table.current_status    = new_status
        table.status_updated_at = timezone.now()
        table.save(update_fields=['current_status', 'status_updated_at', 'updated_at'])

        StaffActivityLog.objects.create(
            staff=staff,
            action_type=StaffActivityLog.ActionType.UPDATE_TABLE_STATUS,
            entity_type='RestaurantTable', entity_id=table.id,
            description=f'{table.table_number} → {new_status}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return Response(RestaurantTableSerializer(table).data)


class RestaurantTableAvailabilityView(APIView):
    """GET /api/crm/restaurant/tables/availability/?date=YYYY-MM-DD"""
    permission_classes = [IsAuthenticated, IsBranchStaff]

    @extend_schema(
        responses  = {200: OpenApiResponse(description='Kun bo\'yicha bo\'sh stollar')},
        summary    = 'Kun bo\'yicha stol mavjudligi (CRM)',
        tags       = ['CRM Restaurant'],
        parameters = [
            OpenApiParameter('date', str, description='YYYY-MM-DD (default: bugun)'),
            OpenApiParameter('time', str, description='HH:MM (ixtiyoriy)'),
        ]
    )
    def get(self, request):
        staff      = request.user.branch_staff_profile
        date_str   = request.query_params.get('date', timezone.now().date().isoformat())
        time_str   = request.query_params.get('time')

        tables = RestaurantTable.objects.filter(
            branch=staff.branch, is_active=True
        ).order_by('section', 'table_number')

        result = []
        for table in tables:
            slots_qs = table.time_slots.filter(date=date_str)
            if time_str:
                slots_qs = slots_qs.filter(start_time__lte=time_str, end_time__gte=time_str)

            booked_slots = slots_qs.filter(is_available=False).count()
            result.append({
                'id':             str(table.id),
                'table_number':   table.table_number,
                'section':        table.section,
                'capacity':       table.capacity,
                'is_vip':         table.is_vip,
                'features':       table.features,
                'current_status': table.current_status,
                'booked_slots':   booked_slots,
                'is_free':        table.current_status == TableStatus.AVAILABLE,
            })

        return Response({'date': date_str, 'tables': result})


class RestaurantTablesGroupedView(APIView):
    """
    GET /api/crm/restaurant/tables/grouped/
    UI: /restaurant/tables — bo'limlar bo'yicha guruhlangan stollar.
    """
    permission_classes = [IsAuthenticated, IsBranchStaff]

    @extend_schema(
        responses={200: OpenApiResponse(description='Bo\'limlar bo\'yicha stollar')},
        summary='Stollar guruhlangan (CRM — /restaurant/tables)',
        tags=['CRM Restaurant'],
        parameters=[
            OpenApiParameter('section', str, description='Faqat bitta bo\'lim: Ichki, Tashqi, VIP, Teras'),
        ],
    )
    def get(self, request):
        staff = request.user.branch_staff_profile
        qs = RestaurantTable.objects.filter(
            branch=staff.branch, is_active=True,
        ).order_by('section', 'table_number')

        if section := request.query_params.get('section'):
            qs = qs.filter(section__iexact=section)

        sections = {}
        for table in qs:
            key = table.section or 'Boshqa'
            sections.setdefault(key, {'section': key, 'count': 0, 'tables': []})
            sections[key]['count'] += 1
            sections[key]['tables'].append(RestaurantTableSerializer(table).data)

        return Response({
            'sections': list(sections.values()),
            'total':    qs.count(),
        })


class RestaurantBookingsCRMListView(generics.ListCreateAPIView):
    """
    GET  /api/crm/restaurant/bookings/ — restoran bronlari
    POST /api/crm/restaurant/bookings/ — yangi bron (+ Yangi bron)
    """
    permission_classes = [IsAuthenticated, IsBranchStaff]
    serializer_class   = RestaurantBookingCRMSerializer

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return RestaurantBookingCreateSerializer
        return RestaurantBookingCRMSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()
        staff     = self.request.user.branch_staff_profile
        if not staff.has_permission('view_bookings'):
            return Booking.objects.none()
        qs = Booking.objects.filter(
            restaurant_detail__branch=staff.branch
        ).select_related('user', 'restaurant_detail').order_by('-created_at')

        params = self.request.query_params
        if s := params.get('status'):
            qs = qs.filter(status=s)
        if d := params.get('date'):
            qs = qs.filter(restaurant_detail__reservation_at__date=d)
        return qs

    @extend_schema(summary='Restoran bronlari (CRM)', tags=['CRM Restaurant'])
    def get(self, request, *args, **kwargs): return super().get(request, *args, **kwargs)

    @extend_schema(
        request   = RestaurantBookingCreateSerializer,
        responses = {201: RestaurantBookingCRMSerializer},
        summary   = 'Yangi restoran bron (CRM)',
        tags      = ['CRM Restaurant'],
    )
    def post(self, request, *args, **kwargs):
        staff = request.user.branch_staff_profile
        if not staff.has_permission('manage_bookings'):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)

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
                'last_name':  ' '.join(data['customer_name'].split()[1:]) if data['customer_name'] else '',
                'role':       UserRole.CUSTOMER,
            },
        )

        table_number = data.get('table_number', '')
        if table_id := data.get('table_id'):
            try:
                table = RestaurantTable.objects.get(id=table_id, branch=staff.branch)
                table_number = table.table_number
            except RestaurantTable.DoesNotExist:
                return Response({'message': 'Stol topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        booking = Booking.objects.create(
            user         = user,
            service_type = ServiceType.RESTAURANT,
            status       = BookingStatus.PENDING,
            title        = f'Stol #{table_number}' if table_number else 'Restoran broni',
            booking_date = data['reservation_at'],
        )
        RestaurantBooking.objects.create(
            booking          = booking,
            branch           = staff.branch,
            reservation_at   = data['reservation_at'],
            guest_count      = data['guest_count'],
            duration_minutes = data['duration_minutes'],
            special_requests = data.get('special_requests', ''),
            table_number     = table_number or None,
        )

        StaffActivityLog.objects.create(
            staff=staff,
            action_type=StaffActivityLog.ActionType.CONFIRM_TABLE_BOOKING,
            entity_type='RestaurantBooking',
            entity_id=booking.id,
            description=f'Yangi bron yaratildi: {data["customer_name"]}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        booking = Booking.objects.select_related('user', 'restaurant_detail').get(id=booking.id)
        return Response(RestaurantBookingCRMSerializer(booking).data, status=status.HTTP_201_CREATED)


class RestaurantBookingConfirmView(APIView):
    """POST /api/crm/restaurant/bookings/<id>/confirm/ — bronni tasdiqlash."""
    permission_classes = [IsAuthenticated, IsBranchStaff]

    @extend_schema(
        responses={200: RestaurantBookingCRMSerializer},
        summary='Restoran bronini tasdiqlash (CRM)',
        tags=['CRM Restaurant'],
    )
    def post(self, request, pk=None):
        staff = request.user.branch_staff_profile
        if not staff.has_permission('manage_bookings'):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            booking = Booking.objects.select_related('user', 'restaurant_detail').get(
                id=pk,
                restaurant_detail__branch=staff.branch,
            )
        except Booking.DoesNotExist:
            return Response({'message': 'Bron topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        if booking.status == BookingStatus.CONFIRMED:
            return Response({'message': 'Bron allaqachon tasdiqlangan.'}, status=status.HTTP_400_BAD_REQUEST)

        booking.status = BookingStatus.CONFIRMED
        booking.save(update_fields=['status', 'updated_at'])

        if hasattr(booking, 'restaurant_detail') and booking.restaurant_detail:
            booking.restaurant_detail.confirmed_by_staff = True
            booking.restaurant_detail.save(update_fields=['confirmed_by_staff', 'updated_at'])

        StaffActivityLog.objects.create(
            staff=staff,
            action_type=StaffActivityLog.ActionType.CONFIRM_TABLE_BOOKING,
            entity_type='RestaurantBooking',
            entity_id=booking.id,
            description=f'Bron tasdiqlandi: {booking.user.full_name}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        return Response(RestaurantBookingCRMSerializer(booking).data)


class RestaurantBookingCancelView(APIView):
    """POST /api/crm/restaurant/bookings/<id>/cancel/ — bronni bekor qilish."""
    permission_classes = [IsAuthenticated, IsBranchStaff]

    @extend_schema(
        responses={200: RestaurantBookingCRMSerializer},
        summary='Restoran bronini bekor qilish (CRM)',
        tags=['CRM Restaurant'],
    )
    def post(self, request, pk=None):
        staff = request.user.branch_staff_profile
        if not staff.has_permission('manage_bookings'):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            booking = Booking.objects.select_related('user', 'restaurant_detail').get(
                id=pk,
                restaurant_detail__branch=staff.branch,
            )
        except Booking.DoesNotExist:
            return Response({'message': 'Bron topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        if booking.status == BookingStatus.CANCELLED:
            return Response({'message': 'Bron allaqachon bekor qilingan.'}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get('reason', '')
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.cancellation_reason = reason
        booking.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'updated_at'])

        StaffActivityLog.objects.create(
            staff=staff,
            action_type=StaffActivityLog.ActionType.CANCEL_TABLE_BOOKING,
            entity_type='RestaurantBooking',
            entity_id=booking.id,
            description=f'Bron bekor qilindi: {booking.user.full_name}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        return Response(RestaurantBookingCRMSerializer(booking).data)


# ═══════════════════════════════════════════════════════════════════════════════
# XODIMLAR STATISTIKASI
# ═══════════════════════════════════════════════════════════════════════════════

class StaffListView(generics.ListAPIView):
    """GET /api/crm/staff/ — kompaniya/filial xodimlari ro'yxati."""
    permission_classes = [IsAuthenticated, IsBranchStaff]
    serializer_class   = StaffLeaderboardSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return BranchStaff.objects.none()
        staff = self.request.user.branch_staff_profile
        if not (staff.has_permission('manage_staff') or staff.has_permission('view_analytics')):
            return BranchStaff.objects.none()
        return BranchStaff.objects.filter(
            branch__organization=staff.branch.organization,
            is_active=True,
        ).select_related('user', 'branch')

    @extend_schema(summary='Xodimlar ro\'yxati (CRM)', tags=['CRM Staff'])
    def get(self, request, *args, **kwargs): return super().get(request, *args, **kwargs)


class MyStaffStatsView(APIView):
    """GET /api/crm/staff/me/stats/ — o'z statistikam."""
    permission_classes = [IsAuthenticated, IsBranchStaff]

    @extend_schema(
        responses  = {200: StaffPerformanceSummarySerializer(many=True)},
        summary    = 'Mening statistikam (CRM)',
        tags       = ['CRM Staff'],
        parameters = [OpenApiParameter('period', str, description='daily|weekly|monthly')]
    )
    def get(self, request):
        staff  = request.user.branch_staff_profile
        period = request.query_params.get('period', 'monthly')

        summaries = StaffPerformanceSummary.objects.filter(
            staff=staff, period_type=period
        ).order_by('-period_start')[:12]

        # Real-time bugungi ma'lumotlar
        today_logs = StaffActivityLog.objects.filter(
            staff=staff, created_at__date=timezone.now().date()
        )
        today_stats = {
            'confirmed_today': today_logs.filter(
                action_type=StaffActivityLog.ActionType.CONFIRM_TOUR_BOOKING
            ).count(),
            'vouchers_today': today_logs.filter(
                action_type=StaffActivityLog.ActionType.GENERATE_VOUCHER
            ).count(),
            'total_actions_today': today_logs.count(),
            'last_active':         today_logs.order_by('-created_at').values_list(
                'created_at', flat=True
            ).first(),
        }

        return Response({
            'staff_info': {
                'id':     str(staff.id),
                'name':   staff.user.full_name,
                'role':   staff.role,
                'branch': staff.branch.name,
            },
            'today':      today_stats,
            'history':    StaffPerformanceSummarySerializer(summaries, many=True).data,
        })


class StaffStatsView(APIView):
    """GET /api/crm/staff/<id>/stats/ — xodim statistikasi (rahbar uchun)."""
    permission_classes = [IsAuthenticated, IsBranchStaff]

    @extend_schema(
        responses  = {200: StaffPerformanceSummarySerializer(many=True)},
        summary    = 'Xodim statistikasi (rahbar uchun, CRM)',
        tags       = ['CRM Staff'],
        parameters = [OpenApiParameter('period', str, description='daily|weekly|monthly')]
    )
    def get(self, request, pk=None):
        requester = request.user.branch_staff_profile
        if not (requester.has_permission('manage_staff') or requester.has_permission('view_analytics')):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            target = BranchStaff.objects.select_related('user', 'branch').get(
                id=pk,
                branch__organization=requester.branch.organization,
            )
        except BranchStaff.DoesNotExist:
            return Response({'message': 'Xodim topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        period    = request.query_params.get('period', 'monthly')
        summaries = StaffPerformanceSummary.objects.filter(
            staff=target, period_type=period
        ).order_by('-period_start')[:12]

        # Oxirgi 30 kunlik faoliyat
        from_date  = timezone.now() - timedelta(days=30)
        activities = StaffActivityLog.objects.filter(
            staff=target, created_at__gte=from_date
        ).values('action_type').annotate(count=Count('id')).order_by('-count')

        return Response({
            'staff_info': {
                'id':          str(target.id),
                'name':        target.user.full_name,
                'phone':       target.user.phone,
                'role':        target.role,
                'branch':      target.branch.name,
                'permissions': target.permissions,
                'joined':      target.created_at.isoformat(),
            },
            'activity_breakdown': list(activities),
            'history': StaffPerformanceSummarySerializer(summaries, many=True).data,
        })


class StaffLeaderboardView(APIView):
    """GET /api/crm/staff/leaderboard/ — xodimlar reytingi."""
    permission_classes = [IsAuthenticated, IsBranchStaff]

    @extend_schema(
        responses  = {200: OpenApiResponse(description='Xodimlar reytingi')},
        summary    = 'Xodimlar reytingi (CRM)',
        tags       = ['CRM Staff'],
        parameters = [OpenApiParameter('period', str, description='daily|weekly|monthly')]
    )
    def get(self, request):
        requester = request.user.branch_staff_profile
        if not (requester.has_permission('manage_staff') or requester.has_permission('view_analytics')):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)

        period = request.query_params.get('period', 'monthly')
        now    = timezone.now()

        if period == 'daily':
            start = now.replace(hour=0, minute=0, second=0)
        elif period == 'weekly':
            start = now - timedelta(days=7)
        else:
            start = now.replace(day=1, hour=0, minute=0, second=0)

        staff_list = BranchStaff.objects.filter(
            branch__organization=requester.branch.organization,
            is_active=True,
        ).select_related('user', 'branch')

        leaderboard = []
        for s in staff_list:
            logs = StaffActivityLog.objects.filter(staff=s, created_at__gte=start)
            leaderboard.append({
                'staff_id':     str(s.id),
                'name':         s.user.full_name,
                'branch':       s.branch.name,
                'role':         s.role,
                'confirmed':    logs.filter(action_type=StaffActivityLog.ActionType.CONFIRM_TOUR_BOOKING).count(),
                'vouchers':     logs.filter(action_type=StaffActivityLog.ActionType.GENERATE_VOUCHER).count(),
                'total_actions': logs.count(),
                'last_active':  logs.order_by('-created_at').values_list('created_at', flat=True).first(),
            })

        # Eng ko'p confirmed bo'yicha tartiblash
        leaderboard.sort(key=lambda x: x['confirmed'], reverse=True)

        return Response({'period': period, 'leaderboard': leaderboard})


class StaffActivityView(generics.ListAPIView):
    """GET /api/crm/staff/activity/ — faoliyat jurnali."""
    permission_classes = [IsAuthenticated, IsBranchStaff]
    serializer_class   = StaffActivityLogSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return StaffActivityLog.objects.none()
        requester = self.request.user.branch_staff_profile
        qs = StaffActivityLog.objects.filter(
            staff__branch__organization=requester.branch.organization
        ).select_related('staff__user').order_by('-created_at')

        params = self.request.query_params
        if staff_id := params.get('staff_id'):
            qs = qs.filter(staff_id=staff_id)
        if action_type := params.get('action_type'):
            qs = qs.filter(action_type=action_type)
        if date := params.get('date'):
            qs = qs.filter(created_at__date=date)
        return qs

    @extend_schema(
        summary    = 'Xodimlar faoliyat jurnali (CRM)',
        tags       = ['CRM Staff'],
        parameters = [
            OpenApiParameter('staff_id',    str, description='Xodim ID'),
            OpenApiParameter('action_type', str, description='Harakat turi'),
            OpenApiParameter('date',        str, description='YYYY-MM-DD'),
        ]
    )
    def get(self, request, *args, **kwargs): return super().get(request, *args, **kwargs)

