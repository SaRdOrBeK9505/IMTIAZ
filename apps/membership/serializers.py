"""Membership app serializers."""

from rest_framework import serializers
from .models import MembershipTier, UserMembership, WaitlistApplication, Subscription


class MembershipTierSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MembershipTier
        fields = [
            'id', 'name', 'slug', 'description', 'monthly_fee',
            'max_ai_autonomy_level', 'commission_discount_percent',
            'exclusive_events_access', 'priority_support', 'sort_order',
        ]
        read_only_fields = fields


class UserMembershipSerializer(serializers.ModelSerializer):
    tier = MembershipTierSerializer(read_only=True)

    class Meta:
        model  = UserMembership
        fields = [
            'id', 'tier',
            'max_ai_autonomy_level',
            'exclusive_events_access',
            'commission_discount_percent',
            'created_at',
        ]
        read_only_fields = fields


class WaitlistApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WaitlistApplication
        fields = ['id', 'status', 'notes', 'promo_code', 'created_at', 'reviewed_at']
        read_only_fields = ['id', 'status', 'created_at', 'reviewed_at']


class WaitlistApplySerializer(serializers.Serializer):
    notes      = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    promo_code = serializers.CharField(max_length=32,   required=False, allow_blank=True)

    def validate_promo_code(self, value: str) -> str:
        if not value:
            return value
        from .models import PromoCode
        try:
            promo = PromoCode.objects.get(code=value)
            if not promo.is_valid:
                raise serializers.ValidationError("Promo-kod yaroqsiz yoki muddati o'tgan.")
        except PromoCode.DoesNotExist:
            raise serializers.ValidationError('Promo-kod topilmadi.')
        return value


class SubscriptionSerializer(serializers.ModelSerializer):
    tier_name = serializers.CharField(source='tier.name', read_only=True)

    class Meta:
        model  = Subscription
        fields = [
            'id', 'tier_name', 'status', 'card_last_four',
            'started_at', 'current_period_end', 'created_at',
        ]
        read_only_fields = fields
