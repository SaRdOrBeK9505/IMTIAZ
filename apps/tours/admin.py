"""Tours app — Django Admin."""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    TourCategory, TourDestination, TourDestinationImage, TourPackage,
    TourItineraryDay, TourAvailability, TourVoucher, TourReview,
)


@admin.register(TourCategory)
class TourCategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'icon', 'is_active', 'sort_order']
    list_editable = ['is_active', 'sort_order']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(TourDestination)
class TourDestinationAdmin(admin.ModelAdmin):
    list_display   = ['name', 'country', 'city', 'organization', 'is_popular', 'is_active']
    list_editable  = ['is_popular', 'is_active']
    list_filter    = ['country', 'is_popular', 'organization']
    search_fields  = ['name', 'country', 'city']
    prepopulated_fields = {'slug': ('country', 'city')}
    inlines = []


class TourDestinationImageInline(admin.TabularInline):
    model = TourDestinationImage
    extra = 1
    fields = ['image', 'caption', 'sort_order', 'is_cover']


TourDestinationAdmin.inlines = [TourDestinationImageInline]


class TourItineraryDayInline(admin.TabularInline):
    model  = TourItineraryDay
    extra  = 0
    fields = ['day_number', 'title', 'accommodation']


class TourAvailabilityInline(admin.TabularInline):
    model  = TourAvailability
    extra  = 0
    fields = ['departure_date', 'return_date', 'total_seats', 'booked_seats', 'status', 'price_override']
    readonly_fields = ['booked_seats']


@admin.register(TourPackage)
class TourPackageAdmin(admin.ModelAdmin):
    list_display   = ['title', 'organization', 'destination', 'base_price', 'duration_days', 'is_active', 'is_featured', 'avg_rating']
    list_editable  = ['is_active', 'is_featured']
    list_filter    = ['is_active', 'is_featured', 'difficulty_level', 'destination__country']
    search_fields  = ['title', 'organization__name', 'destination__name']
    readonly_fields = ['avg_rating', 'review_count', 'total_bookings', 'slug']
    inlines        = [TourItineraryDayInline, TourAvailabilityInline]
    fieldsets = (
        ('Asosiy', {'fields': ('organization', 'branch', 'title', 'slug', 'category', 'destination')}),
        ('Tavsif', {'fields': ('short_description', 'description', 'cover_image', 'gallery')}),
        ('Davomiylik & Narx', {'fields': ('duration_days', 'duration_nights', 'base_price', 'currency', 'price_per', 'max_group_size', 'min_group_size')}),
        ('Mazmun', {'fields': ('inclusions', 'exclusions', 'requirements', 'difficulty_level', 'languages_offered', 'tags')}),
        ('Holat', {'fields': ('is_active', 'is_featured', 'is_exclusive', 'exclusive_tier')}),
        ('Statistika (auto)', {'fields': ('avg_rating', 'review_count', 'total_bookings'), 'classes': ('collapse',)}),
    )


@admin.register(TourVoucher)
class TourVoucherAdmin(admin.ModelAdmin):
    list_display   = ['voucher_number', 'tour_booking', 'issued_by', 'status', 'issued_at', 'download_count']
    list_filter    = ['status']
    search_fields  = ['voucher_number']
    readonly_fields = ['voucher_number', 'issued_at', 'download_count', 'package_snapshot', 'tourist_snapshot', 'booking_snapshot']


@admin.register(TourReview)
class TourReviewAdmin(admin.ModelAdmin):
    list_display  = ['user', 'package', 'rating', 'is_verified', 'is_published', 'created_at']
    list_editable = ['is_published']
    list_filter   = ['is_published', 'is_verified', 'rating']
    search_fields = ['user__full_name', 'package__title']
