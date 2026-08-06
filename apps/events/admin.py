from django.contrib import admin
from .models import Event, EventCategory


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
