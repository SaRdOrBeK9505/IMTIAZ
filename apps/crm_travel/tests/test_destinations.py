"""Tur yo'nalishlari CRM testlari."""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.crm.models import Branch, BranchStaff, BusinessType, Organization
from apps.tours.models import TourDestination
from apps.users.models import User, UserRole


def _crm_token(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['aud'] = user.jwt_audience
    org = user.organization
    if org:
        refresh['organization_id'] = str(org.id)
    return str(refresh.access_token)


def _fake_image(name='test.jpg'):
    return SimpleUploadedFile(name, b'fake-image-bytes', content_type='image/jpeg')


class TourDestinationCRMTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create(
            phone='+998901235100',
            role=UserRole.OWNER_TOUR,
            is_phone_verified=True,
        )
        self.org = Organization.objects.create(
            name='Dest Tur',
            org_type=Organization.OrgType.TOUR_COMPANY,
            business_type=BusinessType.TRAVEL,
            owner=self.owner,
        )
        self.branch = Branch.objects.create(organization=self.org, name='HQ')
        self.staff_user = User.objects.create(
            phone='+998901235101',
            role=UserRole.TOUR_STAFF,
            is_phone_verified=True,
        )
        BranchStaff.objects.create(
            user=self.staff_user,
            branch=self.branch,
            permissions=['manage_bookings', 'view_bookings'],
        )

    def test_owner_can_create_destination_with_images(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')
        resp = self.client.post('/api/crm/tour/destinations/', {
            'name': 'Dubai',
            'country': 'BAA',
            'country_code': 'AE',
            'city': 'Dubai',
            'description': 'Zamonaviy shahar',
            'images': [_fake_image('dubai1.jpg'), _fake_image('dubai2.jpg')],
        }, format='multipart')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['name'], 'Dubai')
        self.assertEqual(len(resp.data['images']), 2)
        dest = TourDestination.objects.get(id=resp.data['id'])
        self.assertEqual(dest.organization_id, self.org.id)

    def test_owner_can_list_destinations_grid(self):
        TourDestination.objects.create(
            organization=self.org,
            name='Istanbul',
            country='Turkiya',
            country_code='TR',
            city='Istanbul',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')
        resp = self.client.get('/api/crm/tour/destinations/grid/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_staff_can_manage_destinations(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.staff_user)}')
        resp = self.client.post('/api/crm/tour/destinations/', {
            'name': 'Antalya',
            'country': 'Turkiya',
            'city': 'Antalya',
        }, format='multipart')
        self.assertEqual(resp.status_code, 201)

    def test_soft_delete_destination(self):
        dest = TourDestination.objects.create(
            organization=self.org,
            name='Test',
            country='Testland',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_crm_token(self.owner)}')
        resp = self.client.delete(f'/api/crm/tour/destinations/{dest.id}/')
        self.assertEqual(resp.status_code, 204)
        dest.refresh_from_db()
        self.assertFalse(dest.is_active)
