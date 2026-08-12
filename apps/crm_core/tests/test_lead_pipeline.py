"""CRM lead pipeline testlari."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.booking.models import Booking, BookingStatus, RestaurantBooking, ServiceType, TourBooking
from apps.crm.models import Branch, BusinessType, Organization
from apps.crm_core.models import Lead
from apps.crm_core.services.leads import create_lead_from_restaurant_booking, create_lead_from_tour_booking
from apps.notifications.crm import notify_new_restaurant_lead, notify_new_tour_lead
from apps.tours.models import TourAvailability, TourDestination, TourPackage
from apps.users.models import User, UserRole


def _crm_token(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['aud'] = 'crm'
    org = user.organization
    if org:
        refresh['organization_id'] = str(org.id)
    return str(refresh.access_token)


class LeadPipelineTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create(
            phone='+998901235000', role=UserRole.OWNER_RESTAURANT, is_phone_verified=True,
            first_name='Owner', last_name='Test',
        )
        self.org = Organization.objects.create(
            name='Lead Restoran',
            org_type=Organization.OrgType.RESTAURANT,
            business_type=BusinessType.RESTAURANT,
            owner=self.owner,
        )
        self.branch = Branch.objects.create(organization=self.org, name='Main')
        self.customer = User.objects.create(
            phone='+998901235001', role=UserRole.CUSTOMER, is_phone_verified=True,
            first_name='Mijoz', last_name='Ali',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')

    def _restaurant_booking(self):
        reservation_at = timezone.now()
        booking = Booking.objects.create(
            user=self.customer,
            service_type=ServiceType.RESTAURANT,
            status=BookingStatus.PENDING,
            booking_date=reservation_at,
        )
        rb = RestaurantBooking.objects.create(
            booking=booking,
            branch=self.branch,
            reservation_at=reservation_at,
            guest_count=2,
        )
        return booking, rb

    def test_create_lead_from_restaurant_booking(self):
        booking, rb = self._restaurant_booking()
        lead = create_lead_from_restaurant_booking(booking, rb)
        self.assertEqual(lead.stage, Lead.Stage.NEW)
        self.assertEqual(lead.vertical, Lead.Vertical.RESTAURANT)
        self.assertEqual(lead.customer_phone, self.customer.phone)

    @patch('apps.notifications.tasks.send_notification.delay')
    def test_notify_creates_lead(self, _mock):
        booking, rb = self._restaurant_booking()
        notify_new_restaurant_lead(booking, rb)
        self.assertTrue(Lead.objects.filter(booking=booking).exists())

    def test_lead_kanban_api(self):
        booking, rb = self._restaurant_booking()
        create_lead_from_restaurant_booking(booking, rb)

        resp = self.client.get('/api/crm/restaurant/leads/kanban/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['total'], 1)
        new_stage = next(s for s in resp.data['stages'] if s['stage'] == 'new')
        self.assertEqual(new_stage['count'], 1)

    def test_lead_stage_update(self):
        booking, rb = self._restaurant_booking()
        lead = create_lead_from_restaurant_booking(booking, rb)

        resp = self.client.patch(f'/api/crm/restaurant/leads/{lead.id}/', {
            'stage': 'contacted',
            'notes': 'Qo\'ng\'iroq qilindi',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, Lead.Stage.CONTACTED)
        self.assertEqual(lead.notes, 'Qo\'ng\'iroq qilindi')

    def test_booking_confirm_marks_lead_won(self):
        booking, rb = self._restaurant_booking()
        lead = create_lead_from_restaurant_booking(booking, rb)

        confirm = self.client.post(f'/api/crm/restaurant/bookings/{booking.id}/confirm/')
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, Lead.Stage.WON)
        self.assertIsNotNone(lead.closed_at)


class TourLeadPipelineTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create(
            phone='+998901235010', role=UserRole.OWNER_TOUR, is_phone_verified=True,
        )
        self.org = Organization.objects.create(
            name='Lead Tour',
            org_type=Organization.OrgType.TOUR_COMPANY,
            business_type=BusinessType.TRAVEL,
            owner=self.owner,
        )
        self.customer = User.objects.create(
            phone='+998901235011', role=UserRole.CUSTOMER, is_phone_verified=True,
            first_name='Sayyoh', last_name='Vali',
        )
        dest = TourDestination.objects.create(
            organization=self.org,
            name='Samarqand',
            slug='samarqand-lead',
            country='O\'zbekiston',
        )
        self.package = TourPackage.objects.create(
            organization=self.org,
            destination=dest,
            title='Samarqand 3 kun',
            description='Test tur',
            duration_days=3,
            base_price=Decimal('1500000'),
            currency='UZS',
        )
        self.availability = TourAvailability.objects.create(
            package=self.package,
            departure_date=date(2026, 9, 1),
            return_date=date(2026, 9, 3),
            total_seats=20,
            booked_seats=0,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')

    @patch('apps.notifications.tasks.send_notification.delay')
    def test_tour_notify_creates_lead(self, _mock):
        booking = Booking.objects.create(
            user=self.customer,
            service_type=ServiceType.TOUR,
            status=BookingStatus.PENDING,
            final_price=Decimal('3000000'),
            currency='UZS',
        )
        tb = TourBooking.objects.create(
            booking=booking,
            package=self.package,
            availability=self.availability,
            tourist_count=2,
        )
        notify_new_tour_lead(booking, tb)
        lead = Lead.objects.get(booking=booking)
        self.assertEqual(lead.vertical, Lead.Vertical.TRAVEL)

    def test_tour_leads_list(self):
        booking = Booking.objects.create(
            user=self.customer, service_type=ServiceType.TOUR, status=BookingStatus.PENDING,
        )
        tb = TourBooking.objects.create(
            booking=booking, package=self.package, availability=self.availability, tourist_count=2,
        )
        create_lead_from_tour_booking(booking, tb)

        resp = self.client.get('/api/crm/tour/leads/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 1)
