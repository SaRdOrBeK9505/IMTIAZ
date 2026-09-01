"""User Inquiry/Support serializers."""

from rest_framework import serializers
from .models import UserInquiry


class UserInquirySerializer(serializers.ModelSerializer):
    """User inquiry serializer for creating inquiries."""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    responded_by_name = serializers.CharField(source='responded_by.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = UserInquiry
        fields = [
            'id', 'user', 'user_name', 'category', 'priority', 'status',
            'subject', 'message', 'admin_response', 'responded_by',
            'responded_by_name', 'responded_at', 'resolved_at',
            'resolution_notes', 'attachments', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'admin_response', 'responded_by',
            'responded_at', 'resolved_at', 'resolution_notes', 'created_at', 'updated_at'
        ]


class UserInquiryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating user inquiries."""
    
    class Meta:
        model = UserInquiry
        fields = ['category', 'priority', 'subject', 'message', 'attachments']
    
    def validate_subject(self, value):
        """Validate subject length."""
        if len(value) < 5:
            raise serializers.ValidationError('Mavzu kamida 5 ta belgidan iborat bo\'lishi kerak')
        return value
    
    def validate_message(self, value):
        """Validate message length."""
        if len(value) < 10:
            raise serializers.ValidationError('Xabar kamida 10 ta belgidan iborat bo\'lishi kerak')
        return value


class AdminInquiryResponseSerializer(serializers.Serializer):
    """Serializer for admin responses."""
    
    response = serializers.CharField(required=True, help_text='Admin javobi')
    status = serializers.ChoiceField(
        choices=UserInquiry.Status.choices,
        required=False,
        help_text='Yangi holat (ixtiyoriy)'
    )


class AdminInquiryResolveSerializer(serializers.Serializer):
    """Serializer for resolving inquiries."""
    
    resolution_notes = serializers.CharField(required=False, allow_blank=True, help_text='Hal qilish izohlari')
