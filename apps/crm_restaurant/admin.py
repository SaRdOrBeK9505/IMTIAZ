"""Restaurant CRM admin configuration."""

from django.contrib import admin

from .models import FeaturedItem, MenuCategory, MenuItem, RestaurantBookingLead, RestaurantStaff


@admin.register(RestaurantStaff)
class RestaurantStaffAdmin(admin.ModelAdmin):
    list_display = ['user', 'restaurant', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'restaurant__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(RestaurantBookingLead)
class RestaurantBookingLeadAdmin(admin.ModelAdmin):
    list_display = [
        'customer_name', 'customer_phone', 'restaurant', 'party_size',
        'preferred_time', 'status', 'accepted_by', 'is_ai_generated', 'created_at'
    ]
    list_filter = ['status', 'restaurant_type', 'is_ai_generated', 'created_at']
    search_fields = ['customer_name', 'customer_phone', 'restaurant__name']
    readonly_fields = ['created_at', 'updated_at', 'accepted_at']
    date_hierarchy = 'created_at'


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'branch', 'order', 'created_at']
    list_filter = ['branch', 'created_at']
    search_fields = ['name', 'branch__name']


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'is_available', 'created_at']
    list_filter = ['category', 'is_available', 'created_at']
    search_fields = ['name', 'description']


@admin.register(FeaturedItem)
class FeaturedItemAdmin(admin.ModelAdmin):
    list_display = ['custom_title', 'branch', 'menu_item', 'order', 'created_at']
    list_filter = ['branch', 'created_at']
    search_fields = ['custom_title', 'menu_item__name']
