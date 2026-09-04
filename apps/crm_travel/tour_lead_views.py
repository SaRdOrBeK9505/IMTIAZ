"""AI orqali kelgan tur leadlari — tur kompaniyasi CRM paneli."""

from __future__ import annotations

from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from apps.core.authentication import CRMJWTAuthentication
from apps.core.permissions import IsTourCRMUser
from apps.crm.models import TourLead
from apps.crm.serializers import TourLeadSerializer, TourLeadUpdateSerializer

_TAG = 'CRM — Travel AI Leads'


class TourLeadPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


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
            # Map UI status to model status
            status_mapping = {
                'yangi': 'new',
                'jarayonda': 'contacted',
                'tasdiqlangan': 'converted',
                'rad_etilgan': 'declined',
            }
            model_status = status_mapping.get(status_param.lower(), status_param)
            qs = qs.filter(status=model_status)
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
    pagination_class = TourLeadPagination

    @extend_schema(
        tags=[_TAG],
        summary='AI tur leadlari ro\'yxati',
        parameters=[
            OpenApiParameter('page', int, description='Sahifa raqami'),
            OpenApiParameter('page_size', int, description='Sahifa hajmi (default: 10, max: 100)'),
            OpenApiParameter('status', str, description='Filter by status: yangi, jarayonda, tasdiqlangan, rad_etilgan'),
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


class TourLeadStatsView(TourLeadQueryMixin, APIView):
    """GET /api/crm/tour/ai-leads/stats/ — Filterlar uchun sonlar"""
    
    @extend_schema(
        tags=[_TAG],
        summary='Tour lead statistikasi (filterlar uchun)',
        responses={200: OpenApiResponse(description='Statistika')},
    )
    def get(self, request):
        organization = self.request.user.organization
        if not organization:
            return Response({'message': 'Tashkilot topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        
        qs = TourLead.objects.filter(organization=organization)
        
        # AI generated count
        ai_generated_count = qs.filter(session__isnull=False).count()
        
        return Response({
            'barchasi': qs.count(),
            'yangi': qs.filter(status='new').count(),
            'jarayonda': qs.filter(status='contacted').count(),
            'tasdiqlangan': qs.filter(status='converted').count(),
            'rad_etilgan': qs.filter(status='declined').count(),
            'ai_qayta_ishlangan': ai_generated_count,
        })


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


class TourLeadConfirmedListView(TourLeadQueryMixin, generics.ListAPIView):
    """GET /api/crm/tour/ai-leads/confirmed/ — Tasdiqlangan arizalar"""
    serializer_class = TourLeadSerializer
    pagination_class = TourLeadPagination

    @extend_schema(
        tags=[_TAG],
        summary='Tasdiqlangan tur arizalari ro\'yxati',
        parameters=[
            OpenApiParameter('page', int, description='Sahifa raqami'),
            OpenApiParameter('page_size', int, description='Sahifa hajmi (default: 10, max: 100)'),
            OpenApiParameter('search', str, required=False),
        ],
        responses={200: TourLeadSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TourLead.objects.none()
        
        # Filter only confirmed (converted) leads
        qs = self.get_tour_lead_queryset().filter(status='converted')
        
        # Apply search if provided
        if q := self.request.query_params.get('search'):
            qs = qs.filter(
                models.Q(full_name__icontains=q)
                | models.Q(phone__icontains=q)
                | models.Q(note__icontains=q)
            )
        return qs
