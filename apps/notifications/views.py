"""
Notifications app views.

GET  /api/notifications/          — foydalanuvchining bildirishnomalar ro'yxati
POST /api/notifications/{id}/read/ — o'qildi deb belgilash
POST /api/notifications/read-all/  — barchasini o'qildi
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer
from django.utils import timezone


class NotificationListView(generics.ListAPIView):
    """GET /api/notifications/"""
    permission_classes = [IsAuthenticated]
    serializer_class   = NotificationSerializer
    queryset           = Notification.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        qs = Notification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')

        # ?unread=true — faqat o'qilmaganlar
        if self.request.query_params.get('unread') == 'true':
            qs = qs.exclude(status=Notification.Status.READ)

        return qs[:50]


class NotificationReadView(APIView):
    """POST /api/notifications/{id}/read/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description="O'qildi")},
        summary="Bildirishnomani o'qildi deb belgilash",
        tags=['Notifications'],
    )
    def post(self, request, pk):
        updated = Notification.objects.filter(
            id=pk, user=request.user
        ).update(
            status=Notification.Status.READ,
            read_at=timezone.now(),
        )
        if not updated:
            return Response(
                {'message': 'Topilmadi'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({'success': True})


class NotificationReadAllView(APIView):
    """POST /api/notifications/read-all/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description='Barchasi o\'qildi')},
        summary='Barcha bildirishnomalarni o\'qildi deb belgilash',
        tags=['Notifications'],
    )
    def post(self, request):
        count = Notification.objects.filter(
            user=request.user,
        ).exclude(
            status=Notification.Status.READ,
        ).update(
            status=Notification.Status.READ,
            read_at=timezone.now(),
        )
        return Response({'success': True, 'updated': count})
