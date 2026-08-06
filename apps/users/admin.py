from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, OTPCode, WalletTransaction


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display    = ['telegram_id', 'phone', 'full_name', 'telegram_username',
                       'ai_autonomy_level', 'balance', 'is_active', 'created_at']
    list_filter     = ['is_active', 'ai_autonomy_level', 'is_staff', 'language_code']
    search_fields   = ['telegram_id', 'telegram_username', 'first_name', 'last_name', 'phone']
    ordering        = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at', 'balance', 'bonus_points']

    fieldsets = (
        ('Identifikator', {
            'fields': ('telegram_id', 'telegram_username', 'phone')
        }),
        ('Shaxsiy', {
            'fields': ('first_name', 'last_name', 'avatar_url', 'language_code')
        }),
        ('AI sozlamalari', {
            'fields': ('ai_autonomy_level', 'ai_auto_price_limit')
        }),
        ('Hamyon', {
            'fields': ('balance', 'bonus_points'),
            'classes': ('collapse',),
        }),
        ('Huquqlar', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Vaqtlar', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields':  ('telegram_id', 'phone', 'first_name', 'last_name'),
        }),
    )


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display  = ['phone', 'purpose', 'is_used', 'attempts', 'expires_at', 'created_at']
    list_filter   = ['purpose', 'is_used']
    search_fields = ['phone']
    readonly_fields = ['created_at', 'updated_at', 'code']

    # OTP kodlarini o'zgartirish taqiqlangan
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'transaction_type', 'amount', 'balance_after', 'created_at']
    list_filter   = ['transaction_type']
    search_fields = ['user__telegram_username', 'user__phone', 'user__first_name']
    readonly_fields = ['id', 'created_at', 'updated_at']

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # Moliyaviy yozuvlar o'chirilmaydi
