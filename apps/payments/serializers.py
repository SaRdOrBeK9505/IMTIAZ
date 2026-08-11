"""Payments app serializers."""

from rest_framework import serializers
from .models import Payment, PaymentLog, PaymentProvider, PaymentStatus


class PaymentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentLog
        fields = ['from_status', 'to_status', 'note', 'created_at']
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    logs = PaymentLogSerializer(many=True, read_only=True)
    booking_title = serializers.CharField(
        source='booking.title', read_only=True, default=None
    )

    class Meta:
        model = Payment
        fields = [
            'id', 'provider', 'status', 'amount', 'currency',
            'commission_amount', 'external_transaction_id',
            'refunded_amount', 'error_message',
            'booking_title', 'created_at', 'logs',
        ]
        read_only_fields = fields


class PaymentInitiateSerializer(serializers.Serializer):
    """Tashqi provayder orqali to'lov boshlash."""
    booking_id = serializers.UUIDField()
    provider = serializers.ChoiceField(
        choices=[
            PaymentProvider.ALIFPAY,
            PaymentProvider.PAYME,
            PaymentProvider.CLICK,
            PaymentProvider.MULTICARD,
        ],
        help_text='To\'lov provayderi. Production uchun alifpay tavsiya etiladi.',
    )
    return_url = serializers.URLField(
        required=False, allow_blank=True,
        help_text='To\'lovdan keyin qaytish URL (masalan: https://app.imtiaz.uz/payment/success)',
    )
    cancel_url = serializers.URLField(
        required=False, allow_blank=True,
        help_text='To\'lov bekor qilinganda qaytish URL',
    )


class WalletPaymentSerializer(serializers.Serializer):
    """IMTIAZ ichki hamyon orqali to'lov."""
    booking_id = serializers.UUIDField()
