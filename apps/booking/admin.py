from django.contrib import admin
from .models import Booking, FlightBooking, TrainBooking, RestaurantBooking, EventBooking


class FlightDetailInline(admin.StackedInline):
    model = FlightBooking
    extra = 0


class TrainDetailInline(admin.StackedInline):
    model = TrainBooking
    extra = 0


class RestaurantDetailInline(admin.StackedInline):
    model = RestaurantBooking
    extra = 0


class EventDetailInline(admin.StackedInline):
    model = EventBooking
    extra = 0


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['user', 'service_type', 'title', 'status', 'final_price', 'currency', 'created_by_ai', 'created_at']
    list_filter = ['service_type', 'status', 'created_by_ai']
    search_fields = ['user__telegram_username', 'user__first_name', 'title', 'external_booking_id']
    readonly_fields = ['created_at', 'updated_at', 'ai_action_log']
    date_hierarchy = 'created_at'
    inlines = [FlightDetailInline, TrainDetailInline, RestaurantDetailInline, EventDetailInline]
