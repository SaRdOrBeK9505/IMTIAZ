"""Bonuses app serializers."""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import BonusCategory, UserBonus


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


class UserBonusSerializer(serializers.ModelSerializer):
    """User bonus serializer."""
    
    bonus_category_name = serializers.CharField(source='bonus_category.name', read_only=True)
    bonus_category_service_type = serializers.CharField(source='bonus_category.service_type', read_only=True)
    discount_percentage = serializers.IntegerField(source='bonus_category.discount_percentage', read_only=True)
    discount_amount = serializers.DecimalField(source='bonus_category.discount_amount', read_only=True, max_digits=14, decimal_places=2)
    is_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = UserBonus
        fields = [
            'id', 'bonus_category', 'bonus_category_name', 'bonus_category_service_type',
            'discount_percentage', 'discount_amount', 'qr_code', 'qr_code_image',
            'is_used', 'used_at', 'booking', 'is_valid', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'qr_code', 'qr_code_image', 'is_used', 'used_at', 'created_at', 'updated_at']
    
    @extend_schema_field(bool)
    def get_is_valid(self, obj: UserBonus) -> bool:
        return obj.bonus_category.is_valid() and not obj.is_used


class BonusQRScanSerializer(serializers.Serializer):
    """Serializer for scanning QR codes."""
    
    qr_code = serializers.CharField(required=True, help_text='QR kod identifikatori')
    
    def validate_qr_code(self, value):
        """Validate QR code format."""
        if ':' not in value:
            raise serializers.ValidationError("Noto'g'ri QR kod formati")
        return value


class BonusValidationResponseSerializer(serializers.Serializer):
    """Response serializer for bonus validation."""
    
    valid = serializers.BooleanField()
    message = serializers.CharField(allow_null=True)
    bonus = serializers.DictField(allow_null=True)
    error = serializers.CharField(allow_null=True)
    category_valid = serializers.BooleanField(allow_null=True)
    category_active = serializers.BooleanField(allow_null=True)
    valid_until = serializers.DateTimeField(allow_null=True)
    usage_count = serializers.IntegerField(allow_null=True)
    max_usage_count = serializers.IntegerField(allow_null=True)
    used_at = serializers.DateTimeField(allow_null=True)
