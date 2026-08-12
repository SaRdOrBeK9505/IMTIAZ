"""Mijozlar uchun yo'nalishlar API testlari."""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Branch, BusinessType, Organization
from apps.tours.models import TourCategory, TourDestination, TourPackage
from apps.users.models import User, UserRole


class TourDestinationUserAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create(
            phone='+998901235200',
            role=UserRole.OWNER_TOUR,
            is_phone_verified=True,
        )
        self.org = Organization.objects.create(
            name='Public Tur',
            org_type=Organization.OrgType.TOUR_COMPANY,
            business_type=BusinessType.TRAVEL,
            owner=self.owner,
        )
        self.branch = Branch.objects.create(organization=self.org, name='HQ')
        self.category = TourCategory.objects.create(name='Deniz', slug='deniz')
        self.dest_dubai = TourDestination.objects.create(
            organization=self.org,
            name='Dubai',
            country='BAA',
            country_code='AE',
            city='Dubai',
            description='Zamonaviy metropolis',
            is_popular=True,
        )
        self.dest_antalya = TourDestination.objects.create(
            organization=self.org,
            name='Antalya',
            country='Turkiya',
            country_code='TR',
            city='Antalya',
            description='Dengiz bo\'yi',
        )
        TourPackage.objects.create(
            organization=self.org,
            branch=self.branch,
            title='Dubai Premium',
            destination=self.dest_dubai,
            category=self.category,
            description='7 kunlik sayohat',
            duration_days=7,
            base_price=Decimal('5500000'),
        )
        TourPackage.objects.create(
            organization=self.org,
            branch=self.branch,
            title='Antalya Budget',
            destination=self.dest_antalya,
            category=self.category,
            description='5 kunlik sayohat',
            duration_days=5,
            base_price=Decimal('3200000'),
        )

    def test_list_pagination(self):
        resp = self.client.get('/api/tours/destinations/?page=1&page_size=1')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 2)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertIn('next', resp.data)

    def test_search_by_country(self):
        resp = self.client.get('/api/tours/destinations/?country=Turkiya')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['name'], 'Antalya')

    def test_filter_by_min_price(self):
        resp = self.client.get('/api/tours/destinations/?min_price=4000000')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['name'], 'Dubai')

    def test_filter_popular_only(self):
        resp = self.client.get('/api/tours/destinations/?is_popular=true')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_filters_metadata(self):
        resp = self.client.get('/api/tours/destinations/filters/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('countries', resp.data)
        self.assertIn('sort_options', resp.data)
        self.assertGreaterEqual(len(resp.data['countries']), 2)

    def test_destination_detail(self):
        resp = self.client.get(f'/api/tours/destinations/{self.dest_dubai.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['name'], 'Dubai')
        self.assertIn('featured_packages', resp.data)
        self.assertEqual(len(resp.data['featured_packages']), 1)

    def test_destination_packages(self):
        resp = self.client.get(f'/api/tours/destinations/{self.dest_dubai.id}/packages/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_ordering_price_asc(self):
        resp = self.client.get('/api/tours/destinations/?ordering=price_asc')
        self.assertEqual(resp.status_code, 200)
        names = [r['name'] for r in resp.data['results']]
        self.assertEqual(names[0], 'Antalya')
