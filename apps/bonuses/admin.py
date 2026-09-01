"""Bonuses app admin configuration."""

from django.contrib import admin

from .models import BonusCategory, UserBonus


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


@admin.register(UserBonus)
class UserBonusAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'bonus_category', 'qr_code', 'is_used', 'used_at', 'created_at'
    ]
    list_filter = ['is_used', 'bonus_category__service_type', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'qr_code']
    readonly_fields = ['qr_code', 'qr_code_image', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
