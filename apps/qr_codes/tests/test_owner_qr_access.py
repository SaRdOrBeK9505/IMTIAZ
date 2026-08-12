"""Owner va staff uchun QR CRM kirish testlari."""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.crm.models import Branch, BranchStaff, BusinessType, Organization
from apps.qr_codes.models import QRCode, QRCodeType
from apps.users.models import User, UserRole


def _crm_token(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['aud'] = user.jwt_audience
    org = user.organization
    if org:
        refresh['organization_id'] = str(org.id)
    return str(refresh.access_token)


class RestaurantOwnerQRAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create(
            phone='+998901234800',
            role=UserRole.OWNER_RESTAURANT,
            is_phone_verified=True,
        )
        self.org = Organization.objects.create(
            name='QR Restoran',
            org_type=Organization.OrgType.RESTAURANT,
            business_type=BusinessType.RESTAURANT,
            owner=self.owner,
        )
        self.branch = Branch.objects.create(organization=self.org, name='Main')
        self.staff_user = User.objects.create(
            phone='+998901234801',
            role=UserRole.RESTAURANT_STAFF,
            is_phone_verified=True,
        )
        BranchStaff.objects.create(
            user=self.staff_user,
            branch=self.branch,
            permissions=['view_analytics', 'manage_bookings'],
        )
        self.qr = QRCode.objects.create(
            organization=self.org,
            title='Test chegirma',
            qr_type=QRCodeType.DISCOUNT_PERCENT,
            discount_value=Decimal('10'),
            created_by=self.owner,
        )

    def test_owner_can_list_qr_via_restaurant_namespace(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')
        resp = self.client.get('/api/crm/restaurant/qr/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_owner_can_list_qr_via_legacy_namespace(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')
        resp = self.client.get('/api/crm/qr/')
        self.assertEqual(resp.status_code, 200)

    @patch('apps.qr_codes.views.QRGeneratorService.generate_qr_image')
    def test_owner_can_create_qr(self, mock_generate):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')
        resp = self.client.post('/api/crm/restaurant/qr/', {
            'title': 'Yangi bonus',
            'qr_type': QRCodeType.DISCOUNT_FIXED,
            'discount_value': '25000',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['title'], 'Yangi bonus')
        mock_generate.assert_called_once()

    def test_owner_can_access_qr_analytics(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')
        resp = self.client.get('/api/crm/restaurant/qr/analytics/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('totals', resp.data)

    def test_staff_with_view_analytics_can_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.staff_user)}')
        resp = self.client.get('/api/crm/restaurant/qr/')
        self.assertEqual(resp.status_code, 200)

    def test_staff_without_permissions_denied(self):
        limited = User.objects.create(
            phone='+998901234802',
            role=UserRole.RESTAURANT_STAFF,
            is_phone_verified=True,
        )
        BranchStaff.objects.create(
            user=limited,
            branch=self.branch,
            permissions=['view_bookings'],
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(limited)}')
        resp = self.client.get('/api/crm/restaurant/qr/')
        self.assertEqual(resp.status_code, 403)

    def test_tour_owner_cannot_access_restaurant_qr(self):
        tour_owner = User.objects.create(
            phone='+998901234803',
            role=UserRole.OWNER_TOUR,
            is_phone_verified=True,
        )
        Organization.objects.create(
            name='Tur kompaniya',
            org_type=Organization.OrgType.TOUR,
            business_type=BusinessType.TOUR,
            owner=tour_owner,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(tour_owner)}')
        resp = self.client.get('/api/crm/restaurant/qr/')
        self.assertEqual(resp.status_code, 403)
