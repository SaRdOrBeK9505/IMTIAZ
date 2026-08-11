"""
Tours — CRM views (tur kompaniyasi xodimlari uchun).

Endpointlar:
    # Paketlar
    GET/POST          /api/crm/tours/packages/
    GET/PUT/DELETE    /api/crm/tours/packages/<id>/
    GET/POST          /api/crm/tours/packages/<id>/availability/
    PUT/DELETE        /api/crm/tours/packages/<id>/availability/<avail_id>/

    # Bronlar
    GET               /api/crm/tours/bookings/
    GET               /api/crm/tours/bookings/<id>/
    POST              /api/crm/tours/bookings/<id>/confirm/
    POST              /api/crm/tours/bookings/<id>/reject/
    POST              /api/crm/tours/bookings/<id>/voucher/generate/
    GET               /api/crm/tours/bookings/<id>/voucher/

    # Dashboard & Analytics
    GET               /api/crm/tours/dashboard/
    GET               /api/crm/tours/analytics/
"""

import logging
from datetime import timedelta

from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.booking.models import TourBooking, BookingStatus, Booking
from apps.crm.models import StaffActivityLog
from ..models import TourPackage, TourAvailability, TourVoucher
from ..serializers import (
    TourPackageCRMSerializer, TourPackageCRMWriteSerializer,
    TourAvailabilityCRMSerializer,
    TourBookingCRMListSerializer, TourBookingCRMDetailSerializer,
    TourBookingConfirmSerializer, TourBookingRejectSerializer,
    TourBookingProcessSerializer,
    TourClientSerializer, TourClientPurchaseSerializer,
    TourVoucherSerializer,
)
from ..services import TourBookingService, TourVoucherService
from ..permissions import (
    IsTourCompanyStaff, IsTourCompanyAdmin,
    CanManageTourPackages, CanConfirmTourBookings, CanGenerateVoucher,
)

logger = logging.getLogger(__name__)


def _log_staff_action(request, action_type, entity_type='', entity_id=None, description='', metadata=None):
    """Xodim harakatini qayd etish yordamchi funksiya."""
    try:
        staff = request.user.branch_staff_profile
        StaffActivityLog.objects.create(
            staff       = staff,
            action_type = action_type,
            entity_type = entity_type,
            entity_id   = entity_id,
            description = description,
            metadata    = metadata or {},
            ip_address  = request.META.get('REMOTE_ADDR'),
        )
    except Exception as e:
        logger.warning('StaffActivityLog yozishda xato: %s', e)


def _get_staff_org(request):
    """Xodimning tashkilotini olish."""
    return request.user.branch_staff_profile.branch.organization


def _tour_bookings_qs(org):
    """Tashkilot bo'yicha tur bronlari queryset."""
    return TourBooking.objects.filter(
        package__organization=org,
    ).select_related(
        'booking__user', 'package__destination', 'availability', 'confirmed_by',
    ).order_by('-booking__created_at')


def _application_summary(org) -> dict:
    """Arizalar tablari uchun sonlar."""
    base = TourBooking.objects.filter(package__organization=org)
    pending     = base.filter(booking__status=BookingStatus.PENDING).count()
    in_progress = base.filter(booking__status=BookingStatus.IN_PROGRESS).count()
    confirmed   = base.filter(booking__status=BookingStatus.CONFIRMED).count()
    rejected    = base.filter(booking__status=BookingStatus.CANCELLED).count()
    return {
        'all':         pending + in_progress,
        'pending':     pending,
        'in_progress': in_progress,
        'confirmed':   confirmed,
        'rejected':    rejected,
        'ai_reprocessed': base.filter(ai_reprocessed=True).count(),
    }


_STATUS_LABELS = {
    'pending':     'Yangi',
    'in_progress': 'Jarayonda',
    'confirmed':   'Tasdiqlangan',
    'cancelled':   'Rad etilgan',
    'completed':   'Bajarilgan',
}


# ─── Tur Paketlari (CRM) ──────────────────────────────────────────────────────

class TourPackageCRMListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/crm/tours/packages/ — kompaniya paketlari
    POST /api/crm/tours/packages/ — yangi paket yaratish
    """
    permission_classes = [IsAuthenticated, CanManageTourPackages]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TourPackageCRMWriteSerializer
        return TourPackageCRMSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TourPackage.objects.none()
        org = _get_staff_org(self.request)
        return TourPackage.objects.filter(
            organization=org
        ).select_related('destination', 'category').prefetch_related('itinerary_days')

    @extend_schema(summary='Tur paketlari (CRM)', tags=['CRM Tours'])
    def get(self, request, *args, **kwargs):
        _log_staff_action(request, StaffActivityLog.ActionType.MANAGE_PACKAGES, description='Paketlar ro\'yxati ko\'rildi')
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request   = TourPackageCRMWriteSerializer,
        responses = {201: TourPackageCRMSerializer},
        summary   = 'Yangi tur paketi (CRM)',
        tags      = ['CRM Tours'],
    )
    def post(self, request, *args, **kwargs):
        serializer = TourPackageCRMWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = _get_staff_org(request)
        package = TourPackage.objects.create(organization=org, **serializer.validated_data)
        _log_staff_action(
            request,
            StaffActivityLog.ActionType.MANAGE_PACKAGES,
            entity_type='TourPackage', entity_id=package.id,
            description=f'Yangi paket yaratildi: {package.title}',
        )
        return Response(TourPackageCRMSerializer(package).data, status=status.HTTP_201_CREATED)


class TourPackageCRMDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH /api/crm/tours/packages/<id>/
    DELETE        /api/crm/tours/packages/<id>/ (soft delete)
    """
    permission_classes = [IsAuthenticated, CanManageTourPackages]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return TourPackageCRMWriteSerializer
        return TourPackageCRMSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TourPackage.objects.none()
        org = _get_staff_org(self.request)
        return TourPackage.objects.filter(organization=org)

    def perform_destroy(self, instance):
        """Soft delete — is_active=False."""
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])
        _log_staff_action(
            self.request,
            StaffActivityLog.ActionType.MANAGE_PACKAGES,
            entity_type='TourPackage', entity_id=instance.id,
            description=f'Paket o\'chirildi: {instance.title}',
        )

    @extend_schema(summary='Tur paketi tafsiloti (CRM)', tags=['CRM Tours'])
    def get(self, request, *args, **kwargs): return super().get(request, *args, **kwargs)

    @extend_schema(summary='Tur paketini yangilash (CRM)', tags=['CRM Tours'])
    def put(self, request, *args, **kwargs): return super().put(request, *args, **kwargs)

    @extend_schema(summary='Tur paketini yangilash (partial, CRM)', tags=['CRM Tours'])
    def patch(self, request, *args, **kwargs): return super().patch(request, *args, **kwargs)

    @extend_schema(summary='Tur paketini o\'chirish (soft, CRM)', tags=['CRM Tours'])
    def delete(self, request, *args, **kwargs): return super().delete(request, *args, **kwargs)


# ─── Mavjudliklar (CRM) ───────────────────────────────────────────────────────

class TourAvailabilityCRMView(generics.ListCreateAPIView):
    """
    GET  /api/crm/tours/packages/<package_id>/availability/
    POST /api/crm/tours/packages/<package_id>/availability/
    """
    permission_classes = [IsAuthenticated, CanManageTourPackages]
    serializer_class   = TourAvailabilityCRMSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TourAvailability.objects.none()
        org = _get_staff_org(self.request)
        return TourAvailability.objects.filter(
            package_id=self.kwargs['package_id'],
            package__organization=org,
        ).order_by('departure_date')

    def perform_create(self, serializer):
        org = _get_staff_org(self.request)
        package = TourPackage.objects.get(
            id=self.kwargs['package_id'], organization=org
        )
        serializer.save(package=package)

    @extend_schema(summary='Tur mavjudliklari (CRM)', tags=['CRM Tours'])
    def get(self, request, *args, **kwargs): return super().get(request, *args, **kwargs)

    @extend_schema(summary='Yangi mavjudlik qo\'shish (CRM)', tags=['CRM Tours'])
    def post(self, request, *args, **kwargs): return super().post(request, *args, **kwargs)


class TourAvailabilityCRMDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/crm/tours/packages/<package_id>/availability/<avail_id>/
    """
    permission_classes = [IsAuthenticated, CanManageTourPackages]
    serializer_class   = TourAvailabilityCRMSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TourAvailability.objects.none()
        org = _get_staff_org(self.request)
        return TourAvailability.objects.filter(
            package_id=self.kwargs['package_id'],
            package__organization=org,
        )

    @extend_schema(summary='Mavjudlik tafsiloti (CRM)', tags=['CRM Tours'])
    def get(self, request, *args, **kwargs): return super().get(request, *args, **kwargs)

    @extend_schema(summary='Mavjudlikni yangilash (CRM)', tags=['CRM Tours'])
    def put(self, request, *args, **kwargs): return super().put(request, *args, **kwargs)

    @extend_schema(summary='Mavjudlikni yangilash (partial, CRM)', tags=['CRM Tours'])
    def patch(self, request, *args, **kwargs): return super().patch(request, *args, **kwargs)

    @extend_schema(summary='Mavjudlikni o\'chirish (CRM)', tags=['CRM Tours'])
    def delete(self, request, *args, **kwargs): return super().delete(request, *args, **kwargs)


# ─── Tur Bronlari (CRM) ───────────────────────────────────────────────────────

class TourBookingCRMListView(generics.ListAPIView):
    """GET /api/crm/tours/bookings/"""
    permission_classes = [IsAuthenticated, IsTourCompanyStaff]
    serializer_class   = TourBookingCRMListSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TourBooking.objects.none()
        org = _get_staff_org(self.request)
        qs  = TourBooking.objects.filter(
            package__organization=org
        ).select_related(
            'booking__user', 'package', 'availability'
        ).order_by('-booking__created_at')

        # Filterlar
        params = self.request.query_params
        if s := params.get('status'):
            qs = qs.filter(booking__status=s)
        if d := params.get('date'):
            qs = qs.filter(availability__departure_date=d)
        if pkg := params.get('package_id'):
            qs = qs.filter(package_id=pkg)
        if voucher := params.get('has_voucher'):
            qs = qs.filter(voucher_generated=(voucher.lower() == 'true'))
        if ai := params.get('created_by_ai'):
            qs = qs.filter(booking__created_by_ai=(ai.lower() == 'true'))

        return qs

    @extend_schema(
        summary    = 'Tur bronlari ro\'yxati (CRM)',
        tags       = ['CRM Tours'],
        parameters = [
            OpenApiParameter('status',        str,  description='Bron holati'),
            OpenApiParameter('date',          str,  description='Jo\'nash sanasi YYYY-MM-DD'),
            OpenApiParameter('package_id',    str,  description='Paket ID'),
            OpenApiParameter('has_voucher',   bool, description='Voaucheri bor/yo\'q'),
            OpenApiParameter('created_by_ai', bool, description='AI tomonidan yaratilgan'),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class TourBookingCRMDetailView(generics.RetrieveAPIView):
    """GET /api/crm/tours/bookings/<id>/"""
    permission_classes = [IsAuthenticated, IsTourCompanyStaff]
    serializer_class   = TourBookingCRMDetailSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TourBooking.objects.none()
        org = _get_staff_org(self.request)
        return TourBooking.objects.filter(
            package__organization=org
        ).select_related('booking__user', 'package__destination', 'availability')

    @extend_schema(summary='Tur bron tafsiloti (CRM)', tags=['CRM Tours'])
    def get(self, request, *args, **kwargs): return super().get(request, *args, **kwargs)


class TourBookingConfirmView(APIView):
    """POST /api/crm/tours/bookings/<id>/confirm/"""
    permission_classes = [IsAuthenticated, CanConfirmTourBookings]

    @extend_schema(
        request   = TourBookingConfirmSerializer,
        responses = {200: TourBookingCRMDetailSerializer},
        summary   = 'Tur bronini tasdiqlash (CRM)',
        tags      = ['CRM Tours'],
    )
    def post(self, request, pk=None):
        serializer = TourBookingConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Tashkilot tekshiruvi
        org = _get_staff_org(request)
        try:
            tour_booking = TourBooking.objects.select_related('package').get(
                id=pk, package__organization=org
            )
        except TourBooking.DoesNotExist:
            return Response({'message': 'Bron topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            tour_booking = TourBookingService.confirm_booking(
                str(pk),
                operator       = request.user,
                operator_notes = serializer.validated_data.get('operator_notes', ''),
            )
        except ValueError as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        _log_staff_action(
            request,
            StaffActivityLog.ActionType.CONFIRM_TOUR_BOOKING,
            entity_type='TourBooking', entity_id=tour_booking.id,
            description=f'Tur broni tasdiqlandi: {tour_booking.package.title}',
            metadata={'booking_id': str(tour_booking.booking_id)},
        )
        return Response(TourBookingCRMDetailSerializer(tour_booking).data)


class TourBookingRejectView(APIView):
    """POST /api/crm/tours/bookings/<id>/reject/"""
    permission_classes = [IsAuthenticated, CanConfirmTourBookings]

    @extend_schema(
        request   = TourBookingRejectSerializer,
        responses = {200: TourBookingCRMDetailSerializer},
        summary   = 'Tur bronini rad etish (CRM)',
        tags      = ['CRM Tours'],
    )
    def post(self, request, pk=None):
        serializer = TourBookingRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        org = _get_staff_org(request)
        try:
            TourBooking.objects.get(id=pk, package__organization=org)
        except TourBooking.DoesNotExist:
            return Response({'message': 'Bron topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            tour_booking = TourBookingService.reject_booking(
                str(pk),
                operator         = request.user,
                rejection_reason = serializer.validated_data['rejection_reason'],
            )
        except ValueError as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        _log_staff_action(
            request,
            StaffActivityLog.ActionType.REJECT_TOUR_BOOKING,
            entity_type='TourBooking', entity_id=tour_booking.id,
            description=f'Tur broni rad etildi: {serializer.validated_data["rejection_reason"][:100]}',
        )
        return Response(TourBookingCRMDetailSerializer(tour_booking).data)


class TourVoucherGenerateView(APIView):
    """POST /api/crm/tours/bookings/<id>/voucher/generate/"""
    permission_classes = [IsAuthenticated, CanGenerateVoucher]

    @extend_schema(
        responses = {201: TourVoucherSerializer},
        summary   = 'Voaucher yaratish (CRM)',
        tags      = ['CRM Tours'],
    )
    def post(self, request, pk=None):
        org = _get_staff_org(request)
        try:
            TourBooking.objects.get(id=pk, package__organization=org)
        except TourBooking.DoesNotExist:
            return Response({'message': 'Bron topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            voucher = TourVoucherService.generate_voucher(str(pk), operator=request.user)
        except ValueError as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        _log_staff_action(
            request,
            StaffActivityLog.ActionType.GENERATE_VOUCHER,
            entity_type='TourVoucher', entity_id=voucher.id,
            description=f'Voaucher yaratildi: {voucher.voucher_number}',
        )
        return Response(TourVoucherSerializer(voucher).data, status=status.HTTP_201_CREATED)


class TourVoucherCRMDetailView(APIView):
    """GET /api/crm/tours/bookings/<id>/voucher/"""
    permission_classes = [IsAuthenticated, IsTourCompanyStaff]

    @extend_schema(
        responses = {200: TourVoucherSerializer},
        summary   = 'Voaucher ko\'rish (CRM)',
        tags      = ['CRM Tours'],
    )
    def get(self, request, pk=None):
        org = _get_staff_org(request)
        try:
            tour_booking = TourBooking.objects.get(id=pk, package__organization=org)
        except TourBooking.DoesNotExist:
            return Response({'message': 'Bron topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            voucher = tour_booking.voucher
        except Exception:
            return Response({'message': 'Voaucher yaratilmagan.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(TourVoucherSerializer(voucher).data)


# ─── Dashboard & Analytics (CRM) ──────────────────────────────────────────────

class TourDashboardView(APIView):
    """GET /api/crm/tours/dashboard/"""
    permission_classes = [IsAuthenticated, IsTourCompanyStaff]

    @extend_schema(
        responses = {200: OpenApiResponse(description='Dashboard ko\'rsatkichlari')},
        summary   = 'Tur kompaniyasi dashboard (CRM)',
        tags      = ['CRM Tours'],
    )
    def get(self, request):
        org   = _get_staff_org(request)
        today = timezone.now().date()

        total_packages = TourPackage.objects.filter(organization=org, is_active=True).count()

        # Bronlar statistikasi (bugun yaratilgan)
        bookings_today = TourBooking.objects.filter(
            package__organization=org,
            booking__created_at__date=today,
        )
        pending_count   = bookings_today.filter(booking__status=BookingStatus.PENDING).count()
        confirmed_count = bookings_today.filter(booking__status=BookingStatus.CONFIRMED).count()
        rejected_count  = bookings_today.filter(booking__status=BookingStatus.CANCELLED).count()

        # Voaucherlar (bugun)
        vouchers_today = TourBooking.objects.filter(
            package__organization=org,
            voucher_generated_at__date=today,
        ).count()

        # Bugungi daromad (tasdiqlangan bronlar)
        revenue_today = Booking.objects.filter(
            tour_detail__package__organization=org,
            status=BookingStatus.CONFIRMED,
            created_at__date=today,
        ).aggregate(total=Sum('final_price'))['total'] or 0

        # Kelgusi 7 kunlik jo'nashlar
        upcoming_departures = TourAvailability.objects.filter(
            package__organization=org,
            departure_date__gte=today,
            departure_date__lte=today + timedelta(days=7),
            status='open',
        ).count()

        _log_staff_action(request, StaffActivityLog.ActionType.VIEW_ANALYTICS, description='Dashboard ko\'rildi')

        return Response({
            'total_packages':       total_packages,
            'bookings_today':       bookings_today.count(),
            'pending':              pending_count,
            'in_progress':          bookings_today.filter(booking__status=BookingStatus.IN_PROGRESS).count(),
            'confirmed':            confirmed_count,
            'rejected':             rejected_count,
            'vouchers_today':       vouchers_today,
            'revenue_today':        str(revenue_today),
            'upcoming_departures':  upcoming_departures,
        })


# ─── Arizalar / Tasdiqlangan / Mijozlar (UI sahifalari) ─────────────────────

class TourApplicationsView(APIView):
    """
    GET /api/crm/tours/applications/
    UI: /tours/applications — arizalar ro'yxati + tab sonlari.
    """
    permission_classes = [IsAuthenticated, IsTourCompanyStaff]

    @extend_schema(
        responses  = {200: OpenApiResponse(description='Tur arizalari')},
        summary    = 'Tur arizalari (CRM — /tours/applications)',
        tags       = ['CRM Tours'],
        parameters = [
            OpenApiParameter('status', str, description='pending | in_progress | confirmed | rejected | all'),
        ],
    )
    def get(self, request):
        org = _get_staff_org(request)
        qs  = _tour_bookings_qs(org)

        status = request.query_params.get('status', 'all')
        if status == 'pending':
            qs = qs.filter(booking__status=BookingStatus.PENDING)
        elif status == 'in_progress':
            qs = qs.filter(booking__status=BookingStatus.IN_PROGRESS)
        elif status == 'confirmed':
            qs = qs.filter(booking__status=BookingStatus.CONFIRMED)
        elif status == 'rejected':
            qs = qs.filter(booking__status=BookingStatus.CANCELLED)
        else:
            qs = qs.filter(booking__status__in=[BookingStatus.PENDING, BookingStatus.IN_PROGRESS])

        return Response({
            'summary':      _application_summary(org),
            'status_filter': status,
            'results':      TourBookingCRMListSerializer(qs, many=True).data,
        })


class TourConfirmedListView(APIView):
    """
    GET /api/crm/tours/confirmed/
    UI: /tours/confirmed — tasdiqlangan arizalar.
    """
    permission_classes = [IsAuthenticated, IsTourCompanyStaff]

    @extend_schema(
        responses = {200: TourBookingCRMListSerializer(many=True)},
        summary   = 'Tasdiqlangan arizalar (CRM — /tours/confirmed)',
        tags      = ['CRM Tours'],
    )
    def get(self, request):
        org = _get_staff_org(request)
        qs  = _tour_bookings_qs(org).filter(booking__status=BookingStatus.CONFIRMED)
        return Response({
            'count':   qs.count(),
            'results': TourBookingCRMListSerializer(qs, many=True).data,
        })


class TourClientsView(APIView):
    """
    GET /api/crm/tours/clients/
    UI: /tours/clients — mijozlar tarixi + qidiruv.
    """
    permission_classes = [IsAuthenticated, IsTourCompanyStaff]

    @extend_schema(
        responses  = {200: TourClientSerializer(many=True)},
        summary    = 'Mijozlar tarixi (CRM — /tours/clients)',
        tags       = ['CRM Tours'],
        parameters = [
            OpenApiParameter('q', str, description='Ism yoki telefon bo\'yicha qidiruv'),
        ],
    )
    def get(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        org = _get_staff_org(request)
        bookings = _tour_bookings_qs(org).filter(
            booking__status__in=[BookingStatus.CONFIRMED, BookingStatus.COMPLETED],
        )

        user_ids = bookings.values_list('booking__user_id', flat=True).distinct()
        users = User.objects.filter(id__in=user_ids)

        if q := request.query_params.get('q', '').strip():
            users = users.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(phone__icontains=q)
                | Q(email__icontains=q)
            )

        clients = []
        for user in users.order_by('first_name', 'last_name'):
            user_bookings = bookings.filter(booking__user=user)
            purchases = []
            for tb in user_bookings:
                voucher_number = None
                try:
                    voucher_number = tb.voucher.voucher_number
                except Exception:
                    pass
                dest = tb.package.destination
                purchases.append({
                    'tour_booking_id': tb.id,
                    'booking_id':      tb.booking_id,
                    'destination':     f'{dest.name}, {dest.country}' if dest else '',
                    'package_title':   tb.package.title,
                    'departure_date':  tb.availability.departure_date,
                    'return_date':     tb.availability.return_date,
                    'tourist_count':   tb.tourist_count,
                    'final_price':     tb.booking.final_price,
                    'currency':        tb.booking.currency,
                    'status':          tb.booking.status,
                    'status_label':    _STATUS_LABELS.get(tb.booking.status, tb.booking.status),
                    'operator_name':   tb.confirmed_by.full_name if tb.confirmed_by else None,
                    'confirmed_at':    tb.confirmed_at,
                    'voucher_number':  voucher_number,
                    'has_voucher':     tb.voucher_generated,
                })

            clients.append({
                'user_id':        user.id,
                'name':           user.full_name or user.phone,
                'phone':          user.phone,
                'email':          user.email or '',
                'purchase_count': len(purchases),
                'purchases':      purchases,
            })

        return Response({
            'count':   len(clients),
            'results': TourClientSerializer(clients, many=True).data,
        })


class TourBookingProcessView(APIView):
    """POST /api/crm/tours/bookings/<id>/process/ — arizani jarayonga o'tkazish."""
    permission_classes = [IsAuthenticated, CanConfirmTourBookings]

    @extend_schema(
        request   = TourBookingProcessSerializer,
        responses = {200: TourBookingCRMDetailSerializer},
        summary   = 'Arizani jarayonga o\'tkazish (CRM)',
        tags      = ['CRM Tours'],
    )
    def post(self, request, pk=None):
        serializer = TourBookingProcessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        org = _get_staff_org(request)
        try:
            TourBooking.objects.get(id=pk, package__organization=org)
        except TourBooking.DoesNotExist:
            return Response({'message': 'Bron topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            tour_booking = TourBookingService.start_processing(
                str(pk),
                operator    = request.user,
                ai_analysis = serializer.validated_data.get('ai_analysis', ''),
            )
        except ValueError as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        _log_staff_action(
            request,
            StaffActivityLog.ActionType.CONFIRM_TOUR_BOOKING,
            entity_type='TourBooking', entity_id=tour_booking.id,
            description=f'Ariza jarayonga o\'tkazildi: {tour_booking.package.title}',
        )
        return Response(TourBookingCRMDetailSerializer(tour_booking).data)


class TourAnalyticsView(APIView):
    """
    GET /api/crm/tours/analytics/
    Query params: period=daily|weekly|monthly|yearly
    """
    permission_classes = [IsAuthenticated, IsTourCompanyStaff]

    @extend_schema(
        responses  = {200: OpenApiResponse(description='Analitika ma\'lumotlari')},
        summary    = 'Tur kompaniyasi analitikasi (CRM)',
        tags       = ['CRM Tours'],
        parameters = [
            OpenApiParameter('period', str, description='daily | weekly | monthly | yearly'),
            OpenApiParameter('package_id', str, description='Konkret paket bo\'yicha (ixtiyoriy)'),
        ]
    )
    def get(self, request):
        org    = _get_staff_org(request)
        period = request.query_params.get('period', 'monthly')
        now    = timezone.now()

        # Davr chegaralari
        if period == 'daily':
            start = now.replace(hour=0, minute=0, second=0)
        elif period == 'weekly':
            start = now - timedelta(days=7)
        elif period == 'monthly':
            start = now.replace(day=1, hour=0, minute=0, second=0)
        elif period == 'yearly':
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0)
        else:
            return Response({'message': 'Noto\'g\'ri period.'}, status=status.HTTP_400_BAD_REQUEST)

        qs = Booking.objects.filter(
            tour_detail__package__organization=org,
            created_at__gte=start,
        )

        if pkg := request.query_params.get('package_id'):
            qs = qs.filter(tour_detail__package_id=pkg)

        confirmed = qs.filter(status=BookingStatus.CONFIRMED)
        stats = confirmed.aggregate(
            total_revenue   = Sum('final_price'),
            total_confirmed = Count('id'),
        )

        # Paket bo'yicha taqsimot
        top_packages = TourBooking.objects.filter(
            package__organization=org,
            booking__created_at__gte=start,
            booking__status=BookingStatus.CONFIRMED,
        ).values('package__title').annotate(
            count   = Count('id'),
            revenue = Sum('booking__final_price'),
        ).order_by('-count')[:10]

        # AI vs operator yaratilgan
        ai_count  = qs.filter(created_by_ai=True).count()
        man_count = qs.filter(created_by_ai=False).count()

        vouchers_in_period = TourBooking.objects.filter(
            package__organization=org,
            voucher_generated_at__gte=start,
        ).count()

        _log_staff_action(request, StaffActivityLog.ActionType.VIEW_ANALYTICS,
                          description=f'Analitika ko\'rildi: {period}')

        return Response({
            'period':           period,
            'from':             start.isoformat(),
            'to':               now.isoformat(),
            'total_bookings':   qs.count(),
            'total_confirmed':  stats['total_confirmed'] or 0,
            'total_rejected':   qs.filter(status=BookingStatus.CANCELLED).count(),
            'total_revenue':    str(stats['total_revenue'] or 0),
            'vouchers_issued':  vouchers_in_period,
            'ai_created':       ai_count,
            'manually_created': man_count,
            'top_packages':     list(top_packages),
        })
