"""Travel Content serializers."""

from decimal import Decimal
from rest_framework import serializers

from .models import TravelReel, CuratedTrip, CuratedTripImage


# ─── Admin — TravelReel ────────────────────────────────────────────────────
class TravelReelAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = TravelReel
        fields = [
            'id', 'title', 'subtitle', 'description', 'media_type',
            'cover_image', 'video_file', 'destination',
            'view_count', 'is_active', 'sort_order',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'view_count', 'created_at', 'updated_at']

    def validate(self, attrs):
        # Yangi obyekt yaratilayotganda cover_image majburiy
        if not self.instance and not attrs.get('cover_image'):
            raise serializers.ValidationError({'cover_image': "Cover rasm majburiy."})

        # Validate media_type and video_file consistency
        media_type = attrs.get('media_type', self.instance.media_type if self.instance else None)
        video_file = attrs.get('video_file', self.instance.video_file if self.instance else None)

        if media_type == 'video' and not video_file:
            raise serializers.ValidationError({'video_file': "media_type='video' bo'lganda video_file majburiy."})
        if media_type == 'image' and video_file:
            raise serializers.ValidationError({'video_file': "media_type='image' bo'lganda video_file bo'sh bo'lishi kerak."})
        return attrs


# ─── Client — TravelReel ───────────────────────────────────────────────────
class TravelReelListSerializer(serializers.ModelSerializer):
    """Bosh sahifadagi gorizontal scroll kartochkalar uchun (Screenshot 1)."""

    class Meta:
        model = TravelReel
        fields = ['id', 'title', 'subtitle', 'media_type', 'cover_image']


class TravelReelDetailSerializer(serializers.ModelSerializer):
    """Fullscreen reels ko'rinishi uchun (Screenshot 2) — video/rasm shu yerdan o'qiladi."""

    class Meta:
        model = TravelReel
        fields = [
            'id', 'title', 'subtitle', 'description', 'media_type',
            'cover_image', 'video_file', 'destination',
            'view_count',
        ]


# ─── Admin — CuratedTrip ───────────────────────────────────────────────────
class CuratedTripImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CuratedTripImage
        fields = ['id', 'trip', 'image', 'caption', 'sort_order']
        read_only_fields = ['id']


class CuratedTripAdminSerializer(serializers.ModelSerializer):
    gallery_images = CuratedTripImageSerializer(many=True, read_only=True)
    price_from = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))

    class Meta:
        model = CuratedTrip
        fields = [
            'id', 'title', 'subtitle', 'short_description', 'full_description',
            'cover_image', 'video_file', 'destination',
            'duration_days_min', 'duration_days_max',
            'group_size_min', 'group_size_max',
            'price_from', 'currency', 'price_unit',
            'is_verified_by_imtiaz', 'is_active', 'is_featured', 'sort_order',
            'view_count', 'gallery_images',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'view_count', 'created_at', 'updated_at']

    def validate(self, attrs):
        # Yangi obyekt yaratilayotganda video_file va cover_image MAJBURIY
        if not self.instance:
            if not attrs.get('video_file'):
                raise serializers.ValidationError({'video_file': "Video fayl majburiy — CuratedTrip video'siz yaratilmaydi."})
            if not attrs.get('cover_image'):
                raise serializers.ValidationError({'cover_image': "Cover rasm majburiy."})

        # Validate duration and group size consistency
        duration_days_min = attrs.get('duration_days_min', self.instance.duration_days_min if self.instance else None)
        duration_days_max = attrs.get('duration_days_max', self.instance.duration_days_max if self.instance else None)
        group_size_min = attrs.get('group_size_min', self.instance.group_size_min if self.instance else None)
        group_size_max = attrs.get('group_size_max', self.instance.group_size_max if self.instance else None)

        if duration_days_max and duration_days_min and duration_days_max < duration_days_min:
            raise serializers.ValidationError({'duration_days_max': "Maksimal davomiylik minimaldan kichik bo'lmasligi kerak."})
        if group_size_max and group_size_min and group_size_max < group_size_min:
            raise serializers.ValidationError({'group_size_max': "Maksimal guruh hajmi minimaldan kichik bo'lmasligi kerak."})
        return attrs


# ─── Client — CuratedTrip ──────────────────────────────────────────────────
class CuratedTripListSerializer(serializers.ModelSerializer):
    """'Путешествия IMTIAZ' gorizontal kartochkalar ro'yxati uchun (Screenshot 3, 4)."""

    duration_display = serializers.CharField(read_only=True)
    price_from = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))

    class Meta:
        model = CuratedTrip
        fields = [
            'id', 'title', 'subtitle', 'short_description', 'cover_image',
            'duration_display', 'group_size_max',
            'price_from', 'currency', 'price_unit',
            'is_verified_by_imtiaz',
        ]


class CuratedTripDetailSerializer(serializers.ModelSerializer):
    """Detail sahifa — video, to'liq matn, galereya."""

    duration_display = serializers.CharField(read_only=True)
    gallery_images = CuratedTripImageSerializer(many=True, read_only=True)
    price_from = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))

    class Meta:
        model = CuratedTrip
        fields = [
            'id', 'title', 'subtitle', 'short_description', 'full_description',
            'cover_image', 'video_file', 'destination',
            'duration_display', 'group_size_min', 'group_size_max',
            'price_from', 'currency', 'price_unit',
            'is_verified_by_imtiaz', 'gallery_images',
            'view_count',
        ]
