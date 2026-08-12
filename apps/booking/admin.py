from django.contrib import admin
from .models import (
    Booking,
    BookingSettlement,
    BookingTransactionLog,
    FlightBooking,
    TrainBooking,
    RestaurantBooking,
    EventBooking,
)


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


class BookingTransactionLogInline(admin.TabularInline):
    model = BookingTransactionLog
    extra = 0
    readonly_fields = ['step', 'from_status', 'to_status', 'success', 'message', 'error_code', 'created_at']
    can_delete = False


@admin.register(BookingSettlement)
class BookingSettlementAdmin(admin.ModelAdmin):
    list_display = [
        'booking', 'status', 'locked_price', 'retry_count',
        'refund_attempts', 'last_error_code', 'created_at',
    ]
    list_filter = ['status', 'last_error_code']
    search_fields = ['booking__title', 'booking__external_booking_id', 'idempotency_key']
    readonly_fields = [
        'booking', 'payment', 'idempotency_key', 'locked_price',
        'bookhara_deposit_at_preflight', 'retry_count', 'refund_attempts',
        'completed_at', 'created_at', 'updated_at',
    ]
    inlines = [BookingTransactionLogInline]
    actions = ['retry_settlement', 'retry_refund']

    @admin.action(description='Bookhara settlement qayta urinish')
    def retry_settlement(self, request, queryset):
        from apps.payments.tasks import retry_bookhara_settlement
        for settlement in queryset:
            retry_bookhara_settlement.delay(str(settlement.id))

    @admin.action(description='Refund qayta urinish')
    def retry_refund(self, request, queryset):
        from apps.payments.tasks import retry_settlement_refund
        for settlement in queryset:
            retry_settlement_refund.delay(str(settlement.id))
