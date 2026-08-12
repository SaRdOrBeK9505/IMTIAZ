"""
Vertical Provider Abstraction — yangi vertikal qo'shish uchun registratsiya.
AI provider patterniga o'xshash.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class VerticalConfig(ABC):
    """Har bir CRM vertikali uchun konfiguratsiya."""

    business_type: str
    url_prefix: str
    frontend_url: str
    feature_flags: dict = field(default_factory=dict)

    @abstractmethod
    def get_dashboard_stats(self, organization) -> dict:
        """Owner dashboard statistikasi."""
        ...


class RestaurantVerticalConfig(VerticalConfig):
    business_type = 'restaurant'
    url_prefix = '/api/crm/restaurant/'
    frontend_url = 'https://imtiaz-crm-restaurant.vercel.app'
    feature_flags = {
        'tables': True,
        'menu': True,
        'featured_items': True,
        'bookings': True,
    }

    def get_dashboard_stats(self, organization) -> dict:
        from django.db.models import Count, Sum
        from django.utils import timezone

        from apps.booking.models import Booking, BookingStatus

        today = timezone.now().date()
        branch_ids = organization.branches.filter(is_active=True).values_list('id', flat=True)
        qs = Booking.objects.filter(
            restaurant_detail__branch_id__in=branch_ids,
            created_at__date=today,
        )
        return {
            'total_bookings_today': qs.count(),
            'pending_bookings': qs.filter(status=BookingStatus.PENDING).count(),
            'confirmed_bookings': qs.filter(status=BookingStatus.CONFIRMED).count(),
            'revenue_today': str(
                qs.filter(status=BookingStatus.CONFIRMED).aggregate(t=Sum('final_price'))['t'] or 0
            ),
        }


class TravelVerticalConfig(VerticalConfig):
    business_type = 'travel'
    url_prefix = '/api/crm/travel/'
    frontend_url = 'https://imtiaz-crm-travel.vercel.app'
    feature_flags = {
        'tour_packages': True,
        'bookings': True,
        'vouchers': True,
    }

    def get_dashboard_stats(self, organization) -> dict:
        from django.db.models import Sum
        from django.utils import timezone

        from apps.booking.models import Booking, BookingStatus, ServiceType

        today = timezone.now().date()
        qs = Booking.objects.filter(
            service_type=ServiceType.TOUR,
            tour_detail__package__organization=organization,
            created_at__date=today,
        )
        return {
            'total_bookings_today': qs.count(),
            'pending_bookings': qs.filter(status=BookingStatus.PENDING).count(),
            'confirmed_bookings': qs.filter(status=BookingStatus.CONFIRMED).count(),
            'revenue_today': str(
                qs.filter(status=BookingStatus.CONFIRMED).aggregate(t=Sum('final_price'))['t'] or 0
            ),
        }
