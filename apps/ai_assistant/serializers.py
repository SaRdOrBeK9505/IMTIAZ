"""AI Assistant serializers."""

from rest_framework import serializers
from .models import ConversationSession, ConversationMessage, AIActionLog


class ChatMessageSerializer(serializers.Serializer):
    """POST /api/ai/chat/"""
    message    = serializers.CharField(min_length=1, max_length=4096)
    session_id = serializers.UUIDField(required=False, allow_null=True)


class SessionBootstrapSerializer(serializers.Serializer):
    """POST /api/ai/sessions/bootstrap/"""
    session_id = serializers.UUIDField(required=False, allow_null=True)


class ChatResponseSerializer(serializers.Serializer):
    """Chat API javobi sxemasi (faqat docs uchun)."""
    success                 = serializers.BooleanField()
    session_id              = serializers.UUIDField()
    message_id              = serializers.UUIDField(required=False)
    content                 = serializers.CharField()
    tool_calls_count        = serializers.IntegerField()
    tokens_used             = serializers.IntegerField()
    requires_confirmation   = serializers.BooleanField(
        help_text=(
            "True bo'lsa — AI biror harakatni bajarishdan oldin tasdiqlash so'raydi. "
            "content maydoni tasdiqlash savolini o'z ichiga oladi."
        )
    )
    timing = serializers.DictField(
        required=False,
        help_text=(
            "Debug/diagnostika uchun: bu so'rov ichidagi har bir qadam "
            "(tarix yuklash, AI chaqiruvi, har bir tool) necha ms olganini "
            "ko'rsatadi. Masalan: {'request_id': 'e8b6...', 'total_ms': 842, "
            "'steps': [{'step': 'provider_call', 'duration_ms': 610, 'ok': true}, ...]}"
        ),
    )


class ConversationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model        = ConversationMessage
        fields       = ['id', 'role', 'content', 'tokens_used', 'created_at']
        read_only_fields = fields


class ConversationSessionSerializer(serializers.ModelSerializer):
    messages = ConversationMessageSerializer(many=True, read_only=True)

    class Meta:
        model        = ConversationSession
        fields       = ['id', 'title', 'is_active', 'created_at', 'updated_at', 'messages']
        read_only_fields = fields


class SessionListSerializer(serializers.ModelSerializer):
    class Meta:
        model        = ConversationSession
        fields       = ['id', 'title', 'is_active', 'updated_at']
        read_only_fields = fields


class AIActionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AIActionLog
        fields = [
            'id', 'action_type', 'service_type',
            'payload', 'status', 'error_message',
            'amount_requiring_confirmation',
            'created_at',
        ]
        read_only_fields = fields