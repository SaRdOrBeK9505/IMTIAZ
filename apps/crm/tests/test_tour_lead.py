"""TourLead va CRM webhook task testlari."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.crm.models import Organization, BusinessType, TourLead, TourLeadStatus
from apps.crm.tasks import send_tour_lead_to_crm
from apps.tours.models import TourDestination, TourPackage
from apps.users.models import User, UserRole


def _crm_token(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['aud'] = 'crm'
    org = user.organization
    if org:
        refresh['organization_id'] = str(org.id)
    return str(refresh.access_token)


class SendTourLeadToCrmTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create(
            phone='+998901236000', role=UserRole.OWNER_TOUR, is_phone_verified=True,
        )
        self.org = Organization.objects.create(
            name='Webhook Tour Co',
            org_type=Organization.OrgType.TOUR_COMPANY,
            business_type=BusinessType.TRAVEL,
            owner=self.owner,
            crm_webhook_url='https://partner.example.com/leads',
            crm_webhook_secret='test-secret',
        )
        dest = TourDestination.objects.create(
            organization=self.org,
            name='Dubai',
            slug='dubai-webhook',
            country='UAE',
        )
        self.package = TourPackage.objects.create(
            organization=self.org,
            destination=dest,
            title='Dubai 5 kun',
            description='Test',
            duration_days=5,
            base_price=Decimal('5000000'),
        )
        self.lead = TourLead.objects.create(
            organization=self.org,
            package=self.package,
            phone='+998901236001',
            full_name='Test Mijoz',
            passengers=2,
        )

    def test_no_webhook_keeps_lead_new(self):
        self.org.crm_webhook_url = ''
        self.org.save(update_fields=['crm_webhook_url'])

        result = send_tour_lead_to_crm(str(self.lead.id))
        self.lead.refresh_from_db()

        self.assertEqual(result['status'], 'no_webhook_configured')
        self.assertEqual(self.lead.status, TourLeadStatus.NEW)

    @patch('apps.crm.tasks.httpx.post')
    def test_successful_webhook_marks_sent(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {'ok': True}
        mock_post.return_value = mock_resp

        result = send_tour_lead_to_crm(str(self.lead.id))
        self.lead.refresh_from_db()

        self.assertEqual(result['status'], 'sent')
        self.assertEqual(self.lead.status, TourLeadStatus.SENT)
        self.assertIsNotNone(self.lead.sent_at)
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertIn('X-Signature', kwargs['headers'])

    @patch('apps.crm.tasks.httpx.post')
    def test_failed_webhook_marks_failed_after_retries(self, mock_post):
        mock_post.side_effect = Exception('Connection error')

        task = send_tour_lead_to_crm
        task.max_retries = 0
        with self.assertRaises(Exception):
            task(str(self.lead.id))

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, TourLeadStatus.FAILED)
        self.assertEqual(self.lead.retry_count, 1)


class TourLeadApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create(
            phone='+998901236010', role=UserRole.OWNER_TOUR, is_phone_verified=True,
        )
        self.org = Organization.objects.create(
            name='API Tour Co',
            org_type=Organization.OrgType.TOUR_COMPANY,
            business_type=BusinessType.TRAVEL,
            owner=self.owner,
        )
        dest = TourDestination.objects.create(
            organization=self.org,
            name='Istanbul',
            slug='istanbul-api',
            country='Turkey',
        )
        self.package = TourPackage.objects.create(
            organization=self.org,
            destination=dest,
            title='Istanbul 4 kun',
            description='Test',
            duration_days=4,
            base_price=Decimal('3000000'),
        )
        self.lead = TourLead.objects.create(
            organization=self.org,
            package=self.package,
            phone='+998901236011',
            full_name='API Test',
            status=TourLeadStatus.FAILED,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')

    def test_list_ai_leads(self):
        resp = self.client.get('/api/crm/tour/ai-leads/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['phone'], '+998901236011')

    def test_update_ai_lead_status(self):
        resp = self.client.patch(
            f'/api/crm/tour/ai-leads/{self.lead.id}/',
            {'status': 'contacted', 'note': 'Qo\'ng\'iroq qilindi'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, TourLeadStatus.CONTACTED)
        self.assertEqual(self.lead.note, 'Qo\'ng\'iroq qilindi')
