"""CRM app serializers — mavjud + yangi (RestaurantTable, Staff)."""

from drf_spectacular.utils import extend_schema_field
from decimal import Decimal
from rest_framework import serializers
from .models import (
    Organization, Branch, BranchStaff,
    RestaurantTable, TableTimeSlot,
    StaffActivityLog, StaffPerformanceSummary,
    TourLead, TourLeadStatus,
)
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
    revenue_today = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.00'))
    branch = BranchSerializer()


class BookingCRMSerializer(serializers.ModelSerializer):
    """CRM uchun bron serializer — mijoz ma'lumotlari ham ko'rinadi."""
    user_name = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()
    user_telegram = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id', 'service_type', 'status', 'title',
            'booking_date', 'final_price', 'currency',
            'created_by_ai', 'created_at',
            'user_name', 'user_phone', 'user_telegram',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_user_name(self, obj) -> str:
        return obj.user.full_name

    @extend_schema_field(serializers.CharField())
    def get_user_phone(self, obj) -> str:
        return obj.user.phone

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_user_telegram(self, obj) -> str | None:
        return obj.user.telegram_username


class RestaurantBookingCRMSerializer(BookingCRMSerializer):
    """Restoran bronlari uchun kengaytirilgan serializer."""
    table_number = serializers.CharField(source='restaurant_detail.table_number', read_only=True, allow_null=True)
    reservation_at = serializers.DateTimeField(source='restaurant_detail.reservation_at', read_only=True)
    guest_count = serializers.IntegerField(source='restaurant_detail.guest_count', read_only=True)
    duration_minutes = serializers.IntegerField(source='restaurant_detail.duration_minutes', read_only=True)
    special_requests = serializers.CharField(source='restaurant_detail.special_requests', read_only=True)
    confirmed_by_staff = serializers.BooleanField(source='restaurant_detail.confirmed_by_staff', read_only=True)

    class Meta(BookingCRMSerializer.Meta):
        fields = BookingCRMSerializer.Meta.fields + [
            'table_number', 'reservation_at', 'guest_count',
            'duration_minutes', 'special_requests', 'confirmed_by_staff',
        ]


class BookingStatusUpdateSerializer(serializers.Serializer):
    """Bron holatini yangilash (filial xodimi uchun)."""
    status = serializers.ChoiceField(choices=BookingStatus.choices)
    note = serializers.CharField(required=False, allow_blank=True)


class RestaurantBookingCreateSerializer(serializers.Serializer):
    """Yangi restoran bron yaratish — CRM /restaurant/bookings."""
    customer_name  = serializers.CharField(max_length=150)
    customer_phone = serializers.CharField(max_length=20)
    table_number   = serializers.CharField(max_length=20, required=False, allow_blank=True)
    reservation_at = serializers.DateTimeField()
    guest_count    = serializers.IntegerField(min_value=1, default=2)
    duration_minutes = serializers.IntegerField(min_value=30, default=120)
    special_requests = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    table_id       = serializers.UUIDField(required=False, allow_null=True)


# ─── RestaurantTable ──────────────────────────────────────────────────────────

class RestaurantTableSerializer(serializers.ModelSerializer):
    """Stol — read."""
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model  = RestaurantTable
        fields = [
            'id', 'branch_name', 'table_number', 'capacity', 'min_capacity',
            'section', 'description', 'is_active', 'is_vip',
            'features', 'current_status', 'status_updated_at',
            'created_at', 'updated_at',
        ]


class RestaurantTableWriteSerializer(serializers.ModelSerializer):
    """Stol — create/update."""
    class Meta:
        model  = RestaurantTable
        fields = [
            'table_number', 'capacity', 'min_capacity',
            'section', 'description', 'is_active', 'is_vip', 'features',
        ]

    def validate_capacity(self, value):
        if value < 1:
            raise serializers.ValidationError('Sig\'im kamida 1 bo\'lishi kerak.')
        return value


class TableTimeSlotSerializer(serializers.ModelSerializer):
    booking_id = serializers.SerializerMethodField()

    class Meta:
        model  = TableTimeSlot
        fields = ['id', 'date', 'start_time', 'end_time', 'is_available', 'notes', 'booking_id']

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_booking_id(self, obj):
        return str(obj.booking_id) if obj.booking_id else None


# ─── Staff ────────────────────────────────────────────────────────────────────

class StaffActivityLogSerializer(serializers.ModelSerializer):
    staff_name   = serializers.CharField(source='staff.user.full_name', read_only=True)
    staff_role   = serializers.CharField(source='staff.role', read_only=True)

    class Meta:
        model  = StaffActivityLog
        fields = [
            'id', 'staff_name', 'staff_role',
            'action_type', 'entity_type', 'entity_id',
            'description', 'metadata', 'ip_address', 'created_at',
        ]


class StaffPerformanceSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model  = StaffPerformanceSummary
        fields = [
            'period_type', 'period_start', 'period_end',
            'tour_bookings_confirmed', 'tour_bookings_rejected', 'vouchers_generated',
            'table_bookings_confirmed', 'table_bookings_cancelled',
            'total_revenue_managed', 'avg_response_time_minutes',
            'login_count', 'total_actions',
        ]


class StaffLeaderboardSerializer(serializers.ModelSerializer):
    """Xodim ro'yxati — rahbar uchun."""
    name         = serializers.CharField(source='user.full_name', read_only=True)
    phone        = serializers.CharField(source='user.phone', read_only=True)
    branch_name  = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model  = BranchStaff
        fields = [
            'id', 'name', 'phone', 'role',
            'branch_name', 'permissions', 'is_active', 'created_at',
        ]


# ─── TourLead (AI) ────────────────────────────────────────────────────────────

class TourLeadSerializer(serializers.ModelSerializer):
    package_title = serializers.CharField(source='package.title', read_only=True, allow_null=True)

    class Meta:
        model = TourLead
        fields = [
            'id', 'full_name', 'phone', 'passengers', 'preferred_departure_date',
            'note', 'status', 'package_title', 'package_id',
            'crm_response', 'sent_at', 'retry_count', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'crm_response', 'sent_at', 'retry_count', 'created_at', 'updated_at',
        ]


class TourLeadUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TourLeadStatus.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)

