"""CRM owner provisioning — faqat admin panel orqali."""

from __future__ import annotations

from django.db import transaction

from apps.crm.models import Branch, BusinessType, Organization
from apps.users.models import User, UserRole

OWNER_ROLE_BY_BUSINESS_TYPE = {
    BusinessType.RESTAURANT: UserRole.OWNER_RESTAURANT,
    BusinessType.TRAVEL: UserRole.OWNER_TOUR,
}

ORG_TYPE_BY_BUSINESS_TYPE = {
    BusinessType.RESTAURANT: Organization.OrgType.RESTAURANT,
    BusinessType.TRAVEL: Organization.OrgType.TOUR_COMPANY,
}


class OwnerProvisioningError(Exception):
    pass


def expected_owner_role(organization: Organization) -> str | None:
    return OWNER_ROLE_BY_BUSINESS_TYPE.get(organization.business_type)


def sync_owner_role_for_organization(organization: Organization) -> None:
    """Organization business_type ga mos owner rolini o'rnatadi."""
    owner = organization.owner
    role = expected_owner_role(organization)
    if not owner or not role or owner.role == role:
        return
    owner.role = role
    owner.save(update_fields=['role', 'updated_at'])


def validate_organization_owner(organization: Organization, *, exclude_pk=None) -> None:
    """Owner boshqa tashkilotga biriktirilmaganini tekshiradi."""
    owner = organization.owner
    if not owner:
        return

    qs = Organization.objects.filter(owner=owner)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise OwnerProvisioningError(
            f'{owner.phone} allaqachon boshqa tashkilot egasi.'
        )

    role = expected_owner_role(organization)
    if role and owner.role not in (role, UserRole.ADMIN):
        raise OwnerProvisioningError(
            f'Owner roli {owner.role} — {organization.business_type} uchun {role} bo\'lishi kerak.'
        )


@transaction.atomic
def provision_owner_with_organization(
    *,
    phone: str,
    password: str,
    first_name: str,
    last_name: str,
    organization_name: str,
    business_type: str,
    branch_name: str = 'Asosiy filial',
    city: str = '',
) -> tuple[User, Organization, Branch]:
    """
    Admin panel orqali yangi CRM hamkor yaratish.
    Self-service register API ishlatilmaydi.
    """
    role = OWNER_ROLE_BY_BUSINESS_TYPE.get(business_type)
    org_type = ORG_TYPE_BY_BUSINESS_TYPE.get(business_type)
    if not role or not org_type:
        raise OwnerProvisioningError(f'Noto\'g\'ri business_type: {business_type}')

    if User.objects.filter(phone=phone).exists():
        raise OwnerProvisioningError('Bu telefon raqam band.')

    user = User(
        phone=phone,
        first_name=first_name,
        last_name=last_name,
        is_phone_verified=True,
        role=role,
        is_active=True,
    )
    user.set_password(password)
    user.save()

    organization = Organization.objects.create(
        name=organization_name.strip(),
        org_type=org_type,
        business_type=business_type,
        owner=user,
        is_active=True,
    )
    branch = Branch.objects.create(
        organization=organization,
        name=branch_name.strip() or 'Asosiy filial',
        city=city.strip(),
        is_active=True,
    )
    return user, organization, branch


@transaction.atomic
def create_branch_for_owner(
    *,
    owner: User,
    name: str,
    city: str = '',
    address: str = '',
    phone: str = '',
) -> Branch:
    organization = getattr(owner, 'owned_organization', None)
    if not organization:
        raise OwnerProvisioningError('Tashkilot topilmadi.')

    return Branch.objects.create(
        organization=organization,
        name=name.strip(),
        city=city.strip(),
        address=address.strip(),
        phone=phone.strip() or None,
        is_active=True,
    )
