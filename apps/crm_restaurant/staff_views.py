"""Restoran CRM — xodim statistikasi va faoliyat jurnali (owner + staff)."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.authentication import CRMJWTAuthentication
from apps.core.permissions import IsRestaurantCRMUser
from apps.crm.models import BranchStaff, StaffActivityLog, StaffPerformanceSummary
from apps.crm.serializers import (
    StaffActivityLogSerializer,
    StaffLeaderboardSerializer,
    StaffPerformanceSummarySerializer,
)

from .helpers import can_manage_staff, can_view_analytics, get_staff_profile, is_restaurant_owner

_STAFF_TAG = 'CRM Restaurant — Staff Analytics'


class RestaurantStaffListView(generics.ListAPIView):
    """GET /api/crm/restaurant/staff/members/ — kompaniya xodimlari."""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]
    serializer_class = StaffLeaderboardSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return BranchStaff.objects.none()
        if not (can_manage_staff(self.request.user) or can_view_analytics(self.request.user)):
            return BranchStaff.objects.none()
        organization = self.request.user.organization
        if not organization:
            return BranchStaff.objects.none()
        return BranchStaff.objects.filter(
            branch__organization=organization,
            is_active=True,
        ).select_related('user', 'branch')

    @extend_schema(tags=[_STAFF_TAG], summary='Kompaniya xodimlari ro\'yxati')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


@extend_schema_view(
    get=extend_schema(
        tags=[_STAFF_TAG],
        summary='Mening statistikam (staff)',
        parameters=[OpenApiParameter('period', str, description='daily|weekly|monthly')],
        responses={200: OpenApiResponse(description='Xodim statistikasi')},
    ),
)
class RestaurantMyStatsView(APIView):
    """GET /api/crm/restaurant/staff/me/stats/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    def get(self, request):
        profile = get_staff_profile(request.user)
        if not profile:
            return Response(
                {'message': 'Faqat restoran xodimi o\'z statistikasini ko\'ra oladi.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        period = request.query_params.get('period', 'monthly')
        summaries = StaffPerformanceSummary.objects.filter(
            staff=profile, period_type=period,
        ).order_by('-period_start')[:12]

        today_logs = StaffActivityLog.objects.filter(
            staff=profile, created_at__date=timezone.now().date(),
        )
        return Response({
            'staff_info': {
                'id': str(profile.id),
                'name': profile.user.full_name,
                'role': profile.role,
                'branch': profile.branch.name,
            },
            'today': {
                'bookings_confirmed': today_logs.filter(
                    action_type=StaffActivityLog.ActionType.CONFIRM_TABLE_BOOKING,
                ).count(),
                'bookings_cancelled': today_logs.filter(
                    action_type=StaffActivityLog.ActionType.CANCEL_TABLE_BOOKING,
                ).count(),
                'table_updates': today_logs.filter(
                    action_type=StaffActivityLog.ActionType.UPDATE_TABLE_STATUS,
                ).count(),
                'total_actions': today_logs.count(),
            },
            'history': StaffPerformanceSummarySerializer(summaries, many=True).data,
        })


@extend_schema_view(
    get=extend_schema(
        tags=[_STAFF_TAG],
        summary='Xodim statistikasi (owner)',
        parameters=[OpenApiParameter('period', str, description='daily|weekly|monthly')],
        responses={200: OpenApiResponse(description='Xodim statistikasi')},
    ),
)
class RestaurantStaffStatsView(APIView):
    """GET /api/crm/restaurant/staff/<id>/stats/ — owner uchun xodim statistikasi."""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    def get(self, request, pk):
        if not (can_manage_staff(request.user) or can_view_analytics(request.user)):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)

        organization = request.user.organization
        try:
            target = BranchStaff.objects.select_related('user', 'branch').get(
                id=pk,
                branch__organization=organization,
            )
        except BranchStaff.DoesNotExist:
            return Response({'message': 'Xodim topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        period = request.query_params.get('period', 'monthly')
        summaries = StaffPerformanceSummary.objects.filter(
            staff=target, period_type=period,
        ).order_by('-period_start')[:12]

        from_date = timezone.now() - timedelta(days=30)
        activities = StaffActivityLog.objects.filter(
            staff=target, created_at__gte=from_date,
        ).values('action_type').annotate(count=Count('id')).order_by('-count')

        return Response({
            'staff_info': {
                'id': str(target.id),
                'name': target.user.full_name,
                'phone': target.user.phone,
                'role': target.role,
                'branch': target.branch.name,
                'permissions': target.permissions,
            },
            'activity_breakdown': list(activities),
            'history': StaffPerformanceSummarySerializer(summaries, many=True).data,
        })


@extend_schema_view(
    get=extend_schema(
        tags=[_STAFF_TAG],
        summary='Xodimlar reytingi (restoran metrikalari)',
        parameters=[OpenApiParameter('period', str, description='daily|weekly|monthly')],
        responses={200: StaffLeaderboardSerializer(many=True)},
    ),
)
class RestaurantStaffLeaderboardView(APIView):
    """GET /api/crm/restaurant/staff/leaderboard/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    def get(self, request):
        if not (can_manage_staff(request.user) or can_view_analytics(request.user)):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)

        organization = request.user.organization
        period = request.query_params.get('period', 'monthly')
        now = timezone.now()

        if period == 'daily':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'weekly':
            start = now - timedelta(days=7)
        else:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        staff_list = BranchStaff.objects.filter(
            branch__organization=organization,
            is_active=True,
        ).select_related('user', 'branch')

        leaderboard = []
        for s in staff_list:
            logs = StaffActivityLog.objects.filter(staff=s, created_at__gte=start)
            leaderboard.append({
                'staff_id': str(s.id),
                'name': s.user.full_name,
                'branch': s.branch.name,
                'role': s.role,
                'bookings_confirmed': logs.filter(
                    action_type=StaffActivityLog.ActionType.CONFIRM_TABLE_BOOKING,
                ).count(),
                'bookings_cancelled': logs.filter(
                    action_type=StaffActivityLog.ActionType.CANCEL_TABLE_BOOKING,
                ).count(),
                'table_updates': logs.filter(
                    action_type=StaffActivityLog.ActionType.UPDATE_TABLE_STATUS,
                ).count(),
                'total_actions': logs.count(),
                'last_active': logs.order_by('-created_at').values_list(
                    'created_at', flat=True,
                ).first(),
            })

        leaderboard.sort(key=lambda x: x['bookings_confirmed'], reverse=True)
        return Response({'period': period, 'leaderboard': leaderboard})


class RestaurantStaffActivityView(generics.ListAPIView):
    """GET /api/crm/restaurant/staff/activity/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]
    serializer_class = StaffActivityLogSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return StaffActivityLog.objects.none()

        organization = self.request.user.organization
        if not organization:
            return StaffActivityLog.objects.none()

        if is_restaurant_owner(self.request.user):
            pass
        elif can_view_analytics(self.request.user) or can_manage_staff(self.request.user):
            pass
        else:
            profile = get_staff_profile(self.request.user)
            if not profile:
                return StaffActivityLog.objects.none()
            return StaffActivityLog.objects.filter(staff=profile).select_related(
                'staff__user',
            ).order_by('-created_at')

        qs = StaffActivityLog.objects.filter(
            staff__branch__organization=organization,
        ).select_related('staff__user').order_by('-created_at')

        if staff_id := self.request.query_params.get('staff_id'):
            qs = qs.filter(staff_id=staff_id)
        if action := self.request.query_params.get('action_type'):
            qs = qs.filter(action_type=action)
        return qs

    @extend_schema(
        tags=[_STAFF_TAG],
        summary='Xodimlar faoliyat jurnali',
        parameters=[
            OpenApiParameter('staff_id', str, required=False),
            OpenApiParameter('action_type', str, required=False),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
