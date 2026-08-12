"""Tours app permissions — tour_staff / owner_tour rollari."""

from rest_framework.permissions import BasePermission

from apps.core.permissions import IsTourOwner
from apps.users.crm_roles import TOUR_OWNER_ROLES, TOUR_STAFF_ROLES


class _BaseTourCRMPermission(BasePermission):
    def _get_staff(self, request):
        if not request.user or not request.user.is_authenticated:
            return None
        if request.user.role not in TOUR_STAFF_ROLES:
            return None
        return getattr(request.user, 'branch_staff_profile', None)

    def has_permission(self, request, view):
        if request.user.role in TOUR_OWNER_ROLES:
            return IsTourOwner().has_permission(request, view)
        staff = self._get_staff(request)
        return bool(staff and staff.is_active and request.user.organization)


class IsTourCompanyStaff(_BaseTourCRMPermission):
    message = 'Siz tur kompaniyasi xodimi emassiz.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.role in TOUR_OWNER_ROLES:
            return True
        staff = self._get_staff(request)
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return staff.has_permission('view_bookings') or staff.has_permission('view_analytics')
        return True


class IsTourCompanyAdmin(_BaseTourCRMPermission):
    message = 'Bu amal uchun kompaniya admin huquqi kerak.'

    def has_permission(self, request, view):
        if request.user.role in TOUR_OWNER_ROLES:
            return IsTourOwner().has_permission(request, view)
        if not super().has_permission(request, view):
            return False
        staff = self._get_staff(request)
        return staff.has_permission('manage_staff')


class CanManageTourPackages(_BaseTourCRMPermission):
    message = 'Tur paketlarini boshqarish uchun ruxsat yo\'q.'

    def has_permission(self, request, view):
        if request.user.role in TOUR_OWNER_ROLES:
            return IsTourOwner().has_permission(request, view)
        if not super().has_permission(request, view):
            return False
        staff = self._get_staff(request)
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return staff.has_permission('view_bookings')
        return staff.has_permission('manage_bookings')


class CanConfirmTourBookings(_BaseTourCRMPermission):
    message = 'Tur bronlarini tasdiqlash uchun ruxsat yo\'q.'

    def has_permission(self, request, view):
        if request.user.role in TOUR_OWNER_ROLES:
            return IsTourOwner().has_permission(request, view)
        if not super().has_permission(request, view):
            return False
        staff = self._get_staff(request)
        return staff.has_permission('manage_bookings')


class CanGenerateVoucher(_BaseTourCRMPermission):
    message = 'Voaucher yaratish uchun ruxsat yo\'q.'

    def has_permission(self, request, view):
        if request.user.role in TOUR_OWNER_ROLES:
            return IsTourOwner().has_permission(request, view)
        if not super().has_permission(request, view):
            return False
        staff = self._get_staff(request)
        return staff.has_permission('manage_bookings')


# Alias — yo'nalishlar paketlar bilan bir xil ruxsat darajasida
CanManageTourDestinations = CanManageTourPackages
