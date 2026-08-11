"""QR Codes app serializers."""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import QRCode, QRCodeRedemption, QRAnalyticsSummary


# ─── User-facing ──────────────────────────────────────────────────────────────

class QRCodePublicSerializer(serializers.ModelSerializer):
    """Foydalanuvchi QR skanlaganda ko'radigan ma'lumotlar."""
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    is_valid          = serializers.BooleanField(read_only=True)

    class Meta:
        model  = QRCode
        fields = [
            'code', 'title', 'description', 'qr_type',
            'discount_value', 'max_discount_amount',
            'minimum_order_amount', 'applicable_services',
            'valid_until', 'is_valid', 'organization_name',
        ]


class QRRedeemRequestSerializer(serializers.Serializer):
    """Chegirma qo'llash so'rovi."""
    order_amount = serializers.DecimalField(max_digits=16, decimal_places=2, min_value=0)
    service_type = serializers.ChoiceField(
        choices=['tour', 'restaurant', 'general'], default='general'
    )
    booking_id   = serializers.UUIDField(required=False, allow_null=True)
    customer_name  = serializers.CharField(required=False, allow_blank=True, max_length=255)
    customer_phone = serializers.CharField(required=False, allow_blank=True, max_length=20)


class QRRedeemResponseSerializer(serializers.Serializer):
    """Chegirma qo'llash javobi."""
    success              = serializers.BooleanField()
    message              = serializers.CharField()
    discount_applied     = serializers.DecimalField(max_digits=16, decimal_places=2, required=False)
    final_amount         = serializers.DecimalField(max_digits=16, decimal_places=2, required=False)
    bonus_points_awarded = serializers.IntegerField(required=False)
    redemption_id        = serializers.UUIDField(required=False)


class QRStaffScanRequestSerializer(serializers.Serializer):
    """CRM skaner — QR kodni tekshirish."""
    code = serializers.CharField(max_length=20)
    order_amount = serializers.DecimalField(
        max_digits=16, decimal_places=2, min_value=0, required=False, default=0,
    )

    def validate_code(self, value):
        return value.strip().upper()


class QRStaffScanResponseSerializer(serializers.Serializer):
    """CRM skaner — QR kod ma'lumotlari."""
    is_valid         = serializers.BooleanField()
    message          = serializers.CharField()
    code             = serializers.CharField(required=False)
    title            = serializers.CharField(required=False)
    description      = serializers.CharField(required=False)
    qr_type          = serializers.CharField(required=False)
    discount_value   = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    discount_preview = serializers.DecimalField(max_digits=16, decimal_places=2, required=False)
    remaining_uses   = serializers.IntegerField(required=False, allow_null=True)


class QRStaffRedeemRequestSerializer(QRRedeemRequestSerializer):
    """CRM skaner — chegirmani qo'llash."""
    code = serializers.CharField(max_length=20)

    def validate_code(self, value):
        return value.strip().upper()


# ─── CRM ──────────────────────────────────────────────────────────────────────

class QRCodeCRMSerializer(serializers.ModelSerializer):
    """CRM uchun QR kod — to'liq ma'lumot."""
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    branch_name       = serializers.CharField(source='branch.name', read_only=True, allow_null=True)
    is_valid          = serializers.BooleanField(read_only=True)
    scan_count        = serializers.SerializerMethodField()
    apply_count       = serializers.SerializerMethodField()
    usage_percent     = serializers.SerializerMethodField()
    remaining_uses    = serializers.SerializerMethodField()

    class Meta:
        model  = QRCode
        fields = [
            'id', 'code', 'qr_image', 'title', 'description',
            'qr_type', 'discount_value', 'max_discount_amount',
            'minimum_order_amount', 'applicable_services',
            'max_total_uses', 'max_uses_per_user', 'total_used_count',
            'valid_from', 'valid_until', 'is_active', 'is_valid',
            'organization_name', 'branch_name',
            'scan_count', 'apply_count', 'usage_percent', 'remaining_uses',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['code', 'qr_image', 'total_used_count', 'created_at', 'updated_at']

    @extend_schema_field(serializers.IntegerField())
    def get_scan_count(self, obj) -> int:
        return obj.redemptions.count()

    @extend_schema_field(serializers.IntegerField())
    def get_apply_count(self, obj) -> int:
        return obj.redemptions.filter(status='applied').count()

    @extend_schema_field(serializers.FloatField())
    def get_usage_percent(self, obj) -> float:
        if not obj.max_total_uses:
            return 0.0
        return round((obj.total_used_count / obj.max_total_uses) * 100, 1)

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_remaining_uses(self, obj) -> int | None:
        if obj.max_total_uses is None:
            return None
        return max(obj.max_total_uses - obj.total_used_count, 0)


class QRCodeCRMCreateSerializer(serializers.ModelSerializer):
    """QR kod yaratish."""
    code = serializers.CharField(max_length=20, required=False, allow_blank=True)

    class Meta:
        model  = QRCode
        fields = [
            'code', 'branch', 'title', 'description',
            'qr_type', 'discount_value', 'max_discount_amount',
            'minimum_order_amount', 'applicable_services',
            'max_total_uses', 'max_uses_per_user',
            'valid_from', 'valid_until',
        ]

    def validate_discount_value(self, value):
        if value <= 0:
            raise serializers.ValidationError('Chegirma qiymati 0 dan katta bo\'lishi kerak.')
        return value

    def validate_code(self, value):
        if not value:
            return value
        value = value.strip().upper()
        if QRCode.objects.filter(code=value).exists():
            raise serializers.ValidationError('Bu QR kod allaqachon mavjud.')
        return value


class QRCodeCRMUpdateSerializer(serializers.ModelSerializer):
    """QR kod yangilash (faqat ayrim maydonlar)."""
    class Meta:
        model  = QRCode
        fields = [
            'title', 'description', 'is_active',
            'valid_until', 'max_total_uses',
        ]


class QRRedemptionCRMSerializer(serializers.ModelSerializer):
    """CRM uchun redemption tarixi."""
    user_name    = serializers.SerializerMethodField()
    user_phone   = serializers.SerializerMethodField()
    qr_code_str  = serializers.CharField(source='qr_code.code', read_only=True)
    bonus_title  = serializers.CharField(source='qr_code.title', read_only=True)
    qr_type      = serializers.CharField(source='qr_code.qr_type', read_only=True)

    class Meta:
        model  = QRCodeRedemption
        fields = [
            'id', 'qr_code_str', 'bonus_title', 'qr_type',
            'user_name', 'user_phone', 'customer_name', 'customer_phone',
            'service_type', 'order_amount', 'discount_applied', 'final_amount',
            'status', 'rejection_reason', 'scanned_at',
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_user_name(self, obj) -> str | None:
        if obj.customer_name:
            return obj.customer_name
        return obj.user.full_name if obj.user else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_user_phone(self, obj) -> str | None:
        if obj.customer_phone:
            return obj.customer_phone
        return obj.user.phone if obj.user else None


class QRAnalyticsSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model  = QRAnalyticsSummary
        fields = [
            'date', 'scan_count', 'apply_count', 'reject_count',
            'total_discount_given', 'total_revenue_generated', 'unique_users',
        ]
