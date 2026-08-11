"""Tours app permissions."""

from rest_framework.permissions import BasePermission

from apps.crm.models import BranchStaff


class _BaseTourCRMPermission(BasePermission):
    """Asosiy tour CRM permission — org_type=tour_company tekshiruvi."""

    def _get_staff(self, request):
        if not request.user or not request.user.is_authenticated:
            return None
        return getattr(request.user, 'branch_staff_profile', None)

    def has_permission(self, request, view):
        staff = self._get_staff(request)
        if not staff or not staff.is_active:
            return False
        org_type = staff.branch.organization.org_type
        return org_type == 'tour_company'


class IsTourCompanyStaff(_BaseTourCRMPermission):
    """
    Tur kompaniyasi xodimi — faqat o'z tashkilotining ma'lumotlarini ko'radi.
    Minimal ruxsat: view_bookings yoki view_analytics.
    """
    message = 'Siz tur kompaniyasi xodimi emassiz.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        staff = self._get_staff(request)
        # GET uchun view_bookings yoki view_analytics kifoya
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return (
                staff.has_permission('view_bookings')
                or staff.has_permission('view_analytics')
            )
        return True


class IsTourCompanyAdmin(_BaseTourCRMPermission):
    """
    Tur kompaniyasi admini — manage_staff ruxsatiga ega.
    Xodimlarni, paketlarni, statistikani boshqarishi mumkin.
    """
    message = 'Bu amal uchun kompaniya admin huquqi kerak.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        staff = self._get_staff(request)
        return staff.has_permission('manage_staff')


class CanManageTourPackages(_BaseTourCRMPermission):
    """Tur paketlarini yaratish/o'zgartirish/o'chirish ruxsati."""
    message = 'Tur paketlarini boshqarish uchun ruxsat yo\'q.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            staff = self._get_staff(request)
            return staff.has_permission('view_bookings')
        staff = self._get_staff(request)
        return staff.has_permission('manage_bookings')


class CanConfirmTourBookings(_BaseTourCRMPermission):
    """Tur bronlarini tasdiqlash/rad etish ruxsati."""
    message = 'Tur bronlarini tasdiqlash uchun ruxsat yo\'q.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        staff = self._get_staff(request)
        return staff.has_permission('manage_bookings')


class CanGenerateVoucher(_BaseTourCRMPermission):
    """Voaucher yaratish ruxsati."""
    message = 'Voaucher yaratish uchun ruxsat yo\'q.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        staff = self._get_staff(request)
        return staff.has_permission('manage_bookings')
