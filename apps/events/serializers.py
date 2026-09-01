"""Events app serializers."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import Event, EventCategory, EventRegistration


class EventCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCategory
        fields = ['id', 'name', 'slug', 'icon']


class EventSerializer(serializers.ModelSerializer):
    category = EventCategorySerializer(read_only=True)
    venue = serializers.SerializerMethodField()
    registration_count = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'description', 'category',
            'venue', 'venue_name', 'venue_address',
            'starts_at', 'ends_at',
            'total_capacity', 'available_tickets', 'ticket_price', 'currency',
            'is_exclusive', 'status', 'cover_image', 'tags', 'registration_count',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.DictField())
    def get_venue(self, obj: Event) -> dict:
        if obj.branch:
            return {'name': obj.branch.name, 'address': obj.branch.address}
        return {'name': obj.venue_name, 'address': obj.venue_address}
    
    @extend_schema_field(serializers.IntegerField())
    def get_registration_count(self, obj: Event) -> int:
        """Get total confirmed registrations."""
        return obj.registrations.filter(status=EventRegistration.Status.CONFIRMED).count()


class EventRegistrationSerializer(serializers.ModelSerializer):
    """Event registration serializer for users."""
    
    event_title = serializers.CharField(source='event.title', read_only=True)
    event_starts_at = serializers.DateTimeField(source='event.starts_at', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = EventRegistration
        fields = [
            'id', 'event', 'event_title', 'event_starts_at',
            'user', 'user_name', 'ticket_count', 'total_price',
            'status', 'booking_reference', 'special_requests',
            'checked_in_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_price', 'booking_reference', 'created_at', 'updated_at']
    
    def validate_ticket_count(self, value):
        """Validate ticket count against event capacity."""
        event = self.context.get('event')
        if event and event.available_tickets < value:
            raise serializers.ValidationError(
                f'Yetarli chipta yo\'q. Qolgan: {event.available_tickets}'
            )
        return value


class EventRegistrationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating event registrations."""
    
    class Meta:
        model = EventRegistration
        fields = ['event', 'ticket_count', 'special_requests']
    
    def validate_ticket_count(self, value):
        """Validate ticket count (1-10)."""
        if value < 1 or value > 10:
            raise serializers.ValidationError('Chipta soni 1-10 oralig\'ida bo\'lishi kerak')
        return value
