"""Tur CRM birlashtirilgan API testlari."""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.crm.models import Branch, BranchStaff, BusinessType, Organization
from apps.users.models import User, UserRole


def _crm_token(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['aud'] = user.jwt_audience
    org = user.organization
    if org:
        refresh['organization_id'] = str(org.id)
    return str(refresh.access_token)


class TourUnifiedAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create(
            phone='+998901235000',
            role=UserRole.OWNER_TOUR,
            is_phone_verified=True,
        )
        self.org = Organization.objects.create(
            name='Unified Tur',
            org_type=Organization.OrgType.TOUR_COMPANY,
            business_type=BusinessType.TRAVEL,
            owner=self.owner,
        )
        self.branch = Branch.objects.create(organization=self.org, name='Tour HQ')
        self.staff_user = User.objects.create(
            phone='+998901235001',
            role=UserRole.TOUR_STAFF,
            is_phone_verified=True,
        )
        BranchStaff.objects.create(
            user=self.staff_user,
            branch=self.branch,
            permissions=['view_bookings', 'manage_bookings', 'view_analytics'],
        )

    def test_owner_can_access_unified_packages(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')
        resp = self.client.get('/api/crm/tour/packages/')
        self.assertEqual(resp.status_code, 200)

    def test_staff_can_access_legacy_dashboard(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.staff_user)}')
        resp = self.client.get('/api/crm/tours/dashboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('total_packages', resp.data)

    def test_staff_can_access_unified_overview(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.staff_user)}')
        resp = self.client.get('/api/crm/tour/overview/')
        self.assertEqual(resp.status_code, 200)

    def test_owner_dashboard_is_owner_only_path(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')
        resp = self.client.get('/api/crm/tour/dashboard/')
        self.assertEqual(resp.status_code, 200)

    def test_staff_blocked_on_owner_dashboard(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.staff_user)}')
        resp = self.client.get('/api/crm/tour/dashboard/')
        self.assertEqual(resp.status_code, 403)

    def test_restaurant_owner_blocked_on_tour_packages(self):
        rest_owner = User.objects.create(
            phone='+998901235002',
            role=UserRole.OWNER_RESTAURANT,
            is_phone_verified=True,
        )
        Organization.objects.create(
            name='Restoran',
            org_type=Organization.OrgType.RESTAURANT,
            business_type=BusinessType.RESTAURANT,
            owner=rest_owner,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(rest_owner)}')
        resp = self.client.get('/api/crm/tour/packages/')
        self.assertEqual(resp.status_code, 403)
