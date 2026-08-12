"""CRM lead pipeline API."""

from __future__ import annotations

from django.db import models
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.authentication import CRMJWTAuthentication
from apps.core.openapi_schemas import ErrorResponseSerializer
from apps.core.permissions import IsCRMUser
from apps.crm_core.mixins import BranchScopedMixin
from apps.crm_core.models import Lead
from apps.crm_core.serializers import LeadListSerializer, LeadUpdateSerializer
from apps.users.models import UserRole

_LEAD_TAG = 'CRM — Leads'
_KANBAN_LIMIT = 30


class LeadQueryMixin(BranchScopedMixin):
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsCRMUser]

    def get_lead_vertical(self) -> str:
        user = self.request.user
        if user.role in (UserRole.OWNER_RESTAURANT, UserRole.RESTAURANT_STAFF):
            return Lead.Vertical.RESTAURANT
        return Lead.Vertical.TRAVEL

    def get_lead_queryset(self):
        organization = self.request.user.organization
        if not organization:
            return Lead.objects.none()

        qs = Lead.objects.filter(
            organization=organization,
            vertical=self.get_lead_vertical(),
        ).select_related('branch', 'booking', 'assigned_to')

        if self.request.user.role in (UserRole.RESTAURANT_STAFF, UserRole.TOUR_STAFF):
            branch = self.get_user_branch()
            if branch:
                qs = qs.filter(branch=branch)

        if stage := self.request.query_params.get('stage'):
            qs = qs.filter(stage=stage)
        if branch_id := self.request.query_params.get('branch_id'):
            qs = qs.filter(branch_id=branch_id)
        if q := self.request.query_params.get('search'):
            qs = qs.filter(
                models.Q(customer_name__icontains=q)
                | models.Q(customer_phone__icontains=q)
                | models.Q(title__icontains=q)
            )
        return qs.order_by('-created_at')


class LeadListView(LeadQueryMixin, generics.ListAPIView):
    """GET /api/crm/{restaurant|tour}/leads/"""
    serializer_class = LeadListSerializer

    @extend_schema(
        tags=[_LEAD_TAG],
        summary='Leadlar ro\'yxati',
        parameters=[
            OpenApiParameter('stage', str, description='new | contacted | qualified | won | lost'),
            OpenApiParameter('branch_id', str, required=False),
            OpenApiParameter('search', str, required=False),
        ],
        responses={200: LeadListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Lead.objects.none()
        return self.get_lead_queryset()


class LeadDetailView(LeadQueryMixin, generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/crm/{restaurant|tour}/leads/<id>/"""
    lookup_url_kwarg = 'pk'

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return LeadUpdateSerializer
        return LeadListSerializer

    @extend_schema(tags=[_LEAD_TAG], summary='Lead tafsiloti', responses={200: LeadListSerializer})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=[_LEAD_TAG],
        summary='Lead yangilash (bosqich, izoh, mas\'ul)',
        request=LeadUpdateSerializer,
        responses={200: LeadListSerializer},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Lead.objects.none()
        return self.get_lead_queryset()

    def perform_update(self, serializer):
        stage = serializer.validated_data.get('stage')
        extra = {}
        if stage in (Lead.Stage.WON, Lead.Stage.LOST):
            extra['closed_at'] = timezone.now()
        elif stage:
            extra['closed_at'] = None
        serializer.save(**extra)


class LeadKanbanView(LeadQueryMixin, APIView):
    """GET /api/crm/{restaurant|tour}/leads/kanban/"""

    @extend_schema(
        tags=[_LEAD_TAG],
        summary='Lead kanban (bosqichlar bo\'yicha)',
        parameters=[
            OpenApiParameter('branch_id', str, required=False),
        ],
        responses={200: OpenApiResponse(description='Kanban')},
    )
    def get(self, request):
        qs = self.get_lead_queryset()
        stages = []
        total = 0
        for stage_value, stage_label in Lead.Stage.choices:
            stage_qs = qs.filter(stage=stage_value)[:_KANBAN_LIMIT]
            count = qs.filter(stage=stage_value).count()
            total += count
            stages.append({
                'stage': stage_value,
                'label': stage_label,
                'count': count,
                'leads': LeadListSerializer(stage_qs, many=True).data,
            })
        return Response({'stages': stages, 'total': total})


class LeadStatsView(LeadQueryMixin, APIView):
    """GET /api/crm/{restaurant|tour}/leads/stats/"""

    @extend_schema(
        tags=[_LEAD_TAG],
        summary='Lead statistikasi',
        responses={200: OpenApiResponse(description='Bosqichlar bo\'yicha sonlar')},
    )
    def get(self, request):
        qs = self.get_lead_queryset()
        stats = {stage: qs.filter(stage=stage).count() for stage, _ in Lead.Stage.choices}
        return Response({
            'total': qs.count(),
            'by_stage': stats,
        })
