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
        from django.db.models import Count, Sum, Q
        from django.utils import timezone
        from django.core.paginator import Paginator

        from apps.booking.models import Booking, BookingStatus
        from apps.crm_restaurant.models import RestaurantBookingLead
        from apps.crm.models import RestaurantTable

        today = timezone.now().date()
        branch_ids = organization.branches.filter(is_active=True).values_list('id', flat=True)
        
        # Booking statistics
        qs = Booking.objects.filter(
            restaurant_detail__branch_id__in=branch_ids,
            created_at__date=today,
        )
        
        # Lead statistics
        leads_qs = RestaurantBookingLead.objects.filter(
            restaurant__branch__in=branch_ids,
            created_at__date=today,
        )
        
        # New leads (pending) - recent leads
        new_leads = RestaurantBookingLead.objects.filter(
            restaurant__branch__in=branch_ids,
            status='pending',
        ).order_by('-created_at')[:5]
        
        # Available tables
        available_tables = RestaurantTable.objects.filter(
            branch_id__in=branch_ids,
            is_active=True,
            current_status='available',
        ).count()
        
        # QR Code statistics
        from apps.qr_codes.models import QRCode, QRCodeRedemption
        qr_codes = QRCode.objects.filter(organization=organization, is_active=True)
        qr_redemptions_today = QRCodeRedemption.objects.filter(
            qr_code__organization=organization,
            scanned_at__date=today,
        )
        
        return {
            'total_bookings_today': qs.count(),
            'pending_bookings': qs.filter(status=BookingStatus.PENDING).count(),
            'confirmed_bookings': qs.filter(status=BookingStatus.CONFIRMED).count(),
            'revenue_today': str(
                qs.filter(status=BookingStatus.CONFIRMED).aggregate(t=Sum('final_price'))['t'] or 0
            ),
            'leads': {
                'total_today': leads_qs.count(),
                'pending': leads_qs.filter(status='pending').count(),
                'accepted': leads_qs.filter(status='accepted').count(),
                'rejected': leads_qs.filter(status='rejected').count(),
                'new_leads': [
                    {
                        'id': str(lead.id),
                        'customer_name': lead.customer_name,
                        'customer_phone': lead.customer_phone,
                        'party_size': lead.party_size,
                        'preferred_time': str(lead.preferred_time),
                        'created_at': lead.created_at.isoformat(),
                    }
                    for lead in new_leads
                ]
            },
            'tables': {
                'available': available_tables,
            },
            'qr_scanner': {
                'total_qr_codes': qr_codes.count(),
                'scans_today': qr_redemptions_today.count(),
                'unique_users_today': qr_redemptions_today.values('user').distinct().count(),
                'total_discount_given_today': str(
                    qr_redemptions_today.aggregate(t=Sum('discount_applied'))['t'] or 0
                ),
            },
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
