"""Banners app serializers."""

from rest_framework import serializers
from .models import Banner


class BannerSerializer(serializers.ModelSerializer):
    """Banner serializer."""
    
    class Meta:
        model = Banner
        fields = [
            'id', 'title', 'description', 'image_url', 'link',
            'order', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_link(self, value):
        """Link faqat ruxsat etilgan qiymatlardan biri bo'lishi kerak."""
        valid_links = [choice[0] for choice in Banner.LinkChoices.choices]
        if value not in valid_links:
            raise serializers.ValidationError(
                f"Link faqat quyidagi qiymatlardan biri bo'lishi kerak: {', '.join(valid_links)}"
            )
        return value
    
    def validate_title(self, value):
        """Title bo'sh bo'lmasligi kerak."""
        if not value or not value.strip():
            raise serializers.ValidationError("Название bo'sh bo'lmasligi kerak.")
        return value.strip()


class BannerCreateSerializer(serializers.ModelSerializer):
    """Banner yaratish serializer (admin uchun)."""
    
    class Meta:
        model = Banner
        fields = [
            'title', 'description', 'image_url', 'link', 'order', 'is_active'
        ]
    
    def validate_link(self, value):
        """Link faqat ruxsat etilgan qiymatlardan biri bo'lishi kerak."""
        valid_links = [choice[0] for choice in Banner.LinkChoices.choices]
        if value not in valid_links:
            raise serializers.ValidationError(
                f"Link faqat quyidagi qiymatlardan biri bo'lishi kerak: {', '.join(valid_links)}"
            )
        return value
    
    def validate_title(self, value):
        """Title bo'sh bo'lmasligi kerak."""
        if not value or not value.strip():
            raise serializers.ValidationError("Название bo'sh bo'lmasligi kerak.")
        return value.strip()


class BannerUpdateSerializer(serializers.ModelSerializer):
    """Banner yangilash serializer (admin uchun)."""
    
    class Meta:
        model = Banner
        fields = [
            'title', 'description', 'image_url', 'link', 'order', 'is_active'
        ]
    
    def validate_link(self, value):
        """Link faqat ruxsat etilgan qiymatlardan biri bo'lishi kerak."""
        valid_links = [choice[0] for choice in Banner.LinkChoices.choices]
        if value not in valid_links:
            raise serializers.ValidationError(
                f"Link faqat quyidagi qiymatlardan biri bo'lishi kerak: {', '.join(valid_links)}"
            )
        return value
    
    def validate_title(self, value):
        """Title bo'sh bo'lmasligi kerak."""
        if value and not value.strip():
            raise serializers.ValidationError("Название bo'sh bo'lmasligi kerak.")
        return value.strip() if value else value
