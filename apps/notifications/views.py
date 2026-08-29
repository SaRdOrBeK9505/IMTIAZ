"""
Notifications app views.

GET  /api/notifications/          — foydalanuvchining bildirishnomalar ro'yxati
POST /api/notifications/{id}/read/ — o'qildi deb belgilash
POST /api/notifications/read-all/  — barchasini o'qildi
"""

from __future__ import annotations

import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer
from django.utils import timezone

logger = logging.getLogger(__name__)


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

        if self.request.query_params.get('unread') == 'true':
            qs = qs.exclude(status=Notification.Status.READ)

        return qs[:50]

    @extend_schema(
        tags=['Notifications'],
        summary='Bildirishnomalar ro\'yxati',
        description='Oxirgi 50 ta yozuv. `?unread=true` — faqat o\'qilmaganlar.',
        parameters=[
            OpenApiParameter('unread', str, description='true — faqat o\'qilmaganlar'),
        ],
        responses={200: NotificationSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


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


class TelegramWebhookView(APIView):
    """
    POST /api/notifications/telegram/webhook/

    Telegram Bot API update'larini qabul qiladi.
    /start va inline tugmalar bot_handlers orqali ishlaydi.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=['Notifications'],
        summary='Telegram bot webhook',
        description='Telegram Bot API update qabul qiladi. X-TELEGRAM-BOT-API-SECRET-TOKEN tekshiriladi.',
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiResponse(description='OK')},
        exclude=True,
    )
    def post(self, request):
        secret = settings.TELEGRAM_BOT_SECRET
        if secret:
            header = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
            if header != secret:
                logger.warning('Telegram webhook: noto\'g\'ri secret token')
                return Response(status=status.HTTP_403_FORBIDDEN)

        update = request.data
        if not isinstance(update, dict):
            return Response({'ok': True})

        # MUHIM: handle_update'ni bu yerda SINXRON chaqirmaymiz.
        # AI javobi + streaming bir necha soniya cho'zilishi mumkin, va agar
        # Telegram webhook javobini vaqtida ololmasa, update'ni QAYTA yuboradi —
        # bu xabarlarning "takrorlanib" ko'rinishiga sabab bo'ladi. Shuning uchun
        # og'ir ishni Celery navbatiga topshirib, darhol 200 OK qaytaramiz.
        try:
            from .tasks import process_telegram_update
            process_telegram_update.delay(update)
        except Exception:
            logger.exception('Telegram update navbatga qo\'yishda xato')

        return Response({'ok': True})
