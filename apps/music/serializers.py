"""Background Music serializers."""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import BackgroundMusic


class BackgroundMusicSerializer(serializers.ModelSerializer):
    """Background music serializer for admin CRUD."""
    
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = BackgroundMusic
        fields = [
            'id', 'title', 'artist', 'mood', 'audio_file',
            'duration_seconds', 'file_size', 'file_size_mb',
            'is_active', 'volume', 'loop', 'fade_in_seconds',
            'fade_out_seconds', 'tags', 'description',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'file_size', 'duration_seconds', 'created_at', 'updated_at']
    
    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_file_size_mb(self, obj: BackgroundMusic) -> float | None:
        """Convert file size to MB."""
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return None
    
    def validate_audio_file(self, value):
        """Validate audio file size (50MB limit)."""
        if value and value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError('Audio file size must not exceed 50MB')
        return value
    
    def validate(self, data):
        """Ensure only one active track."""
        if data.get('is_active'):
            active_tracks = BackgroundMusic.objects.filter(is_active=True)
            if self.instance:
                active_tracks = active_tracks.exclude(id=self.instance.id)
            if active_tracks.exists():
                raise serializers.ValidationError(
                    'Only one track can be active at a time. Please deactivate other tracks first.'
                )
        return data


class BackgroundMusicUpdateSerializer(serializers.Serializer):
    """Serializer for updating volume and active status."""
    
    volume = serializers.IntegerField(
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    is_active = serializers.BooleanField(required=False)
