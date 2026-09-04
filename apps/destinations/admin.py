"""Destination admin."""

from django.contrib import admin
from django.utils.html import format_html

from .models import Destination


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display  = ['flag_preview', 'code', 'name', 'group', 'order', 'is_active']
    list_filter   = ['group', 'is_active']
    search_fields = ['code', 'name']
    list_editable = ['order', 'is_active']
    ordering      = ['group', 'order']
    readonly_fields = ['flag_preview', 'created_at', 'updated_at']

    fieldsets = (
        (None, {
            'fields': ('code', 'name', 'group'),
        }),
        ('Bayroq', {
            'fields': ('flag_image', 'flag_preview'),
        }),
        ('Sozlamalar', {
            'fields': ('order', 'is_active'),
        }),
        ('Vaqt', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Bayroq')
    def flag_preview(self, obj):
        if obj.flag_image:
            return format_html(
                '<img src="{}" style="height:28px;width:auto;border-radius:3px;" />',
                obj.flag_image.url,
            )
        return '—'
