"""App Settings serializers."""

from rest_framework import serializers
from .models import AppSetting


class AppSettingSerializer(serializers.ModelSerializer):
    """App setting serializer for admin CRUD."""
    
    class Meta:
        model = AppSetting
        fields = [
            'id', 'key', 'value', 'setting_type', 'description',
            'is_public', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PublicAppSettingSerializer(serializers.ModelSerializer):
    """Public serializer for non-sensitive settings."""
    
    class Meta:
        model = AppSetting
        fields = ['key', 'value', 'description']
        read_only_fields = ['key', 'value', 'description']
