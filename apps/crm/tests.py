"""Legacy CRM endpoint testlari."""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.crm.models import Branch, BranchStaff, Organization
from apps.users.models import User, UserRole


def _make_user(phone='+998901234567', role=UserRole.RESTAURANT_STAFF, password='Test1234!'):
    user = User.objects.create(
        phone=phone,
        first_name='Test',
        last_name='Staff',
        role=role,
        is_phone_verified=True,
    )
    user.set_password(password)
    user.save(update_fields=['password'])
    return user


def _crm_token(user: User) -> str:
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['aud'] = 'crm'
    return str(refresh.access_token)


class LegacyCRMAuthTests(TestCase):
    def test_deprecated_auth_returns_410(self):
        resp = APIClient().post('/api/crm/auth/')
        self.assertEqual(resp.status_code, status.HTTP_410_GONE)
        self.assertIn('login_url', resp.data)


class LegacyCRMDashboardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        owner = _make_user(phone='+998901234580', role=UserRole.OWNER_RESTAURANT)
        self.org = Organization.objects.create(
            name='Legacy Org',
            org_type=Organization.OrgType.RESTAURANT,
            owner=owner,
        )
        self.branch = Branch.objects.create(organization=self.org, name='Main')
        self.staff_user = _make_user(phone='+998901234567')
        BranchStaff.objects.create(user=self.staff_user, branch=self.branch)

    def test_dashboard_requires_crm_jwt(self):
        resp = self.client.get('/api/crm/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dashboard_with_crm_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.staff_user)}')
        resp = self.client.get('/api/crm/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('deprecated'))
        self.assertIn('migrate_to', resp.data)

    def test_mobile_token_rejected(self):
        refresh = RefreshToken.for_user(self.staff_user)
        refresh['aud'] = 'mobile'
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')
        resp = self.client.get('/api/crm/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
