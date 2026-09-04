"""Banners app admin configuration."""

from django.contrib import admin
from .models import Banner


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    """Banner admin paneli."""
    
    list_display = ['title', 'link', 'order', 'is_active', 'created_at']
    list_filter = ['is_active', 'link']
    search_fields = ['title', 'description']
    list_editable = ['order', 'is_active']
    ordering = ['order', '-created_at']
    
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('title', 'description', 'image_url', 'link')
        }),
        ('Sozlamalar', {
            'fields': ('order', 'is_active')
        }),
    )
