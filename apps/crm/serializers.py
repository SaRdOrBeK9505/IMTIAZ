"""CRM app serializers."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import Organization, Branch, BranchStaff
from apps.booking.models import Booking, BookingStatus


class BranchSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    org_type = serializers.CharField(source='organization.org_type', read_only=True)

    class Meta:
        model = Branch
        fields = [
            'id', 'organization_name', 'org_type', 'name',
            'address', 'city', 'country', 'phone', 'email',
            'working_hours', 'capacity', 'is_active',
        ]
        read_only_fields = fields


class DashboardSerializer(serializers.Serializer):
    """CRM dashboard ma'lumotlari."""
    total_bookings_today = serializers.IntegerField()
    pending_bookings = serializers.IntegerField()
    confirmed_bookings = serializers.IntegerField()
    revenue_today = serializers.DecimalField(max_digits=14, decimal_places=2)
    branch = BranchSerializer()


class BookingCRMSerializer(serializers.ModelSerializer):
    """CRM uchun bron serializer — mijoz ma'lumotlari ham ko'rinadi."""
    user_name = serializers.SerializerMethodField()
    user_telegram = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id', 'service_type', 'status', 'title',
            'booking_date', 'final_price', 'currency',
            'created_by_ai', 'created_at',
            'user_name', 'user_telegram',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_user_name(self, obj) -> str:
        return obj.user.full_name

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_user_telegram(self, obj) -> str | None:
        return obj.user.telegram_username


class BookingStatusUpdateSerializer(serializers.Serializer):
    """Bron holatini yangilash (filial xodimi uchun)."""
    status = serializers.ChoiceField(choices=BookingStatus.choices)
    note = serializers.CharField(required=False, allow_blank=True)
