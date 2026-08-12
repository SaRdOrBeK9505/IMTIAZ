from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, OTPCode, WalletTransaction, UserDevice


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display    = [
        'phone', 'full_name', 'telegram_username',
        'role', 'is_phone_verified',
        'ai_autonomy_level', 'balance', 'is_active', 'created_at',
    ]
    list_filter     = ['role', 'is_active', 'is_phone_verified', 'ai_autonomy_level', 'is_staff']
    search_fields   = ['phone', 'telegram_id', 'telegram_username', 'first_name', 'last_name']
    ordering        = ['-created_at']
    readonly_fields = ['id', 'telegram_id', 'created_at', 'updated_at', 'balance', 'bonus_points']

    def get_search_fields(self, request):
        return self.search_fields

    fieldsets = (
        ('Identifikator', {
            'fields': ('phone', 'telegram_id', 'telegram_username', 'password'),
        }),
        ('Shaxsiy', {
            'fields': ('first_name', 'last_name', 'avatar_url', 'language_code'),
        }),
        ('Rol va tasdiqlash', {
            'fields': ('role', 'is_phone_verified'),
        }),
        ('AI sozlamalari', {
            'fields': ('ai_autonomy_level', 'ai_auto_price_limit'),
        }),
        ('Hamyon', {
            'fields':   ('balance', 'bonus_points'),
            'classes':  ('collapse',),
        }),
        ('Huquqlar', {
            'fields':  ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Vaqtlar', {
            'fields':  ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields':  ('phone', 'password1', 'password2', 'role', 'first_name', 'last_name'),
        }),
    )


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display    = ['phone', 'purpose', 'is_used', 'attempts', 'expires_at', 'created_at']
    list_filter     = ['purpose', 'is_used']
    search_fields   = ['phone']
    readonly_fields = ['code', 'created_at', 'updated_at']

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display    = ['user', 'transaction_type', 'amount', 'balance_after', 'created_at']
    list_filter     = ['transaction_type']
    search_fields   = ['user__phone', 'user__telegram_username', 'user__first_name']
    readonly_fields = ['id', 'created_at', 'updated_at']

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # Moliyaviy yozuvlar o'chirilmaydi


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display    = ['user', 'device_type', 'device_name', 'ip_address', 'is_active', 'last_active']
    list_filter     = ['device_type', 'is_active']
    search_fields   = ['user__phone', 'user__telegram_username', 'device_name', 'ip_address']
    readonly_fields = ['id', 'refresh_token_jti', 'last_active', 'created_at', 'updated_at']

    def has_change_permission(self, request, obj=None):
        return False
