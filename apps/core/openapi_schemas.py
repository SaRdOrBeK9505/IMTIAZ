"""
OpenAPI (Swagger) uchun umumiy response va request serializerlari.

Faqat hujjatlashtirish maqsadida — runtime mantiq o'zgarmaydi.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.users.serializers import OrganizationBriefSerializer, UserProfileSerializer


class ErrorResponseSerializer(serializers.Serializer):
    """Standart DRF xato javobi."""
    detail = serializers.CharField(help_text='Xato tavsifi yoki xato ro\'yxati')


class MessageResponseSerializer(serializers.Serializer):
    message = serializers.CharField()


class JWTAuthResponseSerializer(serializers.Serializer):
    """Login endpointlari umumiy muvaffaqiyatli javobi."""
    success = serializers.BooleanField(help_text='So\'rov muvaffaqiyatli bajarildi')
    access = serializers.CharField(
        help_text='Access JWT. Muddati: 15 daqiqa (SIMPLE_JWT sozlamasiga qarab)',
    )
    refresh = serializers.CharField(
        help_text='Refresh JWT. Muddati: 30 kun. Logout va refresh uchun ishlatiladi',
    )
    user = UserProfileSerializer(help_text='Autentifikatsiya qilingan foydalanuvchi profili')


class DashboardStatsSerializer(serializers.Serializer):
    total_bookings_today = serializers.IntegerField()
    pending_bookings = serializers.IntegerField()
    confirmed_bookings = serializers.IntegerField()
    revenue_today = serializers.CharField(required=False, allow_null=True)


class OwnerDashboardOrganizationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    business_type = serializers.CharField()


class OwnerDashboardResponseSerializer(serializers.Serializer):
    organization = OwnerDashboardOrganizationSerializer()
    stats = DashboardStatsSerializer()
    feature_flags = serializers.DictField(
        child=serializers.BooleanField(),
        help_text='Frontend uchun vertikal funksiya kalitlari',
    )


class RestaurantOrganizationResponseSerializer(serializers.Serializer):
    organization = OrganizationBriefSerializer()
    branches = serializers.ListField(child=serializers.DictField())


class RestaurantBookingListItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    status = serializers.CharField()
    booking_date = serializers.DateTimeField(allow_null=True)
    final_price = serializers.CharField()
    customer_phone = serializers.CharField()
    customer_name = serializers.CharField()


class TravelOrganizationResponseSerializer(serializers.Serializer):
    organization = serializers.DictField()


class OTPRequestResponseSerializer(serializers.Serializer):
    detail = serializers.CharField(help_text='OTP yuborildi')
    expires_in = serializers.IntegerField(help_text='Amal qilish vaqti (soniya)')


class OTPVerifyResponseSerializer(serializers.Serializer):
    verification_token = serializers.CharField(
        help_text='CompleteRegistration uchun 15 daqiqalik imzolangan token',
    )


class LogoutResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    detail = serializers.CharField()
