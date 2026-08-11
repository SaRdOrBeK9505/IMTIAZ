"""QR Codes app permissions."""

from rest_framework.permissions import BasePermission


class IsQRManager(BasePermission):
    """
    Tashkilot xodimi — QR kodlarni boshqarish ruxsati.
    manage_bookings yoki manage_staff ruxsati kerak.
    """
    message = 'QR kodlarni boshqarish uchun ruxsat yo\'q.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        staff = getattr(request.user, 'branch_staff_profile', None)
        if not staff or not staff.is_active:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return (
                staff.has_permission('view_analytics')
                or staff.has_permission('manage_bookings')
            )
        return staff.has_permission('manage_bookings') or staff.has_permission('manage_staff')
