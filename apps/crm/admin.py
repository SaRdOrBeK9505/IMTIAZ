from django.contrib import admin
from .models import Organization, Branch, BranchStaff


class BranchInline(admin.StackedInline):
    model = Branch
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'org_type', 'is_active']
    list_filter = ['org_type', 'is_active']
    search_fields = ['name']
    inlines = [BranchInline]


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'city', 'is_active']
    list_filter = ['organization__org_type', 'is_active', 'city']
    search_fields = ['name', 'organization__name', 'city']


@admin.register(BranchStaff)
class BranchStaffAdmin(admin.ModelAdmin):
    list_display = ['user', 'branch', 'role', 'is_active']
    list_filter = ['is_active', 'branch__organization']
    search_fields = ['user__telegram_username', 'user__first_name']
