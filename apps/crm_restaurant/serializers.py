"""Restaurant CRM serializers."""

from rest_framework import serializers

from apps.crm.models import Branch, Organization, RestaurantTable, TableStatus
from apps.crm.serializers import RestaurantTableSerializer, RestaurantTableWriteSerializer

from .models import FeaturedItem, MenuCategory, MenuItem


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
]
