"""
Services — Serializers.

Admin serializers  → to'liq CRUD (barcha maydonlar)
Client serializers → faqat o'qish (user va CRM panel uchun)
"""

from rest_framework import serializers

from .models import Service, ServiceColor, ServiceIcon


# ─── ServiceIcon ──────────────────────────────────────────────────────────────

class ServiceIconAdminSerializer(serializers.ModelSerializer):
    """Admin — to'liq CRUD."""

    class Meta:
        model = ServiceIcon
        fields = [
            'id', 'name', 'slug', 'svg', 'image',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ServiceIconClientSerializer(serializers.ModelSerializer):
    """Client/CRM — faqat o'qish (icon tanlash uchun ro'yxat)."""

    class Meta:
        model = ServiceIcon
        fields = ['id', 'name', 'slug', 'svg', 'image']
        read_only_fields = fields


# ─── ServiceColor ─────────────────────────────────────────────────────────────

class ServiceColorAdminSerializer(serializers.ModelSerializer):
    """Admin — to'liq CRUD."""

    class Meta:
        model = ServiceColor
        fields = [
            'id', 'name', 'hex_code',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_hex_code(self, value: str) -> str:
        """Hex format tekshiruvi: #RRGGBB."""
        value = value.strip()
        if not value.startswith('#') or len(value) != 7:
            raise serializers.ValidationError(
                "Hex kod #RRGGBB formatida bo'lishi kerak (masalan: #8B5CF6)"
            )
        try:
            int(value[1:], 16)
        except ValueError:
            raise serializers.ValidationError('Hex kod noto\'g\'ri formatda.')
        return value.upper()


class ServiceColorClientSerializer(serializers.ModelSerializer):
    """Client/CRM — faqat o'qish (rang tanlash uchun ro'yxat)."""

    class Meta:
        model = ServiceColor
        fields = ['id', 'name', 'hex_code']
        read_only_fields = fields


# ─── Service ──────────────────────────────────────────────────────────────────

class ServiceAdminSerializer(serializers.ModelSerializer):
    """
    Admin — to'liq CRUD.
    Yozishda icon va color ID qabul qiladi,
    o'qishda ularning ma'lumotlarini ham qaytaradi.
    """

    icon_detail  = ServiceIconClientSerializer(source='icon',  read_only=True)
    color_detail = ServiceColorClientSerializer(source='color', read_only=True)

    class Meta:
        model = Service
        fields = [
            'id', 'name', 'slug', 'description',
            'icon', 'icon_detail',
            'color', 'color_detail',
            'is_active', 'order',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
        extra_kwargs = {
            'icon':  {'write_only': False},
            'color': {'write_only': False},
        }


class ServiceClientSerializer(serializers.ModelSerializer):
    """
    Client/CRM — faqat o'qish.
    Icon va color ma'lumotlari nested holda qaytariladi.
    """

    icon  = ServiceIconClientSerializer(read_only=True)
    color = ServiceColorClientSerializer(read_only=True)

    class Meta:
        model = Service
        fields = [
            'id', 'name', 'slug', 'description',
            'icon', 'color', 'order',
        ]
        read_only_fields = fields
