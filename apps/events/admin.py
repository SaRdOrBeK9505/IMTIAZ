from django.contrib import admin
from .models import Event, EventCategory, EventRegistration


@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'starts_at', 'is_exclusive', 'status', 'available_tickets', 'ticket_price']
    list_filter = ['status', 'is_exclusive', 'category']
    search_fields = ['title', 'venue_name']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'starts_at'


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'event', 'ticket_count', 'total_price',
        'status', 'booking_reference', 'checked_in_at', 'created_at'
    ]
    list_filter = ['status', 'event', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'booking_reference']
    readonly_fields = ['booking_reference', 'checked_in_at', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
