"""Restoran CRM yordamchi funksiyalar — ruxsat va audit."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from apps.crm.models import Branch, BranchStaff, StaffActivityLog
from apps.users.models import UserRole


def get_staff_profile(user) -> BranchStaff | None:
    if user.role != UserRole.RESTAURANT_STAFF:
        return None
    return getattr(user, 'branch_staff_profile', None)


def is_restaurant_owner(user) -> bool:
    return user.role == UserRole.OWNER_RESTAURANT


def require_restaurant_permission(user, permission: str) -> None:
    """Owner — har doim ruxsat. Staff — permissions JSON tekshiruvi."""
    if is_restaurant_owner(user):
        return
    profile = get_staff_profile(user)
    if not profile or not profile.is_active:
        raise PermissionDenied('Restoran CRM kirish huquqi yo\'q.')
    if not profile.has_permission(permission):
        raise PermissionDenied('Bu amal uchun ruxsat yo\'q.')


def can_view_analytics(user) -> bool:
    if is_restaurant_owner(user):
        return True
    profile = get_staff_profile(user)
    return bool(profile and profile.has_permission('view_analytics'))


def can_manage_staff(user) -> bool:
    if is_restaurant_owner(user):
        return True
    profile = get_staff_profile(user)
    return bool(profile and profile.has_permission('manage_staff'))


def resolve_branch(user, branch_id: str | None = None) -> Branch | None:
    """Owner — filial tanlash yoki birinchi filial. Staff — o'z filiali."""
    organization = user.organization
    if not organization:
        return None

    if is_restaurant_owner(user):
        if branch_id:
            return organization.branches.filter(id=branch_id, is_active=True).first()
        return organization.branches.filter(is_active=True).first()

    profile = get_staff_profile(user)
    return profile.branch if profile else None


def log_staff_activity(
    user,
    *,
    action_type: str,
    entity_type: str = '',
    entity_id=None,
    description: str = '',
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
        ip_address=ip,
    )
