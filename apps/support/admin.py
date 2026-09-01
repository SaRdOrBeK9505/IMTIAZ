"""User Inquiry/Support admin configuration."""

from django.contrib import admin

from .models import UserInquiry


@admin.register(UserInquiry)
class UserInquiryAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'subject', 'category', 'priority', 'status',
        'responded_by', 'responded_at', 'resolved_at', 'created_at'
    ]
    list_filter = ['status', 'priority', 'category', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'subject', 'message']
    readonly_fields = ['responded_at', 'resolved_at', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
