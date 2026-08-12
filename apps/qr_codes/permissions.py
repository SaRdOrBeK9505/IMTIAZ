"""QR Codes app permissions — restoran owner va staff."""

from rest_framework.permissions import BasePermission

from apps.core.permissions import _active_organization, _owner_owns_organization
from apps.users.crm_roles import RESTAURANT_OWNER_ROLES, RESTAURANT_STAFF_ROLES


class IsRestaurantQRManager(BasePermission):
    """
    Restoran CRM QR boshqaruvi:
    - owner_restaurant — to'liq kirish
    - restaurant_staff — manage_bookings / manage_staff / view_analytics bo'yicha
    """
    message = 'QR kodlarni boshqarish uchun ruxsat yo\'q.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user = request.user
        if user.role in RESTAURANT_OWNER_ROLES:
            return _owner_owns_organization(user)

        if user.role not in RESTAURANT_STAFF_ROLES:
            return False

        staff = getattr(user, 'branch_staff_profile', None)
        if not staff or not staff.is_active or not _active_organization(user):
            return False

        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return (
                staff.has_permission('view_analytics')
                or staff.has_permission('manage_bookings')
            )
        return staff.has_permission('manage_bookings') or staff.has_permission('manage_staff')


# Legacy alias — mavjud importlar buzilmasin
IsQRManager = IsRestaurantQRManager
