"""CRM lead notification testlari."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.booking.models import Booking, BookingStatus, RestaurantBooking, ServiceType, TourBooking
from apps.crm.models import Branch, BusinessType, Organization
from apps.notifications.models import Notification
from apps.notifications.crm import (
    get_organization_crm_recipients,
    notify_new_restaurant_lead,
    notify_new_tour_lead,
)
from apps.tours.models import TourAvailability, TourDestination, TourPackage
from apps.users.models import User, UserRole


def _make_user(phone, role=UserRole.CUSTOMER):
    user = User.objects.create(phone=phone, role=role, is_phone_verified=True)
    user.set_password('Test1234!')
    user.save()
    return user


class CRMNotificationTests(TestCase):
    def setUp(self):
        self.customer = _make_user('+998901234600')
        self.owner = _make_user('+998901234601', UserRole.OWNER_TOUR)
        self.org = Organization.objects.create(
            name='Test Travel Co',
            org_type=Organization.OrgType.TOUR_COMPANY,
            business_type=BusinessType.TRAVEL,
            owner=self.owner,
        )
        self.branch = Branch.objects.create(organization=self.org, name='HQ')
        self.staff_user = _make_user('+998901234602', UserRole.TOUR_STAFF)
        from apps.crm.models import BranchStaff
        BranchStaff.objects.create(
            user=self.staff_user,
            branch=self.branch,
            permissions=['view_bookings'],
        )

        dest = TourDestination.objects.create(
            name='Dubai', country='UAE', country_code='AE', city='Dubai',
        )
        self.package = TourPackage.objects.create(
            organization=self.org,
            destination=dest,
            title='Dubai Tour',
            description='Test tour package',
            base_price=Decimal('5000000'),
            duration_days=5,
            duration_nights=4,
        )
        self.availability = TourAvailability.objects.create(
            package=self.package,
            departure_date=timezone.now().date(),
            return_date=timezone.now().date(),
            total_seats=10,
            price_override=Decimal('5000000'),
        )

    def test_get_crm_recipients_includes_owner_and_staff(self):
        recipients = get_organization_crm_recipients(self.org)
        phones = {u.phone for u in recipients}
        self.assertIn(self.owner.phone, phones)
        self.assertIn(self.staff_user.phone, phones)

    @patch('apps.notifications.crm.send_notification.delay')
    def test_notify_new_tour_lead_creates_in_app_notifications(self, mock_delay):
        booking = Booking.objects.create(
            user=self.customer,
            service_type=ServiceType.TOUR,
            status=BookingStatus.PENDING,
            title='Dubai Tour',
            final_price=Decimal('5000000'),
        )
        tour_booking = TourBooking.objects.create(
            booking=booking,
            package=self.package,
            availability=self.availability,
            tourist_count=2,
        )

        count = notify_new_tour_lead(booking, tour_booking)
        self.assertEqual(count, 2)

        in_app = Notification.objects.filter(
            notification_type=Notification.NotificationType.NEW_LEAD,
            channel=Notification.Channel.IN_APP,
        )
        self.assertEqual(in_app.count(), 2)
        self.assertTrue(in_app.filter(user=self.owner).exists())
        self.assertTrue(in_app.filter(user=self.staff_user).exists())

    def test_notify_new_restaurant_lead(self):
        rest_owner = _make_user('+998901234603', UserRole.OWNER_RESTAURANT)
        rest_org = Organization.objects.create(
            name='Test Restoran',
            org_type=Organization.OrgType.RESTAURANT,
            business_type=BusinessType.RESTAURANT,
            owner=rest_owner,
        )
        branch = Branch.objects.create(organization=rest_org, name='Filial 1')

        booking = Booking.objects.create(
            user=self.customer,
            service_type=ServiceType.RESTAURANT,
            status=BookingStatus.PENDING,
            title='Restoran bron',
        )
        rb = RestaurantBooking.objects.create(
            booking=booking,
            branch=branch,
            reservation_at=timezone.now(),
            guest_count=4,
        )

        count = notify_new_restaurant_lead(booking, rb)
        self.assertEqual(count, 1)
        notif = Notification.objects.get(
            user=rest_owner,
            notification_type=Notification.NotificationType.NEW_LEAD,
        )
        self.assertEqual(notif.metadata['panel'], 'restaurant')
