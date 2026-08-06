from django.contrib import admin
from .models import ExternalProviderLog


@admin.register(ExternalProviderLog)
class ExternalProviderLogAdmin(admin.ModelAdmin):
    list_display = ['provider', 'method', 'is_success', 'status_code', 'response_time_ms', 'created_at']
    list_filter = ['provider', 'method', 'is_success']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
