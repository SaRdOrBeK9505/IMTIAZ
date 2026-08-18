"""AI Assistant views."""

from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core.openapi_schemas import ErrorResponseSerializer
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import json
import logging
from django.http import StreamingHttpResponse

from apps.core.permissions import HasApprovedMembership
from .confirmation import confirm_pending_action, reject_pending_action, ConfirmationError
from .i18n import resolve_language, t
from .models import ConversationSession, AIActionLog
from .serializers import (
    ChatMessageSerializer,
    ChatResponseSerializer,
    SessionBootstrapSerializer,
    ConversationSessionSerializer,
    SessionListSerializer,
    AIActionLogSerializer,
)
from .services import AIAssistantService

from rest_framework.renderers import BaseRenderer, JSONRenderer

class EventStreamRenderer(BaseRenderer):
    media_type = 'text/event-stream'
    format = 'txt'
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data

def get_ai_service() -> AIAssistantService:
    return AIAssistantService()


view_logger = logging.getLogger(__name__)


class ChatView(APIView):
    """POST /api/ai/chat/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChatMessageSerializer,
        responses={
            200: ChatResponseSerializer,
            400: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
        },
        summary='AI bilan suhbat',
        description=(
            'Gemini function-calling orqali bron qidiruv va booking takliflari.\n\n'
            '`requires_confirmation=true` bo\'lsa — Booking **YARATILMADI**.\n'
            '`pending_action_id` ni olib alohida tasdiqlang:\n'
            '`POST /api/ai/actions/{pending_action_id}/confirm/`'
        ),
        tags=['AI Assistant'],
    )
    def post(self, request):
        # NON-STREAM so'rov — monitoring uchun WARNING
        # Bu endpoint odatda faqat zaxira/debug rejimida ishlatilishi kerak.
        # Production'da ChatStreamView ishlatilsin. Bu log orqali
        # "15:07:06 dagi anomaliya" kabi holatlar darhol aniqlanadi.
        view_logger.warning(
            'NON-STREAM AI so\'rov qabul qilindi: user_id=%s request_id=%s — '
            'ChatStreamView ishlatilishini tekshiring',
            getattr(request.user, 'id', '?'),
            getattr(request, 'request_id', ''),
        )
        serializer = ChatMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = get_ai_service().chat(
            user=request.user,
            message=serializer.validated_data['message'],
            session_id=(
                str(serializer.validated_data['session_id'])
                if serializer.validated_data.get('session_id') else None
            ),
            request_id=getattr(request, 'request_id', ''),
        )
        return Response({'success': True, **result})


class ChatStreamView(APIView):
    """
    POST /api/ai/chat/stream/

    Server-Sent Events (SSE) orqali AI javobini oqim sifatida uzatadi.
    Frontend `fetch()` + `ReadableStream` yoki `EventSource` (GET bilan
    ishlaydi, shuning uchun bu yerda fetch+stream tavsiya etiladi) orqali
    qabul qiladi.

    Event formatlari:
        data: {"type": "chunk", "text": "..."}
        data: {"type": "tool_processing"}
        data: {"type": "done", "content": "...", "session_id": "...", ...}
        data: {"type": "error", "message": "..."}
    """
    permission_classes = [IsAuthenticated]
    renderer_classes = [EventStreamRenderer, JSONRenderer]

    @extend_schema(exclude=True)  # streaming javobni OpenAPI avtomatik hujjatlay olmaydi
    def post(self, request):
        serializer = ChatMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.validated_data['message']
        session_id = (
            str(serializer.validated_data['session_id'])
            if serializer.validated_data.get('session_id') else None
        )
        request_id = getattr(request, 'request_id', '')
        user = request.user

        def event_stream():
            service = get_ai_service()
            try:
                for event in service.chat_stream(
                    user=user, message=message,
                    session_id=session_id, request_id=request_id,
                ):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as e:
                error_event = {'type': 'error', 'message': str(e)}
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(
            event_stream(), content_type='text/event-stream; charset=utf-8',
        )
        response['Cache-Control'] = 'no-cache'
        response['Connection'] = 'keep-alive'
        response['X-Accel-Buffering'] = 'no'  # Nginx buferlab qo'ymasligi uchun MUHIM
        return response


class SessionBootstrapView(APIView):
    """
    POST /api/ai/sessions/bootstrap/

    Mini App AI chat ochilganda salom xabarini qaytaradi.
    """
    permission_classes = [IsAuthenticated, HasApprovedMembership]

    @extend_schema(
        request=SessionBootstrapSerializer,
        responses={
            200: ChatResponseSerializer,
            403: ErrorResponseSerializer,
        },
        summary='AI suhbatni salom bilan boshlash',
        description=(
            'Telegram Mini App `/ai?welcome=1` ochilganda chaqiriladi. '
            'Yangi sessiyada IMTIAZ AI salom beradi va qanday yordam '
            'berishini so\'raydi.'
        ),
        tags=['AI Assistant'],
    )
    def post(self, request):
        serializer = SessionBootstrapSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = get_ai_service().bootstrap_session(
            user=request.user,
            session_id=(
                str(serializer.validated_data['session_id'])
                if serializer.validated_data.get('session_id') else None
            ),
        )
        return Response({'success': True, **result})


class ActionConfirmView(APIView):
    """
    POST /api/ai/actions/{action_id}/confirm/
    Frontend tugmasi bosilganda chaqiriladi — haqiqiy Booking yaratiladi.
    Chat xabari ("ha") orqali emas — faqat shu endpoint.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description='Harakat bajarildi')},
        summary='AI harakatini tasdiqlash',
        tags=['AI Assistant'],
    )
    def post(self, request, action_id):
        try:
            log = confirm_pending_action(
                action_log_id=str(action_id),
                user=request.user,
                confirmation_source='frontend_button',
            )
        except ConfirmationError as e:
            return Response(
                {'success': False, 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            'success':   True,
            'action_id': str(log.id),
            'result':    log.result,
            'message':   t('action_confirmed', resolve_language(request.user)),
        })


class ActionRejectView(APIView):
    """POST /api/ai/actions/{action_id}/reject/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description='Bekor qilindi')},
        summary='AI harakatini bekor qilish',
        tags=['AI Assistant'],
    )
    def post(self, request, action_id):
        try:
            reject_pending_action(action_log_id=str(action_id), user=request.user)
        except ConfirmationError as e:
            return Response(
                {'success': False, 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            'success': True,
            'message': t('action_rejected', resolve_language(request.user)),
        })


class SessionListView(generics.ListAPIView):
    """GET /api/ai/sessions/"""
    permission_classes = [IsAuthenticated]
    serializer_class   = SessionListSerializer
    queryset           = ConversationSession.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ConversationSession.objects.none()
        return ConversationSession.objects.filter(
            user=self.request.user, is_active=True
        ).order_by('-updated_at')

    @extend_schema(
        tags=['AI Assistant'],
        summary='AI suhbat sessiyalari',
        description='Faol sessiyalar ro\'yxati.',
        responses={200: SessionListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SessionDetailView(generics.RetrieveDestroyAPIView):
    """GET / DELETE /api/ai/sessions/{id}/"""
    permission_classes = [IsAuthenticated]
    serializer_class   = ConversationSessionSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ConversationSession.objects.none()
        return ConversationSession.objects.filter(user=self.request.user)

    @extend_schema(
        tags=['AI Assistant'],
        summary='Sessiya tafsilotlari va xabarlar tarixi',
        responses={200: ConversationSessionSerializer, 404: OpenApiResponse(description='Topilmadi')},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=['AI Assistant'],
        summary='Sessiyani yopish (soft delete)',
        description='`is_active=False` qilinadi.',
        responses={204: OpenApiResponse(description='Yopildi')},
    )
    def delete(self, request, *args, **kwargs):
        session = self.get_object()
        session.is_active = False
        session.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class AIActionLogListView(generics.ListAPIView):
    """GET /api/ai/logs/"""
    permission_classes = [IsAuthenticated]
    serializer_class   = AIActionLogSerializer
    queryset           = AIActionLog.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return AIActionLog.objects.none()
        return AIActionLog.objects.filter(
            user=self.request.user
        ).order_by('-created_at')[:50]

    @extend_schema(
        tags=['AI Assistant'],
        summary='AI harakatlar audit jurnali',
        description='Oxirgi 50 ta AI action (booking, search, ...).',
        responses={200: AIActionLogSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)