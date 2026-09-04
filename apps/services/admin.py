"""
Services — Django Admin konfiguratsiyasi.

ServiceIcon va ServiceColor ni Django admin orqali boshqarish.
Service ni esa icon va color ga bog'lab yaratish/tahrirlash.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Service, ServiceColor, ServiceIcon


@admin.register(ServiceIcon)
class ServiceIconAdmin(admin.ModelAdmin):
    list_display  = ('name', 'slug', 'has_svg', 'icon_preview', 'created_at')
    list_filter   = ()
    search_fields = ('name', 'slug')
    readonly_fields = ('id', 'slug', 'created_at', 'updated_at', 'icon_preview')
    ordering      = ('name',)

    fieldsets = (
        ('Asosiy', {
            'fields': ('id', 'name', 'slug'),
        }),
        ('Icon manba', {
            'fields': ('svg', 'image', 'icon_preview'),
            'description': "SVG kod yoki rasm fayldan birini to'ldiring.",
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='SVG', boolean=True)
    def has_svg(self, obj):
        return bool(obj.svg)

    @admin.display(description='Ko\'rinish')
    def icon_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:32px;width:32px;object-fit:contain;" />',
                obj.image.url,
            )
        if obj.svg:
            return format_html(
                '<span style="display:inline-block;width:32px;height:32px;">{}</span>',
                obj.svg,
            )
        return '—'


@admin.register(ServiceColor)
class ServiceColorAdmin(admin.ModelAdmin):
    list_display  = ('name', 'hex_code', 'color_dot', 'created_at')
    search_fields = ('name', 'hex_code')
    readonly_fields = ('id', 'created_at', 'updated_at', 'color_dot')
    ordering      = ('name',)

    fieldsets = (
        ('Asosiy', {
            'fields': ('id', 'name', 'hex_code', 'color_dot'),
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Rang')
    def color_dot(self, obj):
        return format_html(
            '<span style="display:inline-block;width:24px;height:24px;'
            'border-radius:50%;background:{};border:1px solid #ccc;"></span>',
            obj.hex_code,
        )


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display  = (
        'name', 'slug', 'icon_preview', 'color_dot',
        'is_active', 'order', 'created_at',
    )
    list_filter   = ('is_active',)
    search_fields = ('name', 'slug')
    readonly_fields = ('id', 'slug', 'created_at', 'updated_at', 'icon_preview', 'color_dot')
    ordering      = ('order', 'id')
    list_editable = ('is_active', 'order')
    autocomplete_fields = ('icon', 'color')

    fieldsets = (
        ('Asosiy', {
            'fields': ('id', 'name', 'slug', 'description'),
        }),
        ('Ko\'rinish', {
            'fields': ('icon', 'icon_preview', 'color', 'color_dot'),
        }),
        ('Sozlamalar', {
            'fields': ('is_active', 'order'),
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Icon')
    def icon_preview(self, obj):
        if not obj.icon_id:
            return '—'
        icon = obj.icon
        if icon.image:
            return format_html(
                '<img src="{}" style="height:24px;width:24px;object-fit:contain;" />',
                icon.image.url,
            )
        if icon.svg:
            return format_html(
                '<span style="display:inline-block;width:24px;height:24px;">{}</span>',
                icon.svg,
            )
        return format_html('<code>{}</code>', icon.slug)

    @admin.display(description='Rang')
    def color_dot(self, obj):
        if not obj.color_id:
            return '—'
        return format_html(
            '<span style="display:inline-block;width:20px;height:20px;'
            'border-radius:50%;background:{};border:1px solid #ccc;" '
            'title="{}"></span>',
            obj.color.hex_code,
            obj.color.hex_code,
        )
