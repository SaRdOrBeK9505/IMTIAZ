"""Bonuses app serializers."""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import BonusCategory


class BonusCategorySerializer(serializers.ModelSerializer):
    """Bonus category serializer for admin CRUD."""

    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = BonusCategory
        fields = [
            'id', 'service_type', 'name', 'description',
            'discount_percentage', 'discount_amount', 'min_purchase',
            'max_usage_count', 'usage_count', 'valid_from', 'valid_until',
            'is_active', 'order', 'is_valid', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'usage_count', 'created_at', 'updated_at']

    @extend_schema_field(bool)
    def get_is_valid(self, obj: BonusCategory) -> bool:
        return obj.is_valid()

    def validate(self, data):
        """Ensure at least one discount type is specified."""
        discount_percentage = data.get('discount_percentage')
        discount_amount = data.get('discount_amount')

        if not discount_percentage and not discount_amount:
            raise serializers.ValidationError(
                "Kamida bitta chegirma turi (foiz yoki sum) ko'rsatilishi kerak"
            )

        if discount_percentage and discount_amount:
            raise serializers.ValidationError(
                "Faqat bitta chegirma turi ko'rsatilishi mumkin (foiz YOKI sum)"
            )

        return data


class BonusPublishSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField(
        required=False, allow_null=True, default=None,
        help_text="Bo'sh — IMTIAZ platforma darajasida. To'ldirilsa — shu tashkilot nomidan e'lon qilinadi.",
    )


class BonusAssignSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.UUIDField(), min_length=1, max_length=1000,
        help_text="Kimlarga shaxsiy vaucher berilishi kerak",
    )
