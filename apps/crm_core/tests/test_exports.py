"""Hisobot eksport testlari."""

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.booking.models import Booking, BookingStatus, RestaurantBooking, ServiceType
from apps.crm.models import Branch, BusinessType, Organization
from apps.crm_core.exports import export_restaurant_bookings_csv
from apps.users.models import User, UserRole


def _crm_token(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['aud'] = 'crm'
    return str(refresh.access_token)


class RestaurantExportTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create(
            phone='+998901236100', role=UserRole.OWNER_RESTAURANT, is_phone_verified=True,
        )
        self.org = Organization.objects.create(
            name='Export Restoran',
            org_type=Organization.OrgType.RESTAURANT,
            business_type=BusinessType.RESTAURANT,
            owner=self.owner,
        )
        self.branch = Branch.objects.create(organization=self.org, name='Main')
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')

    def test_csv_export_contains_booking_row(self):
        customer = User.objects.create(
            phone='+998901236101', role=UserRole.CUSTOMER, is_phone_verified=True,
            first_name='Test', last_name='User',
        )
        booking = Booking.objects.create(
            user=customer,
            service_type=ServiceType.RESTAURANT,
            status=BookingStatus.CONFIRMED,
            booking_date=timezone.now(),
            final_price=100000,
        )
        RestaurantBooking.objects.create(
            booking=booking,
            branch=self.branch,
            reservation_at=timezone.now(),
            guest_count=2,
        )

        response = export_restaurant_bookings_csv(self.org, period='daily', branch=self.branch)
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('Test User', response.content.decode('utf-8'))

    def test_export_api_endpoint(self):
        analytics = self.client.get('/api/crm/restaurant/analytics/')
        self.assertEqual(analytics.status_code, 200, analytics.data)

        resp = self.client.get('/api/crm/restaurant/analytics/export/?file_format=csv')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp.content[:200]))
        self.assertIn('text/csv', resp['Content-Type'])
