"""Destination admin configuration."""

from django.contrib import admin

from .models import Country, Destination, DestinationImage


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'name_uz', 'code', 'flag_emoji', 'currency', 'is_active', 'order']
    list_filter = ['is_active']
    search_fields = ['name', 'name_uz', 'code']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'name_uz', 'country', 'category', 'rating',
        'review_count', 'is_popular', 'is_active', 'order'
    ]
    list_filter = ['category', 'is_popular', 'is_active', 'country']
    search_fields = ['name', 'name_uz', 'description']
    readonly_fields = ['rating', 'review_count', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(DestinationImage)
class DestinationImageAdmin(admin.ModelAdmin):
    list_display = ['destination', 'caption', 'is_primary', 'order', 'created_at']
    list_filter = ['is_primary', 'destination__country']
    search_fields = ['caption', 'destination__name']
    readonly_fields = ['created_at', 'updated_at']
