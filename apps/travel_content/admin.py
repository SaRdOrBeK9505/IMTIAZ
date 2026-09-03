from django.contrib import admin

from .models import TravelReel, CuratedTrip, CuratedTripImage


@admin.register(TravelReel)
class TravelReelAdmin(admin.ModelAdmin):
    list_display = ['title', 'media_type', 'destination', 'view_count', 'is_active', 'sort_order']
    list_filter = ['media_type', 'is_active', 'destination__country']
    search_fields = ['title', 'subtitle', 'description']
    readonly_fields = ['view_count', 'created_at', 'updated_at']
    list_editable = ['sort_order', 'is_active']


class CuratedTripImageInline(admin.TabularInline):
    model = CuratedTripImage
    extra = 1
    fields = ['image', 'caption', 'sort_order']


@admin.register(CuratedTrip)
class CuratedTripAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'destination', 'duration_display', 'price_from', 'currency',
        'is_verified_by_imtiaz', 'is_featured', 'is_active', 'sort_order',
    ]
    list_filter = ['is_active', 'is_featured', 'is_verified_by_imtiaz', 'destination__country']
    search_fields = ['title', 'subtitle', 'short_description']
    readonly_fields = ['view_count', 'created_at', 'updated_at']
    list_editable = ['sort_order', 'is_featured', 'is_active']
    inlines = [CuratedTripImageInline]

