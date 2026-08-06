from rest_framework import serializers
from .models import ExternalProviderLog


class ExternalProviderLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ExternalProviderLog
        fields = [
            'id', 'provider', 'method', 'is_success',
            'status_code', 'response_time_ms',
            'error_message', 'booking_id', 'created_at',
        ]
        read_only_fields = fields
