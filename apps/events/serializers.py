"""Events app serializers."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import Event, EventCategory


class EventCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCategory
        fields = ['id', 'name', 'slug', 'icon']


class EventSerializer(serializers.ModelSerializer):
    category = EventCategorySerializer(read_only=True)
    venue = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'description', 'category',
            'venue', 'venue_name', 'venue_address',
            'starts_at', 'ends_at',
            'available_tickets', 'ticket_price', 'currency',
            'is_exclusive', 'status', 'cover_image', 'tags',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.DictField())
    def get_venue(self, obj) -> dict:
        if obj.branch:
            return {'name': obj.branch.name, 'address': obj.branch.address}
        return {'name': obj.venue_name, 'address': obj.venue_address}
