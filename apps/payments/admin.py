from django.contrib import admin
from .models import Payment, PaymentLog


class PaymentLogInline(admin.TabularInline):
    model = PaymentLog
    extra = 0
    readonly_fields = ['from_status', 'to_status', 'note', 'metadata', 'created_at']
    can_delete = False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'provider', 'amount', 'currency', 'status', 'created_at']
    list_filter   = ['provider', 'status', 'currency']
    search_fields = ['user__telegram_username', 'user__first_name', 'external_transaction_id']
    readonly_fields = [
        'id', 'user', 'booking', 'subscription',
        'provider', 'amount', 'currency',
        'external_transaction_id', 'external_order_id', 'provider_response',
        'commission_amount', 'commission_percent',
        'refunded_amount', 'error_message',
        'created_at', 'updated_at',
    ]
    inlines = [PaymentLogInline]

    # To'lov ma'lumotlarini o'zgartirish taqiqlangan — faqat ko'rish
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
