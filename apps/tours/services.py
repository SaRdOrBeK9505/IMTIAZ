"""
Tours app — biznes logika qatlami (Service Layer).

TourSearchService     — tur qidirish va filtrlash
TourBookingService    — bron yaratish, tasdiqlash, bekor qilish
TourVoucherService    — voaucher yaratish va boshqarish
TourAvailabilityService — mavjud joylarni boshqarish
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.db.models import QuerySet, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── TourSearchService ────────────────────────────────────────────────────────

class TourSearchService:
    """Tur paketlarini qidirish, filtrlash va saralash."""

    @staticmethod
    def search(
        *,
        destination_id:  Optional[str]     = None,
        category_id:     Optional[str]     = None,
        organization_id: Optional[str]     = None,
        departure_from:  Optional[str]     = None,   # 'YYYY-MM-DD'
        departure_to:    Optional[str]     = None,
        min_price:       Optional[Decimal] = None,
        max_price:       Optional[Decimal] = None,
        min_days:        Optional[int]     = None,
        max_days:        Optional[int]     = None,
        difficulty:      Optional[str]     = None,
        guests:          Optional[int]     = None,
        query:           Optional[str]     = None,
        is_featured:     bool              = False,
        is_exclusive:    bool              = False,
    ) -> QuerySet:
        from .models import TourPackage, TourAvailability
        qs = TourPackage.objects.filter(is_active=True).select_related(
            'organization', 'destination', 'category'
        )

        if destination_id:
            qs = qs.filter(destination_id=destination_id)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if organization_id:
            qs = qs.filter(organization_id=organization_id)
        if min_price is not None:
            qs = qs.filter(base_price__gte=min_price)
        if max_price is not None:
            qs = qs.filter(base_price__lte=max_price)
        if min_days is not None:
            qs = qs.filter(duration_days__gte=min_days)
        if max_days is not None:
            qs = qs.filter(duration_days__lte=max_days)
        if difficulty:
            qs = qs.filter(difficulty_level=difficulty)
        if is_featured:
            qs = qs.filter(is_featured=True)
        if is_exclusive:
            qs = qs.filter(is_exclusive=True)
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(short_description__icontains=query)
                | Q(destination__name__icontains=query)
                | Q(destination__country__icontains=query)
            )

        # Agar sana va joy soni berilgan bo'lsa — mavjud sanalarga filter
        if departure_from or departure_to or guests:
            avail_qs = TourAvailability.objects.filter(status='open')
            if departure_from:
                avail_qs = avail_qs.filter(departure_date__gte=departure_from)
            if departure_to:
                avail_qs = avail_qs.filter(departure_date__lte=departure_to)

            available_package_ids = avail_qs.values_list('package_id', flat=True)
            qs = qs.filter(id__in=available_package_ids)

            if guests:
                # Max guruh o'lchamidan katta bo'lmagan paketlar
                qs = qs.filter(max_group_size__gte=guests)

        return qs

    @staticmethod
    def get_available_dates(package_id: str, *, month: Optional[str] = None) -> QuerySet:
        """Paket uchun bo'sh sanalari."""
        from .models import TourAvailability
        qs = TourAvailability.objects.filter(
            package_id=package_id,
            status='open',
            departure_date__gte=timezone.now().date(),
        ).order_by('departure_date')

        if month:
            # month = 'YYYY-MM'
            try:
                year, m = map(int, month.split('-'))
                qs = qs.filter(departure_date__year=year, departure_date__month=m)
            except (ValueError, AttributeError):
                pass

        return qs


# ─── TourBookingService ───────────────────────────────────────────────────────

class TourBookingService:
    """Tur bronlarini yaratish va boshqarish."""

    @staticmethod
    @transaction.atomic
    def create_booking(
        *,
        user,
        package_id:      str,
        availability_id: str,
        tourist_count:   int,
        tourists_info:   list,
        special_requests: str = '',
        hotel_preference: str = 'any',
        created_by_ai:   bool = False,
        ai_action_log=None,
    ):
        """
        Yangi tur broni yaratadi.
        1. Mavjud joylarni tekshiradi
        2. Booking + TourBooking yaratadi
        3. booked_seats ni yangilaydi
        Returns: (Booking instance, TourBooking instance)
        """
        from apps.booking.models import Booking, TourBooking, ServiceType, BookingStatus
        from .models import TourPackage, TourAvailability

        availability = TourAvailability.objects.select_for_update().get(
            id=availability_id, package_id=package_id
        )
        package = availability.package

        if availability.status != 'open':
            raise ValueError(f'Bu sana uchun bron mavjud emas: {availability.status}')
        if availability.available_seats < tourist_count:
            raise ValueError(
                f'Yetarli joy yo\'q. Mavjud: {availability.available_seats}, '
                f'so\'ralgan: {tourist_count}'
            )

        effective_price = availability.effective_price
        final_price     = effective_price * tourist_count \
                          if package.price_per == 'person' \
                          else effective_price

        booking = Booking.objects.create(
            user           = user,
            service_type   = ServiceType.TOUR,
            status         = BookingStatus.PENDING,
            title          = f'{package.title} | {availability.departure_date}',
            description    = package.short_description,
            booking_date   = timezone.datetime.combine(
                availability.departure_date, timezone.datetime.min.time()
            ).replace(tzinfo=timezone.get_current_timezone()),
            base_price     = effective_price * tourist_count,
            final_price    = final_price,
            currency       = package.currency,
            created_by_ai  = created_by_ai,
            ai_action_log  = ai_action_log,
        )

        tour_booking = TourBooking.objects.create(
            booking          = booking,
            package          = package,
            availability     = availability,
            tourist_count    = tourist_count,
            tourists_info    = tourists_info,
            special_requests = special_requests,
            hotel_preference = hotel_preference,
        )

        # Jo'natilgan joylarni yangilash
        TourAvailability.objects.filter(id=availability_id).update(
            booked_seats=availability.booked_seats + tourist_count
        )

        logger.info(
            'TourBooking created: booking_id=%s, package=%s, user=%s',
            booking.id, package.title, user.id
        )
        return booking, tour_booking

    @staticmethod
    @transaction.atomic
    def confirm_booking(tour_booking_id: str, *, operator, operator_notes: str = ''):
        """Operator tur bronini tasdiqlaydi."""
        from apps.booking.models import TourBooking, BookingStatus

        tour_booking = TourBooking.objects.select_related(
            'booking', 'package', 'availability'
        ).get(id=tour_booking_id)

        if tour_booking.booking.status not in (
            BookingStatus.PENDING, BookingStatus.IN_PROGRESS, BookingStatus.CONFIRMED,
        ):
            raise ValueError(f'Bu bronni tasdiqlash mumkin emas: {tour_booking.booking.status}')

        tour_booking.booking.status = BookingStatus.CONFIRMED
        tour_booking.booking.save(update_fields=['status', 'updated_at'])

        tour_booking.confirmed_by   = operator
        tour_booking.confirmed_at   = timezone.now()
        tour_booking.operator_notes = operator_notes
        tour_booking.save(update_fields=['confirmed_by', 'confirmed_at', 'operator_notes', 'updated_at'])

        # Paket statistikasini yangilash
        from .models import TourPackage
        TourPackage.objects.filter(id=tour_booking.package_id).update(
            total_bookings=TourPackage.objects.get(id=tour_booking.package_id).total_bookings + 1
        )

        logger.info('TourBooking confirmed: id=%s, operator=%s', tour_booking_id, operator.id)
        return tour_booking

    @staticmethod
    @transaction.atomic
    def start_processing(tour_booking_id: str, *, operator, ai_analysis: str = ''):
        """Arizani 'Jarayonda' holatiga o'tkazadi."""
        from apps.booking.models import TourBooking, BookingStatus

        tour_booking = TourBooking.objects.select_related('booking').get(id=tour_booking_id)

        if tour_booking.booking.status != BookingStatus.PENDING:
            raise ValueError('Faqat yangi arizalar jarayonga o\'tkaziladi.')

        tour_booking.booking.status = BookingStatus.IN_PROGRESS
        tour_booking.booking.save(update_fields=['status', 'updated_at'])

        if ai_analysis:
            tour_booking.ai_analysis = ai_analysis
            tour_booking.ai_reprocessed = True
            tour_booking.save(update_fields=['ai_analysis', 'ai_reprocessed', 'updated_at'])

        logger.info('TourBooking in progress: id=%s, operator=%s', tour_booking_id, operator.id)
        return tour_booking

    @staticmethod
    @transaction.atomic
    def reject_booking(
        tour_booking_id: str,
        *,
        operator,
        rejection_reason: str,
    ):
        """Operator tur bronini rad etadi — joylar qaytariladi."""
        from apps.booking.models import TourBooking, BookingStatus
        from .models import TourAvailability

        tour_booking = TourBooking.objects.select_related('booking', 'availability').get(
            id=tour_booking_id
        )

        if tour_booking.booking.status == BookingStatus.CANCELLED:
            raise ValueError('Bu bron allaqachon bekor qilingan.')

        old_status = tour_booking.booking.status
        tour_booking.booking.status              = BookingStatus.CANCELLED
        tour_booking.booking.cancelled_at        = timezone.now()
        tour_booking.booking.cancellation_reason = rejection_reason
        tour_booking.booking.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'updated_at'])

        tour_booking.operator_notes   = operator_notes if (operator_notes := f'Rad: {rejection_reason}') else rejection_reason
        tour_booking.rejection_reason = rejection_reason
        tour_booking.save(update_fields=['rejection_reason', 'operator_notes', 'updated_at'])

        # Joylarni qaytarish — faqat avval faol holatda bo'lsa
        if old_status in (BookingStatus.PENDING, BookingStatus.IN_PROGRESS, BookingStatus.CONFIRMED):
            TourAvailability.objects.filter(id=tour_booking.availability_id).update(
                booked_seats=max(
                    tour_booking.availability.booked_seats - tour_booking.tourist_count, 0
                )
            )

        logger.info('TourBooking rejected: id=%s, reason=%s', tour_booking_id, rejection_reason)
        return tour_booking


# ─── TourVoucherService ───────────────────────────────────────────────────────

class TourVoucherService:
    """Voaucher yaratish va yuklab olish logikasi."""

    @staticmethod
    @transaction.atomic
    def generate_voucher(tour_booking_id: str, *, operator) -> 'TourVoucher':
        """
        Operator tasdiqlangan bron uchun voaucher yaratadi.
        Barcha ma'lumotlar snapshot qilinadi.
        """
        from apps.booking.models import TourBooking, BookingStatus
        from .models import TourVoucher

        tour_booking = TourBooking.objects.select_related(
            'booking__user', 'package__destination', 'availability'
        ).get(id=tour_booking_id)

        if tour_booking.booking.status != BookingStatus.CONFIRMED:
            raise ValueError('Faqat tasdiqlangan bronlar uchun voaucher yaratish mumkin.')

        if tour_booking.voucher_generated:
            # Mavjud voaucherni qaytaramiz
            return TourVoucher.objects.get(tour_booking=tour_booking)

        avail   = tour_booking.availability
        package = tour_booking.package

        # Snapshot — bron paytidagi ma'lumotlar
        package_snapshot = {
            'id':              str(package.id),
            'title':           package.title,
            'destination':     str(package.destination),
            'duration_days':   package.duration_days,
            'duration_nights': package.duration_nights,
            'inclusions':      package.inclusions,
            'exclusions':      package.exclusions,
            'organization':    package.organization.name,
            'guide_name':      avail.guide_name,
        }
        booking_snapshot = {
            'booking_id':      str(tour_booking.booking.id),
            'departure_date':  str(avail.departure_date),
            'return_date':     str(avail.return_date) if avail.return_date else None,
            'tourist_count':   tour_booking.tourist_count,
            'final_price':     str(tour_booking.booking.final_price),
            'currency':        tour_booking.booking.currency,
            'hotel_preference': tour_booking.hotel_preference,
            'special_requests': tour_booking.special_requests,
        }

        voucher = TourVoucher.objects.create(
            tour_booking     = tour_booking,
            issued_by        = operator,
            valid_from       = avail.departure_date,
            valid_until      = avail.return_date or avail.departure_date,
            package_snapshot = package_snapshot,
            tourist_snapshot = tour_booking.tourists_info,
            booking_snapshot = booking_snapshot,
        )

        # TourBooking ni yangilash
        TourBooking.objects.filter(id=tour_booking_id).update(
            voucher_generated    = True,
            voucher_generated_at = timezone.now(),
            voucher_generated_by = operator,
        )

        logger.info(
            'TourVoucher generated: %s for booking %s by operator %s',
            voucher.voucher_number, tour_booking_id, operator.id
        )
        return voucher

    @staticmethod
    def increment_download(voucher_id: str) -> None:
        """Har yuklab olinganda hisoblagich oshadi."""
        from .models import TourVoucher
        TourVoucher.objects.filter(id=voucher_id).update(
            download_count=TourVoucher.objects.get(id=voucher_id).download_count + 1
        )


# ─── TourAvailabilityService ──────────────────────────────────────────────────

class TourAvailabilityService:
    """Mavjud sanalarni boshqarish."""

    @staticmethod
    def expire_past_dates() -> int:
        """O'tib ketgan sanalarni CLOSED qilish — Celery task da ishlatiladi."""
        from .models import TourAvailability, AvailabilityStatus
        count = TourAvailability.objects.filter(
            departure_date__lt=timezone.now().date(),
            status=AvailabilityStatus.OPEN,
        ).update(status=AvailabilityStatus.CLOSED)
        logger.info('Expired %d tour availabilities', count)
        return count

    @staticmethod
    def update_package_stats(package_id: str) -> None:
        """Paket reyting va bron statistikasini yangilash."""
        from .models import TourPackage, TourReview
        from apps.booking.models import TourBooking, BookingStatus
        from django.db.models import Avg, Count

        stats = TourReview.objects.filter(
            package_id=package_id, is_published=True
        ).aggregate(avg=Avg('rating'), count=Count('id'))

        total_bookings = TourBooking.objects.filter(
            package_id=package_id,
            booking__status__in=[BookingStatus.CONFIRMED, BookingStatus.COMPLETED]
        ).count()

        TourPackage.objects.filter(id=package_id).update(
            avg_rating     = stats['avg'] or 0,
            review_count   = stats['count'] or 0,
            total_bookings = total_bookings,
        )
