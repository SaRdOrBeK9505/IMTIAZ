"""
Core permissions — loyiha bo'ylab qayta ishlatiladigan DRF permission sinflari.
"""

from rest_framework.permissions import BasePermission


class HasApprovedMembership(BasePermission):
    """
    Faqat waitlist holati 'approved' bo'lgan foydalanuvchilarga
    bron va AI xizmatlaridan foydalanishga ruxsat beradi.
    Tasdiqlanmaganlar faqat GET so'rovlarni amalga oshira oladi (browse-only).
    """
    message = 'Siz hali a\'zolikka qabul qilinmagansiz. Faqat ko\'rish rejimi mavjud.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        # Write operatsiyalar uchun approved status kerak
        try:
            return request.user.waitlist_application.status == 'approved'
        except Exception:
            return False


class IsBranchStaff(BasePermission):
    """Branch xodimlariga faqat o'z branchlariga kirish huquqi."""
    message = 'Siz bu filialga kirish huquqiga ega emassiz.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, 'branch_staff_profile')
        )
