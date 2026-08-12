"""TableTimeSlot servisi va API testlari."""

from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.booking.models import Booking, BookingStatus, RestaurantBooking, ServiceType
from apps.crm.models import Branch, BranchStaff, BusinessType, Organization, RestaurantTable, TableTimeSlot
from apps.crm_restaurant.services.table_slots import (
    generate_slots_for_table,
    release_slots_for_booking,
    reserve_slots_for_booking,
)
from apps.users.models import User, UserRole


def _crm_token(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['aud'] = user.jwt_audience
    org = user.organization
    if org:
        refresh['organization_id'] = str(org.id)
    return str(refresh.access_token)


class TableSlotServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create(
            phone='+998901234800', role=UserRole.OWNER_RESTAURANT, is_phone_verified=True,
        )
        self.org = Organization.objects.create(
            name='Slot Restoran',
            org_type=Organization.OrgType.RESTAURANT,
            business_type=BusinessType.RESTAURANT,
            owner=self.owner,
        )
        self.branch = Branch.objects.create(
            organization=self.org,
            name='Main',
            working_hours={'mon': '10:00-12:00', 'tue': '10:00-12:00', 'wed': '10:00-12:00',
                           'thu': '10:00-12:00', 'fri': '10:00-12:00', 'sat': '10:00-12:00', 'sun': '10:00-12:00'},
        )
        self.table = RestaurantTable.objects.create(
            branch=self.branch, table_number='A1', capacity=4,
        )

    def test_generate_slots_respects_working_hours(self):
        target = date(2026, 8, 10)  # Monday
        created = generate_slots_for_table(self.table, target, slot_minutes=30)
        self.assertEqual(created, 4)
        slots = TableTimeSlot.objects.filter(table=self.table, date=target)
        self.assertEqual(slots.count(), 4)
        self.assertEqual(str(slots.first().start_time), '10:00:00')

    def test_reserve_and_release_slots(self):
        target = date(2026, 8, 10)
        generate_slots_for_table(self.table, target, slot_minutes=30)

        reservation_at = timezone.make_aware(datetime(2026, 8, 10, 10, 0))
        booking = Booking.objects.create(
            user=self.owner,
            service_type=ServiceType.RESTAURANT,
            status=BookingStatus.PENDING,
            booking_date=reservation_at,
        )
        rb = RestaurantBooking.objects.create(
            booking=booking,
            branch=self.branch,
            reservation_at=reservation_at,
            guest_count=2,
            duration_minutes=60,
            table_number='A1',
        )

        reserved = reserve_slots_for_booking(rb, table=self.table)
        self.assertEqual(len(reserved), 2)
        self.assertEqual(
            TableTimeSlot.objects.filter(table=self.table, date=target, is_available=False).count(),
            2,
        )

        release_slots_for_booking(rb)
        self.assertEqual(
            TableTimeSlot.objects.filter(table=self.table, date=target, is_available=True).count(),
            4,
        )

    def test_double_booking_raises(self):
        target = date(2026, 8, 10)
        generate_slots_for_table(self.table, target, slot_minutes=30)
        reservation_at = timezone.make_aware(datetime(2026, 8, 10, 10, 0))

        booking1 = Booking.objects.create(
            user=self.owner, service_type=ServiceType.RESTAURANT,
            status=BookingStatus.PENDING, booking_date=reservation_at,
        )
        rb1 = RestaurantBooking.objects.create(
            booking=booking1, branch=self.branch, reservation_at=reservation_at,
            guest_count=2, duration_minutes=60, table_number='A1',
        )
        reserve_slots_for_booking(rb1, table=self.table)

        booking2 = Booking.objects.create(
            user=self.owner, service_type=ServiceType.RESTAURANT,
            status=BookingStatus.PENDING, booking_date=reservation_at,
        )
        rb2 = RestaurantBooking.objects.create(
            booking=booking2, branch=self.branch, reservation_at=reservation_at,
            guest_count=2, duration_minutes=60, table_number='A1',
        )
        with self.assertRaises(ValueError):
            reserve_slots_for_booking(rb2, table=self.table)


class TableSlotAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create(
            phone='+998901234810', role=UserRole.OWNER_RESTAURANT, is_phone_verified=True,
        )
        self.org = Organization.objects.create(
            name='Slot API Restoran',
            org_type=Organization.OrgType.RESTAURANT,
            business_type=BusinessType.RESTAURANT,
            owner=self.owner,
        )
        self.branch = Branch.objects.create(
            organization=self.org,
            name='Main',
            working_hours={'mon': '09:00-11:00', 'tue': '09:00-11:00', 'wed': '09:00-11:00',
                           'thu': '09:00-11:00', 'fri': '09:00-11:00', 'sat': '09:00-11:00', 'sun': '09:00-11:00'},
        )
        self.table = RestaurantTable.objects.create(
            branch=self.branch, table_number='B2', capacity=6,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')

    def test_generate_slots_endpoint(self):
        resp = self.client.post('/api/crm/restaurant/tables/slots/generate/', {
            'date': '2026-08-10',
            'slot_minutes': 30,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreater(resp.data['slots_created'], 0)

    def test_list_table_slots(self):
        self.client.post('/api/crm/restaurant/tables/slots/generate/', {
            'date': '2026-08-10',
        }, format='json')
        resp = self.client.get(f'/api/crm/restaurant/tables/{self.table.id}/slots/?date=2026-08-10')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 4)

    def test_availability_shows_booked_slots(self):
        self.client.post('/api/crm/restaurant/tables/slots/generate/', {
            'date': '2026-08-10',
        }, format='json')

        reservation_at = timezone.make_aware(datetime(2026, 8, 10, 9, 0))
        resp = self.client.post('/api/crm/restaurant/bookings/', {
            'customer_name': 'Ali Valiyev',
            'customer_phone': '+998901234811',
            'table_id': str(self.table.id),
            'reservation_at': reservation_at.isoformat(),
            'guest_count': 2,
            'duration_minutes': 60,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        avail = self.client.get('/api/crm/restaurant/tables/availability/?date=2026-08-10')
        self.assertEqual(avail.status_code, status.HTTP_200_OK)
        table_row = next(t for t in avail.data['tables'] if t['table_number'] == 'B2')
        self.assertGreater(table_row['booked_slots'], 0)

    def test_cancel_booking_releases_slots(self):
        self.client.post('/api/crm/restaurant/tables/slots/generate/', {
            'date': '2026-08-10',
        }, format='json')
        reservation_at = timezone.make_aware(datetime(2026, 8, 10, 9, 0))
        create = self.client.post('/api/crm/restaurant/bookings/', {
            'customer_name': 'Test User',
            'customer_phone': '+998901234812',
            'table_id': str(self.table.id),
            'reservation_at': reservation_at.isoformat(),
            'guest_count': 2,
            'duration_minutes': 60,
        }, format='json')
        booking_id = create.data['id']

        cancel = self.client.post(f'/api/crm/restaurant/bookings/{booking_id}/cancel/')
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(
            TableTimeSlot.objects.filter(table=self.table, date=date(2026, 8, 10), is_available=False).count(),
            0,
        )
