"""Restoran CRM birlashtirilgan API testlari."""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
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


class RestaurantUnifiedAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create(
            phone='+998901234700', role=UserRole.OWNER_RESTAURANT, is_phone_verified=True,
        )
        self.org = Organization.objects.create(
            name='Unified Restoran',
            org_type=Organization.OrgType.RESTAURANT,
            business_type=BusinessType.RESTAURANT,
            owner=self.owner,
        )
        self.branch = Branch.objects.create(organization=self.org, name='Main')
        self.staff_user = User.objects.create(
            phone='+998901234701', role=UserRole.RESTAURANT_STAFF, is_phone_verified=True,
        )
        BranchStaff.objects.create(
            user=self.staff_user,
            branch=self.branch,
            permissions=['view_bookings', 'manage_bookings', 'view_analytics'],
        )

    def test_owner_can_access_analytics(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')
        resp = self.client.get('/api/crm/restaurant/analytics/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('total_bookings', resp.data)

    def test_staff_can_list_bookings(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.staff_user)}')
        resp = self.client.get('/api/crm/restaurant/bookings/')
        self.assertEqual(resp.status_code, 200)

    def test_staff_leaderboard_uses_restaurant_metrics(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')
        resp = self.client.get('/api/crm/restaurant/staff/leaderboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('leaderboard', resp.data)

    def test_tables_grouped_endpoint(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')
        resp = self.client.get('/api/crm/restaurant/tables/grouped/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('sections', resp.data)
