"""QR Codes app — Django Admin."""

from django.contrib import admin
from django.utils.html import format_html

from .models import QRCode, QRCodeRedemption, QRAnalyticsSummary


class QRCodeRedemptionInline(admin.TabularInline):
    model = QRCodeRedemption
    extra = 0
    fields = ['user', 'service_type', 'order_amount', 'discount_applied', 'final_amount', 'status', 'scanned_at']
    readonly_fields = ['scanned_at', 'discount_applied', 'final_amount']
    can_delete = False
    max_num = 20

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'code', 'organization', 'qr_type',
        'discount_value', 'total_used_count', 'is_active',
        'valid_until', 'qr_preview',
    ]
    list_editable  = ['is_active']
    list_filter    = ['qr_type', 'is_active', 'organization']
    search_fields  = ['title', 'code', 'organization__name']
    readonly_fields = ['code', 'qr_image', 'total_used_count', 'created_at', 'updated_at', 'qr_preview']
    inlines = [QRCodeRedemptionInline]

    fieldsets = (
        ('Asosiy', {
            'fields': ('organization', 'branch', 'title', 'description', 'code', 'qr_image', 'qr_preview')
        }),
        ("Chegirma konfiguratsiyasi", {
            'fields': ('qr_type', 'discount_value', 'max_discount_amount', 'minimum_order_amount')
        }),
        ("Qo'llanish doirasi", {
            'fields': ('applicable_services',)
        }),
        ('Cheklovlar', {
            'fields': ('max_total_uses', 'max_uses_per_user', 'total_used_count')
        }),
        ('Muddat va holat', {
            'fields': ('valid_from', 'valid_until', 'is_active', 'created_by')
        }),
    )

    def qr_preview(self, obj):
        if obj.qr_image:
            return format_html(
                '<img src="{}" style="width:100px;height:100px;object-fit:contain;" />',
                obj.qr_image.url,
            )
        return '—'
    qr_preview.short_description = 'QR Ko\'rinishi'


@admin.register(QRCodeRedemption)
class QRCodeRedemptionAdmin(admin.ModelAdmin):
    list_display  = ['qr_code', 'user', 'service_type', 'discount_applied', 'final_amount', 'status', 'scanned_at']
    list_filter   = ['status', 'service_type', 'qr_code__organization']
    search_fields = ['qr_code__code', 'user__phone', 'qr_code__title']
    readonly_fields = ['scanned_at', 'qr_code', 'user', 'booking', 'ip_address', 'user_agent']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(QRAnalyticsSummary)
class QRAnalyticsSummaryAdmin(admin.ModelAdmin):
    list_display = [
        'qr_code', 'date', 'scan_count', 'apply_count',
        'reject_count', 'total_discount_given', 'unique_users',
    ]
    list_filter  = ['qr_code', 'date']
    ordering     = ['-date']
    readonly_fields = list_display

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
