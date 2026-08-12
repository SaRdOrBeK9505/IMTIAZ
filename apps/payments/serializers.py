"""Payments app serializers."""

from rest_framework import serializers
from .models import Payment, PaymentLog, PaymentProvider


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
    """AlifPay orqali to'lov boshlash — mijoz to'g'ridan-to'g'ri tashqi provayderda to'laydi."""
    booking_id = serializers.UUIDField()
    provider = serializers.ChoiceField(
        choices=[PaymentProvider.ALIFPAY],
        default=PaymentProvider.ALIFPAY,
        help_text='Hozir faqat AlifPay qo\'llab-quvvatlanadi.',
    )
    return_url = serializers.URLField(
        required=False, allow_blank=True,
        help_text='To\'lovdan keyin qaytish URL (masalan: https://app.imtiaz.uz/payment/success)',
    )
    cancel_url = serializers.URLField(
        required=False, allow_blank=True,
        help_text='To\'lov bekor qilinganda qaytish URL',
    )
