"""App Settings admin configuration."""

from django.contrib import admin

from .models import AppSetting


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'setting_type', 'is_public', 'created_at']
    list_filter = ['setting_type', 'is_public']
    search_fields = ['key', 'value', 'description']
    readonly_fields = ['created_at', 'updated_at']
