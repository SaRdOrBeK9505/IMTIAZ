"""Umumiy CRM mixin va base viewset'lar."""

from __future__ import annotations

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.authentication import CRMJWTAuthentication
from apps.core.permissions import (
    IsRestaurantCRMUser,
    IsRestaurantOwner,
    IsRestaurantStaff,
    IsTourCRMUser,
    IsTourOwner,
    IsTourStaff,
)
from apps.crm.models import BranchStaff
from apps.users.crm_roles import staff_role_for_owner
from apps.users.models import User, UserRole


class OrganizationScopedMixin:
    organization_lookup = 'branch__organization'

    def get_user_organization(self):
        return self.request.user.organization

    def scope_queryset_to_organization(self, queryset):
        organization = self.get_user_organization()
        if not organization:
            return queryset.none()
        return queryset.filter(**{self.organization_lookup: organization})


class BranchScopedMixin(OrganizationScopedMixin):
    branch_lookup = 'branch'

    def get_user_branch(self):
        user = self.request.user
        if user.role in (UserRole.RESTAURANT_STAFF, UserRole.TOUR_STAFF):
            profile = getattr(user, 'branch_staff_profile', None)
            return profile.branch if profile else None
        return None

    def scope_queryset_to_branch(self, queryset):
        branch = self.get_user_branch()
        if branch is not None:
            return queryset.filter(**{self.branch_lookup: branch})
        return self.scope_queryset_to_organization(queryset)


class StaffManagementMixin:
    """Owner o'z kompaniyasiga xodim qo'shadi — role avtomatik owner roliga mos."""

    staff_user_role: str = ''

    def get_staff_queryset(self):
        organization = self.request.user.organization
        if not organization:
            return BranchStaff.objects.none()
        return BranchStaff.objects.filter(
            branch__organization=organization,
        ).select_related('user', 'branch')

    def create_staff_user(self, validated_data: dict) -> BranchStaff:
        from django.db import transaction

        organization = self.request.user.organization
        branch = validated_data['branch']
        if branch.organization_id != organization.id:
            raise ValueError('Filial ushbu tashkilotga tegishli emas.')

        staff_role = self.staff_user_role or staff_role_for_owner(self.request.user.role)

        with transaction.atomic():
            user = User.objects.create_user(
                phone=validated_data['phone'],
                password=validated_data['password'],
                role=staff_role,
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', ''),
                is_phone_verified=True,
            )
            return BranchStaff.objects.create(
                user=user,
                branch=branch,
                role=validated_data.get('role', ''),
                permissions=validated_data.get('permissions', []),
            )


class RestaurantStaffManagementMixin(StaffManagementMixin):
    staff_user_role = UserRole.RESTAURANT_STAFF


class TourStaffManagementMixin(StaffManagementMixin):
    staff_user_role = UserRole.TOUR_STAFF


class OwnerDashboardMixin:
    def build_owner_dashboard(self, organization, panel: str) -> dict:
        from apps.crm_core.verticals.registry import get_feature_flags, get_vertical

        vertical_key = 'travel' if panel == 'tour' else 'restaurant'
        vertical = get_vertical(vertical_key)
        stats = vertical.get_dashboard_stats(organization) if vertical else {}
        return {
            'organization': {
                'id': str(organization.id),
                'name': organization.name,
            },
            'panel': panel,
            'stats': stats,
            'feature_flags': get_feature_flags(vertical_key),
        }


class LeadTrackingMixin:
    def filter_bookings_for_user(self, queryset):
        user = self.request.user
        organization = user.organization
        if not organization:
            return queryset.none()
        if user.role == UserRole.RESTAURANT_STAFF:
            branch = user.branch_staff_profile.branch
            return queryset.filter(restaurant_detail__branch=branch)
        branch_ids = organization.branches.filter(is_active=True).values_list('id', flat=True)
        return queryset.filter(restaurant_detail__branch_id__in=branch_ids)


class RestaurantOperatorViewSet(BranchScopedMixin, viewsets.ModelViewSet):
    """Restoran CRM ViewSet — owner (org) va staff (filial) uchun."""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return super().get_queryset().none()
        return self.scope_queryset_to_branch(super().get_queryset())


class RestaurantCRMViewSet(BranchScopedMixin, viewsets.ModelViewSet):
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return super().get_queryset().none()
        return self.scope_queryset_to_branch(super().get_queryset())
