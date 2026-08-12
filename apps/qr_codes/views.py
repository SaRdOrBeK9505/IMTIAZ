"""
QR Codes app views — User-facing + CRM.

User:
    GET  /api/qr/<code>/           — QR ma'lumotlari (scan)
    POST /api/qr/<code>/redeem/    — chegirmani qo'llash

CRM (asosiy: /api/crm/restaurant/qr/, legacy: /api/crm/qr/):
    GET/POST         /api/crm/qr/
    GET/PATCH/DELETE /api/crm/qr/<id>/
    POST             /api/crm/qr/<id>/regenerate/   — yangi QR PNG
    GET              /api/crm/qr/<id>/analytics/
    GET              /api/crm/qr/analytics/          — umumiy analitika
    GET              /api/crm/qr/<id>/redemptions/   — qo'llashlar tarixi
"""

import logging
from datetime import timedelta

from django.db.models import Sum, Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.authentication import CRMJWTAuthentication
from apps.crm_restaurant.helpers import log_staff_activity

from .models import QRCode, QRCodeRedemption, QRAnalyticsSummary
from .serializers import (
    QRCodePublicSerializer, QRRedeemRequestSerializer, QRRedeemResponseSerializer,
    QRStaffScanRequestSerializer, QRStaffScanResponseSerializer,
    QRStaffRedeemRequestSerializer,
    QRCodeCRMSerializer, QRCodeCRMCreateSerializer, QRCodeCRMUpdateSerializer,
    QRRedemptionCRMSerializer, QRAnalyticsSummarySerializer,
)
from .services import QRScanService, QRRedemptionService, QRGeneratorService
from .permissions import IsRestaurantQRManager
from apps.crm.models import StaffActivityLog

logger = logging.getLogger(__name__)

_QR_CRM_TAG = 'CRM Restaurant — QR Codes'


class RestaurantQRCRMMixin:
    """Restoran CRM JWT + owner/staff QR ruxsatlari."""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantQRManager]


def _get_crm_org(request):
    org = request.user.organization
    if not org:
        raise PermissionDenied('Tashkilot topilmadi.')
    return org


def _log_qr_action(request, description, entity_id=None):
    log_staff_activity(
        request.user,
        action_type=StaffActivityLog.ActionType.MANAGE_QR,
        entity_type='QRCode',
        entity_id=entity_id,
        description=description,
        request=request,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# USER-FACING
# ═══════════════════════════════════════════════════════════════════════════════

class QRCodeInfoView(APIView):
    """GET /api/qr/<code>/ — QR skanlaganda ma'lumot olish."""
    permission_classes = [AllowAny]

    @extend_schema(
        responses = {200: QRCodePublicSerializer},
        summary   = 'QR kod ma\'lumotlari',
        tags      = ['QR Codes — User'],
    )
    def get(self, request, code: str):
        info = QRScanService.validate_and_get_info(
            code, user=request.user if request.user.is_authenticated else None
        )
        if not info.get('qr_code'):
            return Response({'message': info['message']}, status=status.HTTP_404_NOT_FOUND)

        qr_data = QRCodePublicSerializer(info['qr_code']).data
        qr_data['discount_info'] = {
            'is_valid':        info['is_valid'],
            'message':         info['message'],
            'remaining_uses':  info.get('remaining_uses'),
        }
        return Response(qr_data)


class QRRedeemView(APIView):
    """POST /api/qr/<code>/redeem/ — chegirmani qo'llash."""
    permission_classes = [AllowAny]  # login bo'lmagan user ham qo'llashi mumkin

    @extend_schema(
        request   = QRRedeemRequestSerializer,
        responses = {200: QRRedeemResponseSerializer},
        summary   = 'QR kod chegirmasini qo\'llash',
        tags      = ['QR Codes — User'],
    )
    def post(self, request, code: str):
        serializer = QRRedeemRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = QRRedemptionService.redeem(
            code,
            user           = request.user if request.user.is_authenticated else None,
            order_amount   = data['order_amount'],
            service_type   = data.get('service_type', 'general'),
            booking_id     = str(data['booking_id']) if data.get('booking_id') else None,
            ip_address     = request.META.get('REMOTE_ADDR', ''),
            user_agent     = request.META.get('HTTP_USER_AGENT', ''),
            customer_name  = data.get('customer_name', ''),
            customer_phone = data.get('customer_phone', ''),
        )

        if not result['success']:
            return Response(
                {'success': False, 'message': result['message']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'success':              True,
            'message':              result['message'],
            'discount_applied':     str(result['discount_applied']),
            'final_amount':         str(result['final_amount']),
            'bonus_points_awarded': result.get('bonus_points_awarded', 0),
            'redemption_id':        str(result['redemption'].id),
        })


# ═══════════════════════════════════════════════════════════════════════════════
# CRM
# ═══════════════════════════════════════════════════════════════════════════════

class QRCodeCRMListCreateView(RestaurantQRCRMMixin, generics.ListCreateAPIView):
    """
    GET  /api/crm/restaurant/qr/ — kompaniya QR kodlari
    POST /api/crm/restaurant/qr/ — yangi QR kod yaratish
    """
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QRCodeCRMCreateSerializer
        return QRCodeCRMSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return QRCode.objects.none()
        org = _get_crm_org(self.request)
        qs  = QRCode.objects.filter(organization=org).select_related('branch')

        params = self.request.query_params
        if is_active := params.get('is_active'):
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        if qr_type := params.get('qr_type'):
            qs = qs.filter(qr_type=qr_type)
        return qs

    @extend_schema(summary='QR kodlar ro\'yxati (CRM)', tags=[_QR_CRM_TAG])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request   = QRCodeCRMCreateSerializer,
        responses = {201: QRCodeCRMSerializer},
        summary   = 'Yangi QR kod yaratish (CRM)',
        tags      = [_QR_CRM_TAG],
    )
    def post(self, request, *args, **kwargs):
        serializer = QRCodeCRMCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = _get_crm_org(request)

        qr = QRCode.objects.create(
            organization = org,
            created_by   = request.user,
            **{k: v for k, v in serializer.validated_data.items() if k != 'code'},
        )
        if custom_code := serializer.validated_data.get('code'):
            qr.code = custom_code
            qr.save(update_fields=['code', 'updated_at'])
        # QR PNG yaratish
        QRGeneratorService.generate_qr_image(qr)

        _log_qr_action(request, f'Yangi QR kod yaratildi: {qr.title}', entity_id=qr.id)
        return Response(QRCodeCRMSerializer(qr).data, status=status.HTTP_201_CREATED)


class QRCodeCRMDetailView(RestaurantQRCRMMixin, generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/crm/restaurant/qr/<id>/"""
    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return QRCodeCRMUpdateSerializer
        return QRCodeCRMSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return QRCode.objects.none()
        org = _get_crm_org(self.request)
        return QRCode.objects.filter(organization=org)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])
        _log_qr_action(self.request, f'QR kod o\'chirildi: {instance.code}', entity_id=instance.id)

    @extend_schema(summary='QR kod tafsiloti (CRM)', tags=[_QR_CRM_TAG])
    def get(self, request, *args, **kwargs): return super().get(request, *args, **kwargs)

    @extend_schema(summary='QR kodni yangilash (CRM)', tags=[_QR_CRM_TAG])
    def patch(self, request, *args, **kwargs): return super().patch(request, *args, **kwargs)

    @extend_schema(summary='QR kodni o\'chirish (soft, CRM)', tags=[_QR_CRM_TAG])
    def delete(self, request, *args, **kwargs): return super().delete(request, *args, **kwargs)


@extend_schema_view(
    post=extend_schema(
        responses={200: QRCodeCRMSerializer},
        summary='QR PNG qayta generatsiya (CRM)',
        tags=[_QR_CRM_TAG],
        request=None,
    ),
)
class QRCodeRegenerateView(RestaurantQRCRMMixin, APIView):
    """POST /api/crm/restaurant/qr/<id>/regenerate/ — yangi QR PNG yaratish."""
    def post(self, request, pk=None):
        org = _get_crm_org(request)
        try:
            qr = QRCode.objects.get(id=pk, organization=org)
        except QRCode.DoesNotExist:
            return Response({'message': 'QR kod topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        QRGeneratorService.generate_qr_image(qr)
        qr.refresh_from_db()
        _log_qr_action(request, f'QR PNG qayta yaratildi: {qr.code}', entity_id=qr.id)
        return Response(QRCodeCRMSerializer(qr).data)


# ═══════════════════════════════════════════════════════════════════════════════
# CRM — UI sahifalari (screenshot mos)
# ═══════════════════════════════════════════════════════════════════════════════

class QRScannerDashboardView(RestaurantQRCRMMixin, APIView):
    """
    GET /api/crm/restaurant/qr/scanner/
    UI: /qr/scanner — skaner sahifasi uchun boshlang'ich ma'lumotlar.
    """
    @extend_schema(
        responses={200: OpenApiResponse(description='QR skaner dashboard')},
        summary='QR skaner sahifasi (CRM — /qr/scanner)',
        tags=[_QR_CRM_TAG],
    )
    def get(self, request):
        org = _get_crm_org(request)
        applied = QRCodeRedemption.objects.filter(
            qr_code__organization=org, status='applied',
        ).select_related('qr_code', 'user').order_by('-scanned_at')

        active_bonuses = QRCode.objects.filter(organization=org, is_active=True).count()

        return Response({
            'active_bonuses':   active_bonuses,
            'recent_scans':     QRRedemptionCRMSerializer(applied[:10], many=True).data,
        })


class QRBonusesListView(RestaurantQRCRMMixin, generics.ListAPIView):
    """
    GET /api/crm/restaurant/qr/bonuses/
    UI: /qr/bonuses — alias for QR kodlar ro'yxati.
    """
    serializer_class   = QRCodeCRMSerializer
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return QRCode.objects.none()
        org = _get_crm_org(self.request)
        qs  = QRCode.objects.filter(organization=org).select_related('branch')
        if is_active := self.request.query_params.get('is_active'):
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        return qs

    @extend_schema(summary='Bonuslar ro\'yxati (CRM — /qr/bonuses)', tags=[_QR_CRM_TAG])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class QRAllRedemptionsListView(RestaurantQRCRMMixin, generics.ListAPIView):
    """GET /api/crm/restaurant/qr/redemptions/ — barcha so'nggi skanlar (org bo'yicha)."""
    serializer_class   = QRRedemptionCRMSerializer
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return QRCodeRedemption.objects.none()
        org = _get_crm_org(self.request)
        qs = QRCodeRedemption.objects.filter(
            qr_code__organization=org,
            status='applied',
        ).select_related('qr_code', 'user').order_by('-scanned_at')

        if limit := self.request.query_params.get('limit'):
            try:
                return qs[:min(int(limit), 100)]
            except ValueError:
                pass
        return qs[:20]

    @extend_schema(
        summary='Barcha QR qo\'llashlar (CRM)',
        tags=[_QR_CRM_TAG],
        operation_id='crm_restaurant_qr_all_redemptions_list',
        parameters=[OpenApiParameter('limit', int, description='Natijalar soni (default: 20, max: 100)')],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class QRStaffScanView(RestaurantQRCRMMixin, APIView):
    """POST /api/crm/restaurant/qr/scan/ — CRM xodimi QR kodni tekshiradi."""
    @extend_schema(
        request   = QRStaffScanRequestSerializer,
        responses = {200: QRStaffScanResponseSerializer},
        summary   = 'QR kodni skanerlash (CRM)',
        tags      = [_QR_CRM_TAG],
    )
    def post(self, request):
        serializer = QRStaffScanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        info = QRScanService.validate_and_get_info(
            data['code'],
            order_amount=data.get('order_amount', 0),
        )

        if not info.get('qr_code'):
            return Response({
                'is_valid': False,
                'message':  info['message'],
            }, status=status.HTTP_404_NOT_FOUND)

        qr = info['qr_code']
        org = _get_crm_org(request)
        if qr.organization_id != org.id:
            return Response({'is_valid': False, 'message': 'QR kod sizning tashkilotingizga tegishli emas.'},
                            status=status.HTTP_403_FORBIDDEN)

        return Response({
            'is_valid':         info['is_valid'],
            'message':          info['message'],
            'code':             qr.code,
            'title':            qr.title,
            'description':      qr.description,
            'qr_type':          qr.qr_type,
            'discount_value':   str(qr.discount_value),
            'discount_preview': str(info['discount_amount']),
            'remaining_uses':   info.get('remaining_uses'),
        })


class QRStaffRedeemView(RestaurantQRCRMMixin, APIView):
    """POST /api/crm/restaurant/qr/redeem/ — CRM xodimi chegirmani qo'llaydi."""
    @extend_schema(
        request   = QRStaffRedeemRequestSerializer,
        responses = {200: QRRedeemResponseSerializer},
        summary   = 'Chegirmani qo\'llash (CRM skaner)',
        tags      = [_QR_CRM_TAG],
    )
    def post(self, request):
        serializer = QRStaffRedeemRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        org = _get_crm_org(request)
        try:
            qr = QRCode.objects.get(code=data['code'], organization=org)
        except QRCode.DoesNotExist:
            return Response({'message': 'QR kod topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        result = QRRedemptionService.redeem(
            qr.code,
            order_amount   = data['order_amount'],
            service_type   = data.get('service_type', 'restaurant'),
            booking_id     = str(data['booking_id']) if data.get('booking_id') else None,
            ip_address     = request.META.get('REMOTE_ADDR', ''),
            user_agent     = request.META.get('HTTP_USER_AGENT', ''),
            customer_name  = data.get('customer_name', ''),
            customer_phone = data.get('customer_phone', ''),
            staff_user     = request.user,
        )

        if not result['success']:
            return Response({'success': False, 'message': result['message']},
                            status=status.HTTP_400_BAD_REQUEST)

        _log_qr_action(
            request,
            f'Chegirma qo\'llandi: {qr.title} — {result["discount_applied"]} UZS',
            entity_id=qr.id,
        )

        redemption_data = QRRedemptionCRMSerializer(result['redemption']).data
        return Response({
            'success':              True,
            'message':              result['message'],
            'discount_applied':     str(result['discount_applied']),
            'final_amount':         str(result['final_amount']),
            'bonus_points_awarded': result.get('bonus_points_awarded', 0),
            'redemption_id':        str(result['redemption'].id),
            'redemption':           redemption_data,
        })


class QRCodeRedemptionListView(RestaurantQRCRMMixin, generics.ListAPIView):
    """GET /api/crm/restaurant/qr/<id>/redemptions/ — qo'llashlar tarixi."""
    serializer_class   = QRRedemptionCRMSerializer
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return QRCodeRedemption.objects.none()
        org = _get_crm_org(self.request)
        return QRCodeRedemption.objects.filter(
            qr_code_id=self.kwargs['pk'],
            qr_code__organization=org,
        ).select_related('user').order_by('-scanned_at')

    @extend_schema(
        summary='QR qo\'llashlar tarixi (CRM)',
        tags=[_QR_CRM_TAG],
        operation_id='crm_restaurant_qr_code_redemptions_list',
    )
    def get(self, request, *args, **kwargs): return super().get(request, *args, **kwargs)


class QRCodeAnalyticsView(RestaurantQRCRMMixin, APIView):
    """GET /api/crm/restaurant/qr/<id>/analytics/ — bitta QR kod statistikasi."""
    @extend_schema(
        responses  = {200: QRAnalyticsSummarySerializer(many=True)},
        summary    = 'QR kod analitikasi (CRM)',
        tags       = [_QR_CRM_TAG],
        parameters = [
            OpenApiParameter('days', int, description='Oxirgi N kun (default: 30)'),
        ]
    )
    def get(self, request, pk=None):
        org = _get_crm_org(request)
        try:
            qr = QRCode.objects.get(id=pk, organization=org)
        except QRCode.DoesNotExist:
            return Response({'message': 'QR topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        days     = min(int(request.query_params.get('days', 30)), 365)
        from_date = timezone.now().date() - timedelta(days=days)

        analytics = QRAnalyticsSummary.objects.filter(
            qr_code=qr, date__gte=from_date
        ).order_by('date')

        # Umumiy jami
        totals = analytics.aggregate(
            total_scans    = Sum('scan_count'),
            total_applied  = Sum('apply_count'),
            total_discount = Sum('total_discount_given'),
            total_revenue  = Sum('total_revenue_generated'),
        )

        return Response({
            'qr_code':        {'id': str(qr.id), 'code': qr.code, 'title': qr.title},
            'period_days':    days,
            'totals':         totals,
            'daily_data':     QRAnalyticsSummarySerializer(analytics, many=True).data,
            'total_used_count': qr.total_used_count,
        })


class QRAllAnalyticsView(RestaurantQRCRMMixin, APIView):
    """GET /api/crm/restaurant/qr/analytics/ — barcha QR kodlar umumiy statistikasi."""
    @extend_schema(
        responses  = {200: OpenApiResponse(description='Umumiy QR analitika')},
        summary    = 'Barcha QR kodlar analitikasi (CRM)',
        tags       = [_QR_CRM_TAG],
        parameters = [
            OpenApiParameter('period', str, description='daily | weekly | monthly'),
        ]
    )
    def get(self, request):
        org    = _get_crm_org(request)
        period = request.query_params.get('period', 'monthly')
        now    = timezone.now()

        if period == 'daily':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'weekly':
            start = now - timedelta(days=7)
        else:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        qr_codes = QRCode.objects.filter(organization=org)
        applied_redemptions = QRCodeRedemption.objects.filter(
            qr_code__organization=org,
            status='applied',
        )
        period_redemptions = applied_redemptions.filter(scanned_at__gte=start)

        totals = period_redemptions.aggregate(
            total_scans    = Count('id'),
            total_applied  = Count('id'),
            total_discount = Sum('discount_applied'),
            total_revenue  = Sum('final_amount'),
        )
        total_scans = totals['total_scans'] or 0
        total_discount = float(totals['total_discount'] or 0)
        avg_discount = round(total_discount / total_scans, 2) if total_scans else 0

        # Kunlik skanlar — oxirgi 7 kun
        daily_scans = []
        for i in range(6, -1, -1):
            day = (now - timedelta(days=i)).date()
            count = applied_redemptions.filter(scanned_at__date=day).count()
            daily_scans.append({'date': day.isoformat(), 'count': count})

        # Eng ko'p foydalanilgan bonuslar (barcha vaqt)
        top_bonuses = list(
            qr_codes.annotate(
                scans=Count('redemptions', filter=Q(redemptions__status='applied'))
            ).order_by('-scans').values('id', 'title', 'code', 'scans', 'qr_type', 'discount_value')[:5]
        )

        top_qr = qr_codes.annotate(
            uses=Count('redemptions', filter=Q(
                redemptions__status='applied',
                redemptions__scanned_at__gte=start,
            ))
        ).order_by('-uses')[:5].values('title', 'code', 'uses')

        _log_qr_action(request, 'QR umumiy analitika ko\'rildi')

        return Response({
            'period':           period,
            'from':             start.isoformat(),
            'total_qr_codes':   qr_codes.count(),
            'active_qr':        qr_codes.filter(is_active=True).count(),
            # UI kartochkalari (/qr/analytics)
            'summary': {
                'total_scans':      total_scans,
                'total_discount':   str(totals['total_discount'] or 0),
                'avg_discount':     avg_discount,
            },
            'totals': {
                **totals,
                'avg_discount': avg_discount,
            },
            'daily_scans':      daily_scans,
            'top_bonuses':      top_bonuses,
            'top_qr_codes':     list(top_qr),
            'all_scans': QRRedemptionCRMSerializer(
                applied_redemptions.select_related('qr_code', 'user').order_by('-scanned_at'),
                many=True,
            ).data,
            'recent_redemptions': QRRedemptionCRMSerializer(
                applied_redemptions.select_related('qr_code', 'user').order_by('-scanned_at')[:10],
                many=True,
            ).data,
        })
