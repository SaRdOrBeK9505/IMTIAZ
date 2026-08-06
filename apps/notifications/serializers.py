from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model  = Notification
        fields = [
            'id', 'notification_type', 'channel', 'status',
            'title', 'body', 'metadata', 'is_read',
            'sent_at', 'read_at', 'created_at',
        ]
        read_only_fields = fields

    def get_is_read(self, obj) -> bool:
        return obj.status == Notification.Status.READ
