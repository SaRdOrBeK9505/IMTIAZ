"""Restoran analytics — owner va analytics ruxsati bor staff."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.authentication import CRMJWTAuthentication
from apps.core.permissions import IsRestaurantCRMUser
from apps.crm_core.exports import (
    build_restaurant_analytics_summary,
    export_restaurant_bookings_csv,
    export_restaurant_bookings_xlsx,
)

from .helpers import can_view_analytics, resolve_branch

_ANALYTICS_TAG = 'CRM Restaurant — Analytics'


class RestaurantAnalyticsView(APIView):
    """
    GET /api/crm/restaurant/analytics/
    Filial yoki butun kompaniya bo'yicha bron statistikasi.
    """
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    @extend_schema(
        tags=[_ANALYTICS_TAG],
        summary='Restoran analytics',
        parameters=[
            OpenApiParameter('period', str, description='daily|weekly|monthly'),
            OpenApiParameter('branch_id', str, required=False),
        ],
        responses={200: OpenApiResponse(description='Statistika')},
    )
    def get(self, request):
        if not can_view_analytics(request.user):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)

        organization = request.user.organization
        if not organization:
            return Response({'message': 'Tashkilot topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        period = request.query_params.get('period', 'daily')
        branch = resolve_branch(request.user, request.query_params.get('branch_id'))
        summary = build_restaurant_analytics_summary(organization, period=period, branch=branch)
        return Response({
            **summary,
            'branch_id': str(branch.id) if branch else None,
        })


class RestaurantAnalyticsExportView(APIView):
    """GET /api/crm/restaurant/analytics/export/?format=csv|xlsx"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    @extend_schema(
        tags=[_ANALYTICS_TAG],
        summary='Restoran hisobotini yuklab olish (CSV/Excel)',
        parameters=[
            OpenApiParameter('file_format', str, description='csv yoki xlsx'),
            OpenApiParameter('period', str, description='daily|weekly|monthly'),
            OpenApiParameter('branch_id', str, required=False),
        ],
        responses={200: OpenApiResponse(description='Fayl')},
    )
    def get(self, request):
        if not can_view_analytics(request.user):
            return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)

        organization = request.user.organization
        if not organization:
            return Response({'message': 'Tashkilot topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        period = request.query_params.get('period', 'daily')
        branch = resolve_branch(request.user, request.query_params.get('branch_id'))
        fmt = request.query_params.get('file_format', 'csv').lower()

        try:
            if fmt == 'xlsx':
                return export_restaurant_bookings_xlsx(organization, period=period, branch=branch)
            return export_restaurant_bookings_csv(organization, period=period, branch=branch)
        except ImportError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
