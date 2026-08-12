"""CRM admin provisioning testlari."""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.crm.models import BusinessType, Organization
from apps.crm_core.onboarding import (
    OwnerProvisioningError,
    provision_owner_with_organization,
    sync_owner_role_for_organization,
    validate_organization_owner,
)
from apps.users.models import User, UserRole


class CRMOwnerProvisioningTests(TestCase):
    def test_provision_owner_with_organization(self):
        user, org, branch = provision_owner_with_organization(
            phone='+998901236000',
            password='AdminPass1!',
            first_name='Rustam',
            last_name='Karimov',
            organization_name='Premium Oshxona',
            business_type=BusinessType.RESTAURANT,
            branch_name='Markaz',
            city='Tashkent',
        )
        self.assertEqual(user.role, UserRole.OWNER_RESTAURANT)
        self.assertEqual(org.owner_id, user.id)
        self.assertEqual(branch.organization_id, org.id)

    def test_duplicate_phone_rejected(self):
        provision_owner_with_organization(
            phone='+998901236001',
            password='AdminPass1!',
            first_name='A',
            last_name='B',
            organization_name='Org1',
            business_type=BusinessType.TRAVEL,
        )
        with self.assertRaises(OwnerProvisioningError):
            provision_owner_with_organization(
                phone='+998901236001',
                password='AdminPass1!',
                first_name='C',
                last_name='D',
                organization_name='Org2',
                business_type=BusinessType.TRAVEL,
            )

    def test_sync_owner_role_on_business_type_change(self):
        owner = User.objects.create(
            phone='+998901236002',
            role=UserRole.OWNER_RESTAURANT,
            is_phone_verified=True,
        )
        org = Organization.objects.create(
            name='Switch Org',
            org_type=Organization.OrgType.TOUR_COMPANY,
            business_type=BusinessType.TRAVEL,
            owner=owner,
        )
        sync_owner_role_for_organization(org)
        owner.refresh_from_db()
        self.assertEqual(owner.role, UserRole.OWNER_TOUR)

    def test_validate_owner_not_linked_twice(self):
        owner = User.objects.create(
            phone='+998901236003',
            role=UserRole.OWNER_RESTAURANT,
            is_phone_verified=True,
        )
        Organization.objects.create(
            name='First Org',
            org_type=Organization.OrgType.RESTAURANT,
            business_type=BusinessType.RESTAURANT,
            owner=owner,
        )
        second = Organization(
            name='Second Org',
            org_type=Organization.OrgType.RESTAURANT,
            business_type=BusinessType.RESTAURANT,
            owner=owner,
        )
        with self.assertRaises(OwnerProvisioningError):
            validate_organization_owner(second)


class CRMRegisterDisabledAPITests(TestCase):
    def test_register_endpoints_return_410(self):
        client = APIClient()
        for url in (
            '/api/crm/auth/register/request-otp/',
            '/api/crm/auth/register/verify-otp/',
            '/api/crm/auth/register/complete/',
        ):
            resp = client.post(url, {})
            self.assertEqual(resp.status_code, status.HTTP_410_GONE, url)
