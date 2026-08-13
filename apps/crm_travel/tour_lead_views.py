"""AI orqali kelgan tur leadlari — tur kompaniyasi CRM paneli."""

from __future__ import annotations

from django.db import models
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.authentication import CRMJWTAuthentication
from apps.core.permissions import IsTourCRMUser
from apps.crm.models import TourLead
from apps.crm.serializers import TourLeadSerializer, TourLeadUpdateSerializer

_TAG = 'CRM Travel — AI Leads'


class TourLeadQueryMixin:
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTourCRMUser]

    def get_tour_lead_queryset(self):
        organization = self.request.user.organization
        if not organization:
            return TourLead.objects.none()

        qs = TourLead.objects.filter(
            organization=organization,
        ).select_related('package', 'user').order_by('-created_at')

        if status_param := self.request.query_params.get('status'):
            qs = qs.filter(status=status_param)
        if q := self.request.query_params.get('search'):
            qs = qs.filter(
                models.Q(full_name__icontains=q)
                | models.Q(phone__icontains=q)
                | models.Q(note__icontains=q)
            )
        return qs


class TourLeadListView(TourLeadQueryMixin, generics.ListAPIView):
    """GET /api/crm/tour/ai-leads/"""
    serializer_class = TourLeadSerializer

    @extend_schema(
        tags=[_TAG],
        summary='AI tur leadlari ro\'yxati',
        parameters=[
            OpenApiParameter('status', str, description='new | sent | failed | contacted | converted | declined'),
            OpenApiParameter('search', str, required=False),
        ],
        responses={200: TourLeadSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TourLead.objects.none()
        return self.get_tour_lead_queryset()


class TourLeadDetailView(TourLeadQueryMixin, APIView):
    """PATCH /api/crm/tour/ai-leads/{id}/ — holat yangilash (qo'lda ishlov)."""

    @extend_schema(
        tags=[_TAG],
        summary='AI tur lead holatini yangilash',
        request=TourLeadUpdateSerializer,
        responses={200: TourLeadSerializer},
    )
    def patch(self, request, pk):
        try:
            lead = self.get_tour_lead_queryset().get(pk=pk)
        except TourLead.DoesNotExist:
            return Response({'message': 'Lead topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TourLeadUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        lead.status = data['status']
        update_fields = ['status', 'updated_at']
        if 'note' in data:
            lead.note = data['note']
            update_fields.append('note')
        lead.save(update_fields=update_fields)

        return Response(TourLeadSerializer(lead).data)
