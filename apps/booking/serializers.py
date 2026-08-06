"""Booking app serializers."""

from rest_framework import serializers
from .models import Booking, FlightBooking, TrainBooking, RestaurantBooking, EventBooking


class FlightDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightBooking
        exclude = ['id', 'booking', 'created_at', 'updated_at']


class TrainDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainBooking
        exclude = ['id', 'booking', 'created_at', 'updated_at']


class RestaurantDetailSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = RestaurantBooking
        exclude = ['id', 'booking', 'created_at', 'updated_at']


class EventDetailSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='event.title', read_only=True)

    class Meta:
        model = EventBooking
        exclude = ['id', 'booking', 'created_at', 'updated_at']


class BookingSerializer(serializers.ModelSerializer):
    flight_detail = FlightDetailSerializer(read_only=True)
    train_detail = TrainDetailSerializer(read_only=True)
    restaurant_detail = RestaurantDetailSerializer(read_only=True)
    event_detail = EventDetailSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'service_type', 'status', 'title', 'description',
            'booking_date', 'base_price', 'discount_amount', 'final_price',
            'currency', 'external_booking_id', 'created_by_ai',
            'cancelled_at', 'cancellation_reason', 'created_at',
            'flight_detail', 'train_detail', 'restaurant_detail', 'event_detail',
        ]
        read_only_fields = fields
