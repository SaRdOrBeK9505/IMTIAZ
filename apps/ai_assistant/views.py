"""AI Assistant views."""

from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core.openapi_schemas import ErrorResponseSerializer
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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


def get_ai_service() -> AIAssistantService:
    return AIAssistantService()


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
        serializer = ChatMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = get_ai_service().chat(
            user=request.user,
            message=serializer.validated_data['message'],
            session_id=(
                str(serializer.validated_data['session_id'])
                if serializer.validated_data.get('session_id') else None
            ),
            # RequestLoggingMiddleware o'rnatgan request_id — shu orqali
            # "API POST /api/ai/chat/ → 200 [842ms]" logi va "AI chat timing"
            # logi bitta so'rov ekanini bir xil request_id orqali bilib olamiz.
            request_id=getattr(request, 'request_id', ''),
        )
        return Response({'success': True, **result})


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