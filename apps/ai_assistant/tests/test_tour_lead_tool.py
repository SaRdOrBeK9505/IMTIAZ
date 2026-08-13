"""AI submit_tour_lead tool testlari."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.ai_assistant.tool_handlers import handle_search_tour_packages, handle_submit_tour_lead
from apps.crm.models import Organization, BusinessType, TourLead
from apps.tours.models import TourAvailability, TourDestination, TourPackage
from apps.users.models import User, UserRole


class TourLeadToolTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone='+998901237000',
            role=UserRole.CUSTOMER,
            is_phone_verified=True,
            first_name='Ali',
            last_name='Valiyev',
        )
        self.owner = User.objects.create(
            phone='+998901237001', role=UserRole.OWNER_TOUR, is_phone_verified=True,
        )
        self.org = Organization.objects.create(
            name='Tool Tour Co',
            org_type=Organization.OrgType.TOUR_COMPANY,
            business_type=BusinessType.TRAVEL,
            owner=self.owner,
        )
        dest = TourDestination.objects.create(
            organization=self.org,
            name='Samarqand',
            slug='samarqand-tool',
            country='O\'zbekiston',
        )
        self.package = TourPackage.objects.create(
            organization=self.org,
            destination=dest,
            title='Samarqand 3 kun',
            description='Test tur',
            duration_days=3,
            base_price=Decimal('1500000'),
        )
        TourAvailability.objects.create(
            package=self.package,
            departure_date=date(2026, 9, 1),
            return_date=date(2026, 9, 3),
            total_seats=20,
        )

    def test_search_tour_packages(self):
        result = handle_search_tour_packages(
            self.user, destination='Samarqand', lang='uz',
        )
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['title'], 'Samarqand 3 kun')

    def test_submit_tour_lead_invalid_phone(self):
        result = handle_submit_tour_lead(
            self.user,
            package_id=str(self.package.id),
            phone='12345',
            lang='uz',
        )
        self.assertEqual(result['status'], 'error')
        self.assertFalse(TourLead.objects.exists())

    @patch('apps.crm.tasks.send_tour_lead_to_crm.delay')
    def test_submit_tour_lead_success(self, mock_delay):
        result = handle_submit_tour_lead(
            self.user,
            package_id=str(self.package.id),
            phone='998901237002',
            full_name='Bobur',
            passengers=2,
            note='Erkak va ayol',
            lang='uz',
        )
        self.assertEqual(result['status'], 'ok')
        lead = TourLead.objects.get()
        self.assertEqual(lead.phone, '+998901237002')
        self.assertEqual(lead.full_name, 'Bobur')
        self.assertEqual(lead.passengers, 2)
        mock_delay.assert_called_once_with(str(lead.id))
