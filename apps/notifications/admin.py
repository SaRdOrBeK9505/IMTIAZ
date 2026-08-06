from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display   = ['user', 'notification_type', 'channel', 'status',
                      'sent_at', 'created_at']
    list_filter    = ['notification_type', 'channel', 'status']
    search_fields  = ['user__telegram_username', 'user__phone', 'title']
    readonly_fields = ['id', 'telegram_message_id', 'sent_at', 'read_at',
                       'created_at', 'updated_at']
    date_hierarchy = 'created_at'

    def has_change_permission(self, request, obj=None):
        return False  # Log — o'zgartirilmaydi
