from django.contrib import admin
from .models import ConversationSession, ConversationMessage, AIActionLog


@admin.register(AIActionLog)
class AIActionLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action_type', 'service_type', 'status', 'created_at']
    list_filter = ['action_type', 'service_type', 'status']
    search_fields = ['user__telegram_username', 'user__first_name']
    readonly_fields = ['user', 'session', 'action_type', 'service_type', 'payload', 'result', 'status', 'created_at']
    date_hierarchy = 'created_at'


@admin.register(ConversationSession)
class ConversationSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['user__telegram_username', 'title']


@admin.register(ConversationMessage)
class ConversationMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'role', 'tokens_used', 'created_at']
    list_filter = ['role']
    readonly_fields = ['session', 'role', 'content', 'tokens_used', 'created_at']
