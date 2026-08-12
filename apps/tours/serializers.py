"""
Tours app serializers.

User-facing:
    TourCategorySerializer, TourDestinationSerializer,
    TourPackageListSerializer, TourPackageDetailSerializer,
    TourAvailabilitySerializer, TourReviewSerializer,
    TourBookingCreateSerializer, TourBookingDetailSerializer,
    TourVoucherSerializer

CRM-facing:
    TourPackageCRMSerializer, TourPackageCRMWriteSerializer,
    TourAvailabilityCRMSerializer,
    TourBookingCRMListSerializer, TourBookingCRMDetailSerializer,
    TourBookingConfirmSerializer, TourBookingRejectSerializer,
    TouristInfoSerializer
"""

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import (
    TourCategory, TourDestination, TourDestinationImage, TourPackage,
    TourItineraryDay, TourAvailability, TourVoucher, TourReview,
)
from apps.booking.models import TourBooking


# ─── Shared ───────────────────────────────────────────────────────────────────

class TouristInfoSerializer(serializers.Serializer):
    """Sayohatchi ma'lumotlari validatsiyasi."""
    name        = serializers.CharField(max_length=150)
    passport    = serializers.CharField(max_length=30)
    dob         = serializers.DateField(help_text='YYYY-MM-DD')
    nationality = serializers.CharField(max_length=3, help_text='ISO 3166-1 alpha-2')

    def validate_dob(self, value):
        if value >= timezone.now().date():
            raise serializers.ValidationError("Tug'ilgan sana kelajakda bo'lishi mumkin emas.")
        return value


# ─── User-facing: Category & Destination ──────────────────────────────────────

class TourCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = TourCategory
        fields = ['id', 'name', 'slug', 'icon', 'description', 'cover_image']


class TourDestinationImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = TourDestinationImage
        fields = ['id', 'image', 'caption', 'sort_order', 'is_cover']
        read_only_fields = ['id']


class TourDestinationSerializer(serializers.ModelSerializer):
    images = TourDestinationImageSerializer(many=True, read_only=True)
    package_count = serializers.IntegerField(read_only=True, required=False)
    min_price = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True, required=False, allow_null=True,
    )

    class Meta:
        model  = TourDestination
        fields = [
            'id', 'name', 'slug', 'country', 'country_code', 'city',
            'description', 'cover_image', 'climate_info', 'visa_info',
            'best_months', 'is_popular', 'images', 'package_count', 'min_price',
        ]


class TourDestinationListSerializer(serializers.ModelSerializer):
    """Mobil grid — yengil kartochka."""
    images = TourDestinationImageSerializer(many=True, read_only=True)
    package_count = serializers.IntegerField(read_only=True, required=False)
    min_price = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True, required=False, allow_null=True,
    )
    max_price = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True, required=False, allow_null=True,
    )
    avg_rating = serializers.DecimalField(
        max_digits=3, decimal_places=2, read_only=True, required=False, allow_null=True,
    )
    short_description = serializers.SerializerMethodField()

    class Meta:
        model = TourDestination
        fields = [
            'id', 'name', 'slug', 'country', 'country_code', 'city',
            'short_description', 'cover_image', 'is_popular',
            'images', 'package_count', 'min_price', 'max_price', 'avg_rating',
        ]

    @extend_schema_field(serializers.CharField())
    def get_short_description(self, obj) -> str:
        if not obj.description:
            return ''
        return obj.description[:180] + ('…' if len(obj.description) > 180 else '')


class TourDestinationCRMWriteSerializer(serializers.ModelSerializer):
    """CRM — yo'nalish yaratish / tahrirlash."""

    class Meta:
        model = TourDestination
        fields = [
            'name', 'country', 'country_code', 'city',
            'description', 'cover_image', 'climate_info', 'visa_info',
            'best_months', 'is_active', 'is_popular',
        ]

    def validate_best_months(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('best_months ro\'yxat bo\'lishi kerak.')
        return value


class TourDestinationCRMSerializer(serializers.ModelSerializer):
    """CRM — yo'nalish to'liq ko'rinishi."""
    images = TourDestinationImageSerializer(many=True, read_only=True)
    package_count = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()

    class Meta:
        model = TourDestination
        fields = [
            'id', 'name', 'slug', 'country', 'country_code', 'city',
            'description', 'cover_image', 'climate_info', 'visa_info',
            'best_months', 'is_active', 'is_popular',
            'images', 'package_count', 'min_price',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    @extend_schema_field(serializers.IntegerField())
    def get_package_count(self, obj) -> int:
        if getattr(obj, 'package_count', None) is not None:
            return obj.package_count
        return obj.packages.filter(is_active=True).count()

    @extend_schema_field(serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True))
    def get_min_price(self, obj):
        if getattr(obj, 'min_price', None) is not None:
            return obj.min_price
        from django.db.models import Min
        return obj.packages.filter(is_active=True).aggregate(v=Min('base_price'))['v']


class TourDestinationImageUploadSerializer(serializers.Serializer):
    """Bir yoki bir nechta rasm yuklash."""
    image = serializers.ImageField(required=False)
    caption = serializers.CharField(required=False, allow_blank=True, max_length=255)
    is_cover = serializers.BooleanField(required=False, default=False)


# ─── User-facing: TourPackage ─────────────────────────────────────────────────

class TourItineraryDaySerializer(serializers.ModelSerializer):
    class Meta:
        model  = TourItineraryDay
        fields = ['day_number', 'title', 'description', 'activities', 'accommodation', 'meals', 'image']


class TourPackageListSerializer(serializers.ModelSerializer):
    """Yengil serializer — ro'yxat ko'rinishi (karta)."""
    destination_name = serializers.CharField(source='destination.name', read_only=True)
    destination_country = serializers.CharField(source='destination.country', read_only=True)
    category_name    = serializers.CharField(source='category.name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    nearest_departure = serializers.SerializerMethodField()

    class Meta:
        model  = TourPackage
        fields = [
            'id', 'title', 'slug', 'short_description',
            'cover_image', 'destination_name', 'destination_country',
            'category_name', 'organization_name',
            'duration_days', 'duration_nights',
            'base_price', 'currency', 'price_per',
            'difficulty_level', 'is_featured', 'is_exclusive',
            'avg_rating', 'review_count', 'total_bookings',
            'nearest_departure',
        ]

    @extend_schema_field(serializers.DateField(allow_null=True))
    def get_nearest_departure(self, obj) -> str | None:
        avail = obj.availabilities.filter(
            status='open', departure_date__gte=timezone.now().date()
        ).order_by('departure_date').first()
        return str(avail.departure_date) if avail else None


class TourDestinationDetailSerializer(serializers.ModelSerializer):
    """To'liq yo'nalish — galereya + tavsiya etilgan turlar."""
    images = TourDestinationImageSerializer(many=True, read_only=True)
    package_count = serializers.IntegerField(read_only=True, required=False)
    min_price = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True, required=False, allow_null=True,
    )
    max_price = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True, required=False, allow_null=True,
    )
    avg_rating = serializers.DecimalField(
        max_digits=3, decimal_places=2, read_only=True, required=False, allow_null=True,
    )
    featured_packages = serializers.SerializerMethodField()

    class Meta:
        model = TourDestination
        fields = [
            'id', 'name', 'slug', 'country', 'country_code', 'city',
            'description', 'cover_image', 'climate_info', 'visa_info',
            'best_months', 'is_popular', 'images',
            'package_count', 'min_price', 'max_price', 'avg_rating',
            'featured_packages',
        ]

    @extend_schema_field(TourPackageListSerializer(many=True))
    def get_featured_packages(self, obj) -> list:
        from .models import TourPackage
        qs = TourPackage.objects.filter(
            destination=obj,
            is_active=True,
            organization__is_active=True,
        ).select_related('destination', 'category', 'organization').order_by(
            '-is_featured', '-avg_rating', '-total_bookings',
        )[:6]
        return TourPackageListSerializer(qs, many=True, context=self.context).data


class TourPackageDetailSerializer(serializers.ModelSerializer):
    """To'liq detail — itinerary bilan."""
    destination    = TourDestinationSerializer(read_only=True)
    category       = TourCategorySerializer(read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    itinerary_days    = TourItineraryDaySerializer(many=True, read_only=True)
    availabilities    = serializers.SerializerMethodField()

    class Meta:
        model  = TourPackage
        fields = [
            'id', 'title', 'slug', 'description', 'short_description',
            'cover_image', 'gallery',
            'destination', 'category', 'organization_name',
            'duration_days', 'duration_nights',
            'base_price', 'currency', 'price_per',
            'max_group_size', 'min_group_size',
            'inclusions', 'exclusions', 'requirements',
            'difficulty_level', 'languages_offered', 'tags',
            'is_featured', 'is_exclusive',
            'avg_rating', 'review_count', 'total_bookings',
            'itinerary_days', 'availabilities',
        ]

    @extend_schema_field(serializers.ListField())
    def get_availabilities(self, obj) -> list:
        qs = obj.availabilities.filter(
            status='open', departure_date__gte=timezone.now().date()
        ).order_by('departure_date')[:12]
        return TourAvailabilitySerializer(qs, many=True).data


class TourAvailabilitySerializer(serializers.ModelSerializer):
    available_seats   = serializers.IntegerField(read_only=True)
    effective_price   = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    occupancy_percent = serializers.FloatField(read_only=True)

    class Meta:
        model  = TourAvailability
        fields = [
            'id', 'departure_date', 'return_date',
            'total_seats', 'booked_seats', 'available_seats',
            'effective_price', 'occupancy_percent',
            'status', 'notes', 'guide_name',
        ]


class TourReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model  = TourReview
        fields = [
            'id', 'user_name', 'rating', 'title', 'comment',
            'photos', 'is_verified', 'created_at',
        ]
        read_only_fields = ['is_verified', 'is_published', 'created_at']

    @extend_schema_field(serializers.CharField())
    def get_user_name(self, obj) -> str:
        return obj.user.full_name if obj.user else 'Anonim'


class TourReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TourReview
        fields = ['rating', 'title', 'comment', 'photos']

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Reyting 1 dan 5 gacha bo\'lishi kerak.')
        return value


# ─── User-facing: TourBooking ─────────────────────────────────────────────────

class TourBookingCreateSerializer(serializers.Serializer):
    """Yangi tur broni yaratish."""
    package_id       = serializers.UUIDField()
    availability_id  = serializers.UUIDField()
    tourist_count    = serializers.IntegerField(min_value=1, max_value=50)
    tourists_info    = TouristInfoSerializer(many=True)
    special_requests = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    hotel_preference = serializers.ChoiceField(
        choices=['standard', 'deluxe', 'suite', 'any'], default='any'
    )

    def validate(self, data):
        if len(data['tourists_info']) != data['tourist_count']:
            raise serializers.ValidationError(
                'tourists_info soni tourist_count bilan mos kelishi kerak.'
            )
        return data


class TourBookingDetailSerializer(serializers.ModelSerializer):
    """Mijoz uchun bron tafsiloti — voaucher ma'lumoti bilan."""
    package_title      = serializers.CharField(source='package.title', read_only=True)
    package_cover      = serializers.ImageField(source='package.cover_image', read_only=True)
    destination        = serializers.CharField(source='package.destination.name', read_only=True)
    departure_date     = serializers.DateField(source='availability.departure_date', read_only=True)
    return_date        = serializers.DateField(source='availability.return_date', read_only=True)
    booking_status     = serializers.CharField(source='booking.status', read_only=True)
    booking_id         = serializers.UUIDField(source='booking.id', read_only=True)
    final_price        = serializers.DecimalField(source='booking.final_price', max_digits=16, decimal_places=2, read_only=True)
    currency           = serializers.CharField(source='booking.currency', read_only=True)
    created_at         = serializers.DateTimeField(source='booking.created_at', read_only=True)
    has_voucher        = serializers.BooleanField(source='voucher_generated', read_only=True)
    voucher_number     = serializers.SerializerMethodField()

    class Meta:
        model  = TourBooking
        fields = [
            'id', 'booking_id', 'booking_status',
            'package_title', 'package_cover', 'destination',
            'departure_date', 'return_date',
            'tourist_count', 'tourists_info',
            'special_requests', 'hotel_preference',
            'final_price', 'currency',
            'has_voucher', 'voucher_number',
            'rejection_reason', 'created_at',
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_voucher_number(self, obj) -> str | None:
        try:
            return obj.voucher.voucher_number
        except Exception:
            return None


class TourVoucherSerializer(serializers.ModelSerializer):
    """Voaucher detail — mijozga ko'rsatiladigan to'liq ma'lumot."""
    user_name = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()

    class Meta:
        model  = TourVoucher
        fields = [
            'id', 'voucher_number', 'status',
            'issued_at', 'valid_from', 'valid_until',
            'package_snapshot', 'tourist_snapshot', 'booking_snapshot',
            'pdf_file', 'download_count',
            'user_name', 'user_phone',
        ]

    @extend_schema_field(serializers.CharField())
    def get_user_name(self, obj) -> str:
        return obj.tour_booking.booking.user.full_name

    @extend_schema_field(serializers.CharField())
    def get_user_phone(self, obj) -> str:
        return obj.tour_booking.booking.user.phone


# ─── CRM-facing: TourPackage ──────────────────────────────────────────────────

class TourItineraryDayCRMSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TourItineraryDay
        fields = ['id', 'day_number', 'title', 'description', 'activities', 'accommodation', 'meals', 'image']


class TourPackageCRMSerializer(serializers.ModelSerializer):
    """CRM uchun to'liq paket serializer (read)."""
    destination_name   = serializers.CharField(source='destination.name', read_only=True)
    category_name      = serializers.CharField(source='category.name', read_only=True)
    itinerary_days     = TourItineraryDayCRMSerializer(many=True, read_only=True)
    total_availabilities = serializers.SerializerMethodField()
    upcoming_bookings  = serializers.SerializerMethodField()

    class Meta:
        model  = TourPackage
        fields = [
            'id', 'title', 'slug', 'short_description', 'description',
            'cover_image', 'gallery',
            'destination', 'destination_name',
            'category', 'category_name',
            'duration_days', 'duration_nights',
            'base_price', 'currency', 'price_per',
            'max_group_size', 'min_group_size',
            'inclusions', 'exclusions', 'requirements',
            'difficulty_level', 'languages_offered', 'tags',
            'is_active', 'is_featured', 'is_exclusive',
            'avg_rating', 'review_count', 'total_bookings',
            'itinerary_days', 'total_availabilities', 'upcoming_bookings',
            'created_at', 'updated_at',
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_total_availabilities(self, obj) -> int:
        return obj.availabilities.filter(status='open').count()

    @extend_schema_field(serializers.IntegerField())
    def get_upcoming_bookings(self, obj) -> int:
        from apps.booking.models import BookingStatus
        return obj.tour_bookings.filter(
            booking__status=BookingStatus.PENDING
        ).count()


class TourPackageCRMWriteSerializer(serializers.ModelSerializer):
    """CRM uchun paket yaratish/o'zgartirish."""

    class Meta:
        model  = TourPackage
        fields = [
            'title', 'category', 'destination',
            'short_description', 'description',
            'cover_image', 'gallery',
            'duration_days', 'duration_nights',
            'base_price', 'currency', 'price_per',
            'max_group_size', 'min_group_size',
            'inclusions', 'exclusions', 'requirements',
            'difficulty_level', 'languages_offered', 'tags',
            'is_active', 'is_featured',
        ]

    def validate_destination(self, value):
        request = self.context.get('request')
        if not request:
            return value
        org = request.user.organization
        if value.organization_id and value.organization_id != org.id:
            raise serializers.ValidationError('Bu yo\'nalish sizning kompaniyangizga tegishli emas.')
        if value.organization_id and not value.is_active:
            raise serializers.ValidationError('Yo\'nalish faol emas.')
        return value


class TourAvailabilityCRMSerializer(serializers.ModelSerializer):
    """CRM uchun mavjudlikni boshqarish."""
    available_seats   = serializers.IntegerField(read_only=True)
    occupancy_percent = serializers.FloatField(read_only=True)

    class Meta:
        model  = TourAvailability
        fields = [
            'id', 'departure_date', 'return_date',
            'total_seats', 'booked_seats', 'available_seats',
            'price_override', 'status', 'notes', 'guide_name',
            'occupancy_percent', 'created_at',
        ]
        read_only_fields = ['booked_seats', 'available_seats', 'occupancy_percent']


# ─── CRM-facing: TourBooking ──────────────────────────────────────────────────

class TourBookingCRMListSerializer(serializers.ModelSerializer):
    """CRM bronlar ro'yxati — asosiy ma'lumotlar."""
    booking_id       = serializers.UUIDField(source='booking.id', read_only=True)
    booking_status   = serializers.CharField(source='booking.status', read_only=True)
    status_label     = serializers.SerializerMethodField()
    final_price      = serializers.DecimalField(source='booking.final_price', max_digits=16, decimal_places=2, read_only=True)
    currency         = serializers.CharField(source='booking.currency', read_only=True)
    created_at       = serializers.DateTimeField(source='booking.created_at', read_only=True)
    created_by_ai    = serializers.BooleanField(source='booking.created_by_ai', read_only=True)
    user_name        = serializers.CharField(source='booking.user.full_name', read_only=True)
    user_phone       = serializers.CharField(source='booking.user.phone', read_only=True)
    user_email       = serializers.CharField(source='booking.user.email', read_only=True)
    user_telegram    = serializers.CharField(source='booking.user.telegram_username', read_only=True)
    package_title    = serializers.CharField(source='package.title', read_only=True)
    destination      = serializers.SerializerMethodField()
    departure_date   = serializers.DateField(source='availability.departure_date', read_only=True)
    return_date      = serializers.DateField(source='availability.return_date', read_only=True)

    class Meta:
        model  = TourBooking
        fields = [
            'id', 'booking_id', 'booking_status', 'status_label',
            'user_name', 'user_phone', 'user_email', 'user_telegram',
            'package_title', 'destination', 'departure_date', 'return_date',
            'tourist_count', 'final_price', 'currency',
            'voucher_generated', 'created_by_ai', 'ai_analysis', 'ai_reprocessed',
            'created_at',
        ]

    @extend_schema_field(serializers.CharField())
    def get_status_label(self, obj) -> str:
        labels = {
            'pending':     'Yangi',
            'in_progress': 'Jarayonda',
            'confirmed':   'Tasdiqlangan',
            'cancelled':   'Rad etilgan',
            'completed':   'Bajarilgan',
        }
        return labels.get(obj.booking.status, obj.booking.status)

    @extend_schema_field(serializers.CharField())
    def get_destination(self, obj) -> str:
        dest = obj.package.destination
        return f'{dest.name}, {dest.country}' if dest else ''


class TourBookingCRMDetailSerializer(TourBookingCRMListSerializer):
    """CRM bron tafsiloti — to'liq ma'lumot."""
    voucher_number = serializers.SerializerMethodField()

    class Meta(TourBookingCRMListSerializer.Meta):
        fields = TourBookingCRMListSerializer.Meta.fields + [
            'tourists_info', 'special_requests', 'hotel_preference',
            'confirmed_at', 'rejection_reason', 'operator_notes',
            'voucher_generated_at', 'voucher_number',
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_voucher_number(self, obj) -> str | None:
        try:
            return obj.voucher.voucher_number
        except Exception:
            return None


class TourBookingConfirmSerializer(serializers.Serializer):
    """Bronni tasdiqlash."""
    operator_notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class TourBookingRejectSerializer(serializers.Serializer):
    """Bronni rad etish."""
    rejection_reason = serializers.CharField(max_length=1000)


class TourBookingProcessSerializer(serializers.Serializer):
    """Arizani jarayonga o'tkazish."""
    ai_analysis = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class TourClientPurchaseSerializer(serializers.Serializer):
    """Mijoz xarid tarixi elementi."""
    tour_booking_id  = serializers.UUIDField()
    booking_id       = serializers.UUIDField()
    destination      = serializers.CharField()
    package_title    = serializers.CharField()
    departure_date   = serializers.DateField()
    return_date      = serializers.DateField(allow_null=True)
    tourist_count    = serializers.IntegerField()
    final_price      = serializers.DecimalField(max_digits=16, decimal_places=2)
    currency         = serializers.CharField()
    status           = serializers.CharField()
    status_label     = serializers.CharField()
    operator_name    = serializers.CharField(allow_null=True)
    confirmed_at     = serializers.DateTimeField(allow_null=True)
    voucher_number   = serializers.CharField(allow_null=True)
    has_voucher      = serializers.BooleanField()


class TourClientSerializer(serializers.Serializer):
    """Mijozlar tarixi — CRM /tours/clients sahifasi."""
    user_id          = serializers.UUIDField()
    name             = serializers.CharField()
    phone            = serializers.CharField()
    email            = serializers.CharField(allow_blank=True)
    purchase_count   = serializers.IntegerField()
    purchases        = TourClientPurchaseSerializer(many=True)
