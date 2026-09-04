"""
Integrations app views — tashqi API loglari (faqat admin).
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAdminUser

from apps.core.openapi_schemas import ErrorResponseSerializer

from .models import ExternalProviderLog
from .serializers import ExternalProviderLogSerializer

_TAG = 'Admin — Integrations'


class ExternalProviderLogListView(generics.ListAPIView):
    """GET /api/integrations/logs/ — faqat admin"""
    permission_classes = [IsAdminUser]
    serializer_class   = ExternalProviderLogSerializer
    queryset           = ExternalProviderLog.objects.all().order_by('-created_at')[:200]
    filterset_fields   = ['provider', 'method', 'is_success']

    @extend_schema(
        tags=[_TAG],
        summary='Tashqi provayder API loglari',
        description='Aviakassa, Bookhara va boshqa integratsiya so\'rovlari jurnali. **Admin token talab qilinadi.**',
        parameters=[
            OpenApiParameter('provider', str, description='aviakassa|bookhara|...'),
            OpenApiParameter('method', str, description='GET|POST|...'),
            OpenApiParameter('is_success', bool, description='Muvaffaqiyatli so\'rovlar'),
        ],
        responses={200: ExternalProviderLogSerializer(many=True), 403: ErrorResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
