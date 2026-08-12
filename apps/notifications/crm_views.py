"""
CRM bildirishnomalar — CRM JWT bilan kirish.

GET  /api/crm/notifications/          — CRM foydalanuvchi bildirishnomalari
POST /api/crm/notifications/{id}/read/  — o'qildi
POST /api/crm/notifications/read-all/ — barchasini o'qildi
"""

from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.authentication import CRMJWTAuthentication
from apps.core.permissions import IsCRMUser

from .models import Notification
from .serializers import NotificationSerializer


class CRMNotificationListView(generics.ListAPIView):
    """GET /api/crm/notifications/ — CRM panel bildirishnomalari."""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsCRMUser]
    serializer_class = NotificationSerializer
    queryset = Notification.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()

        qs = Notification.objects.filter(
            user=self.request.user,
            channel=Notification.Channel.IN_APP,
        ).order_by('-created_at')

        if self.request.query_params.get('unread') == 'true':
            qs = qs.exclude(status=Notification.Status.READ)

        ntype = self.request.query_params.get('type')
        if ntype:
            qs = qs.filter(notification_type=ntype)

        return qs[:100]

    @extend_schema(
        tags=['CRM — Notifications'],
        summary='CRM bildirishnomalar ro\'yxati',
        description=(
            'Owner va xodimlar uchun in-app bildirishnomalar. '
            '`?unread=true` — faqat o\'qilmaganlar. '
            '`?type=new_lead` — faqat yangi leadlar.'
        ),
        parameters=[
            OpenApiParameter('unread', str, description='true — faqat o\'qilmaganlar'),
            OpenApiParameter('type', str, description='Masalan: new_lead'),
        ],
        responses={200: NotificationSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CRMNotificationReadView(APIView):
    """POST /api/crm/notifications/{id}/read/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsCRMUser]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description="O'qildi")},
        summary="CRM bildirishnomani o'qildi deb belgilash",
        tags=['CRM — Notifications'],
    )
    def post(self, request, pk):
        updated = Notification.objects.filter(
            id=pk,
            user=request.user,
            channel=Notification.Channel.IN_APP,
        ).update(
            status=Notification.Status.READ,
            read_at=timezone.now(),
        )
        if not updated:
            return Response({'message': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'success': True})


class CRMNotificationReadAllView(APIView):
    """POST /api/crm/notifications/read-all/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsCRMUser]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description='Barchasi o\'qildi')},
        summary='Barcha CRM bildirishnomalarni o\'qildi deb belgilash',
        tags=['CRM — Notifications'],
    )
    def post(self, request):
        count = Notification.objects.filter(
            user=request.user,
            channel=Notification.Channel.IN_APP,
        ).exclude(
            status=Notification.Status.READ,
        ).update(
            status=Notification.Status.READ,
            read_at=timezone.now(),
        )
        return Response({'success': True, 'updated': count})
