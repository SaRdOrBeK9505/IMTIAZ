"""
Core permissions — loyiha bo'ylab qayta ishlatiladigan DRF permission sinflari.
CRM kirish User.role orqali (owner_restaurant, restaurant_staff, owner_tour, tour_staff).
"""

from rest_framework.permissions import BasePermission

from apps.users.crm_roles import (
    RESTAURANT_CRM_ROLES,
    RESTAURANT_OWNER_ROLES,
    RESTAURANT_STAFF_ROLES,
    TOUR_CRM_ROLES,
    TOUR_OWNER_ROLES,
    TOUR_STAFF_ROLES,
    is_crm_role,
)


class HasApprovedMembership(BasePermission):
    """
    Faqat waitlist holati 'approved' bo'lgan foydalanuvchilarga
    bron va AI xizmatlaridan foydalanishga ruxsat beradi.
    """
    message = 'Siz hali a\'zolikka qabul qilinmagansiz. Faqat ko\'rish rejimi mavjud.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        try:
            return request.user.waitlist_application.status == 'approved'
        except Exception:
            return False


def _active_organization(user):
    organization = user.organization
    if not organization or not organization.is_active:
        return None
    return organization


def _owner_owns_organization(user) -> bool:
    organization = _active_organization(user)
    return bool(organization and organization.owner_id == user.pk)


# ─── Restoran CRM ─────────────────────────────────────────────────────────────

class IsRestaurantOwner(BasePermission):
    """Faqat owner_restaurant — o'z kompaniyasi doirasida."""
    message = 'Bu amal faqat restoran egasi uchun.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role not in RESTAURANT_OWNER_ROLES:
            return False
        return _owner_owns_organization(request.user)


class IsRestaurantStaff(BasePermission):
    """Faqat restaurant_staff — owner tomonidan qo'shilgan xodim."""
    message = 'Siz restoran xodimi emassiz.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role not in RESTAURANT_STAFF_ROLES:
            return False
        profile = getattr(request.user, 'branch_staff_profile', None)
        return bool(
            profile
            and profile.is_active
            and _active_organization(request.user)
        )


class IsRestaurantCRMUser(BasePermission):
    """Restoran CRM: owner_restaurant yoki restaurant_staff."""
    message = 'Restoran CRM paneliga kirish huquqi yo\'q.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role not in RESTAURANT_CRM_ROLES:
            return False
        if request.user.role in RESTAURANT_OWNER_ROLES:
            return _owner_owns_organization(request.user)
        profile = getattr(request.user, 'branch_staff_profile', None)
        return bool(profile and profile.is_active and _active_organization(request.user))


# ─── Tur CRM ──────────────────────────────────────────────────────────────────

class IsTourOwner(BasePermission):
    """Faqat owner_tour — o'z kompaniyasi doirasida."""
    message = 'Bu amal faqat tur kompaniyasi egasi uchun.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role not in TOUR_OWNER_ROLES:
            return False
        return _owner_owns_organization(request.user)


class IsTourStaff(BasePermission):
    """Faqat tour_staff."""
    message = 'Siz tur kompaniyasi xodimi emassiz.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role not in TOUR_STAFF_ROLES:
            return False
        profile = getattr(request.user, 'branch_staff_profile', None)
        return bool(
            profile
            and profile.is_active
            and _active_organization(request.user)
        )


class IsTourCRMUser(BasePermission):
    """Tur CRM: owner_tour yoki tour_staff."""
    message = 'Tur CRM paneliga kirish huquqi yo\'q.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role not in TOUR_CRM_ROLES:
            return False
        if request.user.role in TOUR_OWNER_ROLES:
            return _owner_owns_organization(request.user)
        profile = getattr(request.user, 'branch_staff_profile', None)
        return bool(profile and profile.is_active and _active_organization(request.user))


# ─── Umumiy / legacy alias ────────────────────────────────────────────────────

class IsCRMUser(BasePermission):
    """Har qanday CRM roli (restoran yoki tur)."""
    message = 'CRM panelga kirish huquqi yo\'q.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not is_crm_role(request.user.role):
            return False
        if request.user.role in RESTAURANT_OWNER_ROLES | TOUR_OWNER_ROLES:
            return _owner_owns_organization(request.user)
        profile = getattr(request.user, 'branch_staff_profile', None)
        return bool(profile and profile.is_active and _active_organization(request.user))


class IsBranchStaff(IsRestaurantStaff):
    """Legacy alias — restoran xodimi (restaurant_staff)."""

    message = 'Siz bu filialga kirish huquqiga ega emassiz.'


class IsOrganizationOwner(IsRestaurantOwner):
    """Legacy alias — endi IsRestaurantOwner ishlating."""

    message = 'Bu amal faqat tashkilot egasi uchun.'
