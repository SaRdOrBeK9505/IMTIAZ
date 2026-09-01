"""Restaurant CRM serializers."""

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from django.core.exceptions import ValidationError

from apps.crm.models import Branch, Organization, RestaurantTable, TableStatus
from apps.crm.serializers import RestaurantTableSerializer, RestaurantTableWriteSerializer

from .models import FeaturedItem, MenuCategory, MenuItem, RestaurantBookingLead, RestaurantStaff


class OrganizationProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'description', 'logo', 'website',
            'contact_email', 'contact_phone', 'business_type',
        ]
        read_only_fields = ['id', 'business_type']


class BranchProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            'id', 'name', 'address', 'city', 'phone', 'email',
            'working_hours', 'latitude', 'longitude',
        ]
        read_only_fields = ['id']


class MenuCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuCategory
        fields = ['id', 'branch', 'name', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']


class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = MenuItem
        fields = [
            'id', 'category', 'category_name', 'name', 'description',
            'price', 'image', 'is_available', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class FeaturedItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source='menu_item.name', read_only=True, allow_null=True)

    class Meta:
        model = FeaturedItem
        fields = [
            'id', 'branch', 'menu_item', 'menu_item_name', 'custom_title',
            'order', 'active_from', 'active_until', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class TableStatusUpdateSerializer(serializers.Serializer):
    current_status = serializers.ChoiceField(choices=TableStatus.choices)


class TableSlotGenerateSerializer(serializers.Serializer):
    date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    slot_minutes = serializers.IntegerField(min_value=15, max_value=240, default=30)
    branch_id = serializers.UUIDField(required=False, allow_null=True)


class TableSlotUpdateSerializer(serializers.Serializer):
    is_available = serializers.BooleanField(required=False)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)


class BranchCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, min_length=2)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    address = serializers.CharField(required=False, allow_blank=True, default='')
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')


class RestaurantStaffSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    
    class Meta:
        model = RestaurantStaff
        fields = [
            'id', 'user', 'user_name', 'restaurant', 'restaurant_name',
            'role', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
        validators = [
            UniqueTogetherValidator(
                queryset=RestaurantStaff.objects.all(),
                fields=['user', 'restaurant'],
                message='Bu foydalanuvchi allaqachon bu restoranga biriktirilgan'
            )
        ]


class RestaurantBookingLeadSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    accepted_by_name = serializers.CharField(source='accepted_by.user.get_full_name', read_only=True, allow_null=True)
    
    class Meta:
        model = RestaurantBookingLead
        fields = [
            'id', 'restaurant', 'restaurant_name', 'customer_name', 'customer_phone',
            'party_size', 'preferred_time', 'restaurant_type', 'status',
            'accepted_by', 'accepted_by_name', 'accepted_at', 'rejection_reason',
            'actual_time', 'notes', 'special_requests', 'is_ai_generated',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'accepted_by', 'accepted_at', 'created_at', 'updated_at']
    
    def validate_party_size(self, value):
        if value < 1 or value > 20:
            raise serializers.ValidationError("Party size 1-20 oralig'ida bo'lishi kerak")
        return value
    
    def validate_preferred_time(self, value):
        """HH:MM formatni tekshirish."""
        if value:
            time_str = value.strftime('%H:%M')
            if len(time_str) != 5 or time_str[2] != ':':
                raise serializers.ValidationError("Vaqt HH:MM formatida bo'lishi kerak")
        return value
    
    def validate_actual_time(self, value):
        """Haqiqiy vaqt uchun validatsiya."""
        if value:
            time_str = value.strftime('%H:%M')
            if len(time_str) != 5 or time_str[2] != ':':
                raise serializers.ValidationError("Vaqt HH:MM formatida bo'lishi kerak")
        return value


class RestaurantBookingLeadAcceptSerializer(serializers.Serializer):
    """Lead qabul qilish uchun serializer."""
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class RestaurantBookingLeadRejectSerializer(serializers.Serializer):
    """Lead rad etish uchun serializer."""
    reason = serializers.CharField(required=True, max_length=500, help_text='Rad etish sababi')


class RestaurantBookingLeadUpdateTimeSerializer(serializers.Serializer):
    """Lead vaqtini yangilash uchun serializer (muzokara)."""
    actual_time = serializers.TimeField(required=True, help_text='Yangi vaqt (HH:MM)')


__all__ = [
    'OrganizationProfileSerializer',
    'BranchProfileSerializer',
    'MenuCategorySerializer',
    'MenuItemSerializer',
    'FeaturedItemSerializer',
    'RestaurantTableSerializer',
    'RestaurantTableWriteSerializer',
    'TableStatusUpdateSerializer',
    'TableSlotGenerateSerializer',
    'TableSlotUpdateSerializer',
    'BranchCreateSerializer',
    'RestaurantStaffSerializer',
    'RestaurantBookingLeadSerializer',
    'RestaurantBookingLeadAcceptSerializer',
    'RestaurantBookingLeadRejectSerializer',
    'RestaurantBookingLeadUpdateTimeSerializer',
]
