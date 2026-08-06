"""
Integrations app views — tashqi API loglari (faqat admin).
"""

from rest_framework import generics
from rest_framework.permissions import IsAdminUser

from .models import ExternalProviderLog
from .serializers import ExternalProviderLogSerializer


class ExternalProviderLogListView(generics.ListAPIView):
    """GET /api/integrations/logs/ — faqat admin"""
    permission_classes = [IsAdminUser]
    serializer_class   = ExternalProviderLogSerializer
    queryset           = ExternalProviderLog.objects.all().order_by('-created_at')[:200]
    filterset_fields   = ['provider', 'method', 'is_success']
