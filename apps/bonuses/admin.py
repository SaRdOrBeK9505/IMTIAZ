"""Bonuses app admin configuration."""

from django.contrib import admin

from .models import BonusCategory


@admin.register(BonusCategory)
class BonusCategoryAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'service_type', 'discount_percentage', 'discount_amount',
        'min_purchase', 'usage_count', 'max_usage_count', 'is_active',
        'valid_from', 'valid_until', 'order'
    ]
    list_filter = ['service_type', 'is_active', 'valid_from', 'valid_until']
    search_fields = ['name', 'description']
    readonly_fields = ['usage_count', 'created_at', 'updated_at']
    date_hierarchy = 'valid_from'
