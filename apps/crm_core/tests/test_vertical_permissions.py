"""CRM role-based permission testlari."""

from __future__ import annotations

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.crm.models import Branch, BranchStaff, BusinessType, Organization
from apps.users.models import User, UserRole


def _make_user(phone='+998901234567', role=UserRole.CUSTOMER, password='Test1234!'):
    user = User.objects.create(
        phone=phone,
        first_name='Test',
        last_name='User',
        role=role,
        is_phone_verified=True,
    )
    user.set_password(password)
    user.save(update_fields=['password'])
    return user


def _make_restaurant_org(owner: User) -> Organization:
    return Organization.objects.create(
        name='Test Restoran',
        org_type=Organization.OrgType.RESTAURANT,
        business_type=BusinessType.RESTAURANT,
        owner=owner,
    )


def _make_tour_org(owner: User) -> Organization:
    return Organization.objects.create(
        name='Test Travel',
        org_type=Organization.OrgType.TOUR_COMPANY,
        business_type=BusinessType.TRAVEL,
        owner=owner,
    )


def _crm_token(user: User) -> str:
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['aud'] = user.jwt_audience
    organization = user.organization
    if organization:
        refresh['organization_id'] = str(organization.id)
    return str(refresh.access_token)


class CRMLoginRoleTests(TestCase):
    url = '/api/crm/auth/login/'

    def setUp(self):
        self.client = APIClient()

    def test_owner_restaurant_login(self):
        owner = _make_user(phone='+998901234568', role=UserRole.OWNER_RESTAURANT)
        _make_restaurant_org(owner)
        resp = self.client.post(self.url, {'phone': '+998901234568', 'password': 'Test1234!'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['user']['role'], 'owner_restaurant')

    def test_legacy_owner_rejected(self):
        _make_user(phone='+998901234567', role=UserRole.OWNER)
        resp = self.client.post(self.url, {'phone': '+998901234567', 'password': 'Test1234!'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_restaurant_staff_login(self):
        owner = _make_user(phone='+998901234569', role=UserRole.OWNER_RESTAURANT)
        org = _make_restaurant_org(owner)
        branch = Branch.objects.create(organization=org, name='Main')
        staff_user = _make_user(phone='+998901234570', role=UserRole.RESTAURANT_STAFF)
        BranchStaff.objects.create(user=staff_user, branch=branch, permissions=['view_bookings'])
        resp = self.client.post(self.url, {'phone': '+998901234570', 'password': 'Test1234!'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['user']['role'], 'restaurant_staff')


class RoleIsolationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.restaurant_owner = _make_user(phone='+998901234571', role=UserRole.OWNER_RESTAURANT)
        self.tour_owner = _make_user(phone='+998901234572', role=UserRole.OWNER_TOUR)
        _make_restaurant_org(self.restaurant_owner)
        _make_tour_org(self.tour_owner)

    def test_restaurant_owner_on_restaurant_dashboard(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.restaurant_owner)}')
        resp = self.client.get('/api/crm/restaurant/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_restaurant_owner_blocked_on_tour_dashboard(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.restaurant_owner)}')
        resp = self.client.get('/api/crm/tour/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_tour_owner_blocked_on_restaurant_staff(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.tour_owner)}')
        resp = self.client.get('/api/crm/restaurant/staff/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class OwnerStaffCreationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = _make_user(phone='+998901234573', role=UserRole.OWNER_RESTAURANT)
        self.org = _make_restaurant_org(self.owner)
        self.branch = Branch.objects.create(organization=self.org, name='Filial 1')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')

    def test_owner_creates_restaurant_staff(self):
        resp = self.client.post('/api/crm/restaurant/staff/', {
            'phone': '+998901234574',
            'password': 'Staff1234!',
            'branch': str(self.branch.id),
            'permissions': ['view_bookings'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        staff_user = User.objects.get(phone='+998901234574')
        self.assertEqual(staff_user.role, UserRole.RESTAURANT_STAFF)

    def test_tour_owner_uses_tour_staff_endpoint(self):
        tour_owner = _make_user(phone='+998901234575', role=UserRole.OWNER_TOUR)
        tour_org = _make_tour_org(tour_owner)
        tour_branch = Branch.objects.create(organization=tour_org, name='Tour HQ')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(tour_owner)}')
        resp = self.client.post('/api/crm/tour/staff/', {
            'phone': '+998901234576',
            'password': 'Staff1234!',
            'branch': str(tour_branch.id),
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(phone='+998901234576').role, UserRole.TOUR_STAFF)

    def test_restaurant_owner_cannot_use_tour_staff_endpoint(self):
        resp = self.client.post('/api/crm/tour/staff/', {
            'phone': '+998901234577',
            'password': 'Staff1234!',
            'branch': str(self.branch.id),
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
