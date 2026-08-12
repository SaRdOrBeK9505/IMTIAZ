"""Tur CRM yordamchi funksiyalar — ruxsat va audit."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from apps.crm.models import BranchStaff, StaffActivityLog
from apps.users.models import UserRole


def get_staff_profile(user) -> BranchStaff | None:
    if user.role != UserRole.TOUR_STAFF:
        return None
    return getattr(user, 'branch_staff_profile', None)


def is_tour_owner(user) -> bool:
    return user.role == UserRole.OWNER_TOUR


def require_tour_permission(user, permission: str) -> None:
    """Owner — har doim ruxsat. Staff — permissions JSON tekshiruvi."""
    if is_tour_owner(user):
        return
    profile = get_staff_profile(user)
    if not profile or not profile.is_active:
        raise PermissionDenied('Tur CRM kirish huquqi yo\'q.')
    if not profile.has_permission(permission):
        raise PermissionDenied('Bu amal uchun ruxsat yo\'q.')


def can_view_analytics(user) -> bool:
    if is_tour_owner(user):
        return True
    profile = get_staff_profile(user)
    return bool(profile and profile.has_permission('view_analytics'))


def get_crm_org(user):
    org = user.organization
    if not org:
        raise PermissionDenied('Tashkilot topilmadi.')
    return org


def log_staff_activity(
    user,
    *,
    action_type: str,
    entity_type: str = '',
    entity_id=None,
    description: str = '',
    metadata: dict | None = None,
    request=None,
) -> None:
    """Owner harakatlari loglanmaydi; staff uchun audit."""
    profile = get_staff_profile(user)
    if not profile:
        return
    ip = request.META.get('REMOTE_ADDR') if request else None
    StaffActivityLog.objects.create(
        staff=profile,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        metadata=metadata or {},
        ip_address=ip,
    )
