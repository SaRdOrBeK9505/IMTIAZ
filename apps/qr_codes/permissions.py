"""QR Codes app permissions — barcha CRM vertikallari uchun umumiy."""

from rest_framework.permissions import BasePermission

from apps.core.permissions import _active_organization, _owner_owns_organization
from apps.users.crm_roles import (
    RESTAURANT_OWNER_ROLES, RESTAURANT_STAFF_ROLES,
    TOUR_OWNER_ROLES, TOUR_STAFF_ROLES,
)

_ALL_OWNER_ROLES = RESTAURANT_OWNER_ROLES | TOUR_OWNER_ROLES
_ALL_STAFF_ROLES = RESTAURANT_STAFF_ROLES | TOUR_STAFF_ROLES


class IsOrgQRManager(BasePermission):
    """
    Har qanday CRM vertikali (restoran, tur kompaniyasi, ...) uchun QR boshqaruvi:
    - <vertikal>_owner — to'liq kirish
    - <vertikal>_staff — manage_bookings / manage_staff / view_analytics bo'yicha
    """
    message = "QR kodlarni boshqarish uchun ruxsat yo'q."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user = request.user
        if user.role in _ALL_OWNER_ROLES:
            return _owner_owns_organization(user)

        if user.role not in _ALL_STAFF_ROLES:
            return False

        staff = getattr(user, 'branch_staff_profile', None)
        if not staff or not staff.is_active or not _active_organization(user):
            return False

        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return staff.has_permission('view_analytics') or staff.has_permission('manage_bookings')
        return staff.has_permission('manage_bookings') or staff.has_permission('manage_staff')


# Legacy nomlar — mavjud importlar (apps/qr_codes/views.py, crm_restaurant) buzilmasin
IsRestaurantQRManager = IsOrgQRManager
IsQRManager = IsOrgQRManager
