from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['title', 'organization', 'vertical', 'stage', 'customer_phone', 'created_at']
    list_filter = ['vertical', 'stage', 'organization']
    search_fields = ['title', 'customer_name', 'customer_phone']
    readonly_fields = ['created_at', 'updated_at']
