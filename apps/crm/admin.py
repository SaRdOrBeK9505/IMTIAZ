from django.contrib import admin
from django.contrib import messages

from apps.crm_core.onboarding import sync_owner_role_for_organization

from .admin_forms import OrganizationAdminForm
from .models import (
    Branch,
    BranchStaff,
    Organization,
    RestaurantTable,
    StaffActivityLog,
    StaffPerformanceSummary,
    TableTimeSlot,
    TourLead,
    RestaurantLead,
)


class BranchInline(admin.StackedInline):
    model = Branch
    extra = 0


class TableTimeSlotInline(admin.TabularInline):
    model = TableTimeSlot
    extra = 0
    fields = ['date', 'start_time', 'end_time', 'is_available', 'booking', 'notes']
    readonly_fields = ['booking']
    ordering = ['date', 'start_time']


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    form = OrganizationAdminForm
    list_display = ['name', 'org_type', 'business_type', 'owner', 'is_active']
    list_filter = ['org_type', 'business_type', 'is_active']
    search_fields = ['name', 'owner__phone', 'owner__first_name']
    autocomplete_fields = ['owner']
    inlines = [BranchInline]

    fieldsets = (
        (None, {
            'fields': ('name', 'org_type', 'business_type', 'owner', 'is_active'),
            'description': (
                'CRM egasi self-register qilmaydi. Avval Users admin da owner yaratiling '
                '(owner_restaurant / owner_tour), keyin shu yerda biriktiring yoki '
                'provision_crm_partner management command dan foydalaning.'
            ),
        }),
        ('Qo\'shimcha', {
            'classes': ('collapse',),
            'fields': (
                'description', 'logo', 'website', 'contact_email', 'contact_phone',
                'crm_webhook_url', 'crm_webhook_secret',
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        sync_owner_role_for_organization(obj)
        if obj.owner:
            messages.info(
                request,
                f'Owner {obj.owner.phone} roli {obj.business_type} ga moslashtirildi.',
            )


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


@admin.register(RestaurantTable)
class RestaurantTableAdmin(admin.ModelAdmin):
    list_display = ['table_number', 'branch', 'section', 'capacity', 'current_status', 'is_active']
    list_filter = ['branch__organization', 'is_active', 'current_status', 'is_vip']
    search_fields = ['table_number', 'section', 'branch__name']
    inlines = [TableTimeSlotInline]


@admin.register(TableTimeSlot)
class TableTimeSlotAdmin(admin.ModelAdmin):
    list_display = ['table', 'date', 'start_time', 'end_time', 'is_available', 'booking']
    list_filter = ['date', 'is_available', 'table__branch']
    search_fields = ['table__table_number', 'notes']
    date_hierarchy = 'date'


@admin.register(StaffActivityLog)
class StaffActivityLogAdmin(admin.ModelAdmin):
    list_display = ['staff', 'action_type', 'entity_type', 'created_at']
    list_filter = ['action_type', 'created_at']
    search_fields = ['staff__user__phone', 'description']
    readonly_fields = ['staff', 'action_type', 'entity_type', 'entity_id', 'description', 'metadata', 'ip_address', 'created_at']


@admin.register(StaffPerformanceSummary)
class StaffPerformanceSummaryAdmin(admin.ModelAdmin):
    list_display = ['staff', 'period_type', 'period_start', 'period_end', 'table_bookings_confirmed']
    list_filter = ['period_type', 'period_start']
    search_fields = ['staff__user__phone']


@admin.register(TourLead)
class TourLeadAdmin(admin.ModelAdmin):
    list_display = ['phone', 'full_name', 'organization', 'package', 'status', 'created_at']
    list_filter = ['status', 'organization']
    search_fields = ['phone', 'full_name', 'note']
    readonly_fields = ['crm_response', 'sent_at', 'retry_count', 'created_at', 'updated_at']
    raw_id_fields = ['organization', 'package', 'user', 'session']


@admin.register(RestaurantLead)
class RestaurantLeadAdmin(admin.ModelAdmin):
    list_display = ['phone', 'full_name', 'organization', 'branch', 'preferred_date', 'preferred_time', 'guests', 'status', 'created_at']
    list_filter = ['status', 'organization', 'branch']
    search_fields = ['phone', 'full_name', 'note']
    readonly_fields = ['crm_response', 'sent_at', 'retry_count', 'created_at', 'updated_at']
    raw_id_fields = ['organization', 'branch', 'user', 'session']

