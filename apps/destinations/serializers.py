"""Destination serializers."""

from rest_framework import serializers
from .models import Country, Destination, DestinationImage


class CountrySerializer(serializers.ModelSerializer):
    """Country serializer for admin CRUD."""
    
    class Meta:
        model = Country
        fields = [
            'id', 'name', 'name_uz', 'code', 'flag_emoji',
            'currency', 'calling_code', 'is_active', 'order',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DestinationImageSerializer(serializers.ModelSerializer):
    """Destination image serializer."""
    
    class Meta:
        model = DestinationImage
        fields = [
            'id', 'destination', 'image', 'caption', 'caption_uz',
            'is_primary', 'order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DestinationSerializer(serializers.ModelSerializer):
    """Destination serializer for admin CRUD."""
    
    country_name = serializers.CharField(source='country.name', read_only=True)
    images = DestinationImageSerializer(many=True, read_only=True)
    
    class Meta:
        model = Destination
        fields = [
            'id', 'country', 'country_name', 'name', 'name_uz',
            'description', 'description_uz', 'category',
            'latitude', 'longitude', 'rating', 'review_count',
            'is_popular', 'is_active', 'featured_image',
            'images', 'order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'rating', 'review_count', 'created_at', 'updated_at']


class DestinationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for destination lists."""
    
    country_name = serializers.CharField(source='country.name', read_only=True)
    country_code = serializers.CharField(source='country.code', read_only=True)
    country_flag = serializers.CharField(source='country.flag_emoji', read_only=True)
    
    class Meta:
        model = Destination
        fields = [
            'id', 'name', 'name_uz', 'country_name', 'country_code',
            'country_flag', 'category', 'rating', 'review_count',
            'is_popular', 'featured_image'
        ]


class CountryWithDestinationsSerializer(serializers.ModelSerializer):
    """Country serializer with popular destinations."""
    
    popular_destinations = serializers.SerializerMethodField()
    
    class Meta:
        model = Country
        fields = [
            'id', 'name', 'name_uz', 'code', 'flag_emoji',
            'currency', 'calling_code', 'is_active',
            'popular_destinations'
        ]
    
    def get_popular_destinations(self, obj):
        """Get popular destinations for this country."""
        destinations = obj.destinations.filter(is_popular=True, is_active=True)[:5]
        return DestinationListSerializer(destinations, many=True).data
