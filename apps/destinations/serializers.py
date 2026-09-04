"""Destination serializers."""

from rest_framework import serializers

from .models import Destination


class DestinationAdminSerializer(serializers.ModelSerializer):
    """Admin — to'liq CRUD."""

    class Meta:
        model = Destination
        fields = [
            'id', 'code', 'name', 'group',
            'flag_image', 'order', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DestinationClientSerializer(serializers.ModelSerializer):
    """Client — faqat o'qish."""

    group_display = serializers.CharField(source='get_group_display', read_only=True)

    class Meta:
        model = Destination
        fields = ['id', 'code', 'name', 'group', 'group_display', 'flag_image']
        read_only_fields = fields
