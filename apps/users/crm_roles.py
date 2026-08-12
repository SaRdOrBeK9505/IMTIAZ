"""
CRM rollari — vertikal ajratish business_type emas, User.role orqali.
Har bir kompaniya o'z owneriga ega (Organization.owner OneToOne).
"""

from __future__ import annotations

from apps.users.models import UserRole

# ─── Yangi rollar ─────────────────────────────────────────────────────────────

RESTAURANT_OWNER_ROLES = frozenset({
    UserRole.OWNER_RESTAURANT,
})

RESTAURANT_STAFF_ROLES = frozenset({
    UserRole.RESTAURANT_STAFF,
})

TOUR_OWNER_ROLES = frozenset({
    UserRole.OWNER_TOUR,
})

TOUR_STAFF_ROLES = frozenset({
    UserRole.TOUR_STAFF,
})

RESTAURANT_CRM_ROLES = RESTAURANT_OWNER_ROLES | RESTAURANT_STAFF_ROLES
TOUR_CRM_ROLES = TOUR_OWNER_ROLES | TOUR_STAFF_ROLES

CRM_ROLES = RESTAURANT_CRM_ROLES | TOUR_CRM_ROLES

# Eski rollar (migratsiyadan keyin ishlatilmaydi)
LEGACY_OWNER_ROLES = frozenset({UserRole.OWNER})
LEGACY_STAFF_ROLES = frozenset({UserRole.BRANCH_STAFF})


def is_restaurant_owner(role: str) -> bool:
    return role in RESTAURANT_OWNER_ROLES


def is_restaurant_staff(role: str) -> bool:
    return role in RESTAURANT_STAFF_ROLES


def is_tour_owner(role: str) -> bool:
    return role in TOUR_OWNER_ROLES


def is_tour_staff(role: str) -> bool:
    return role in TOUR_STAFF_ROLES


def is_crm_role(role: str) -> bool:
    return role in CRM_ROLES


def staff_role_for_owner(owner_role: str) -> str:
    """Owner roliga mos xodim roli."""
    if owner_role == UserRole.OWNER_RESTAURANT:
        return UserRole.RESTAURANT_STAFF
    if owner_role == UserRole.OWNER_TOUR:
        return UserRole.TOUR_STAFF
    raise ValueError(f'Owner roli uchun xodim roli aniqlanmadi: {owner_role}')
