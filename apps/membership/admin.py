from django.contrib import admin
from django.utils import timezone
from .models import MembershipTier, UserMembership, WaitlistApplication, PromoCode, Subscription


@admin.register(MembershipTier)
class MembershipTierAdmin(admin.ModelAdmin):
    list_display  = ['name', 'monthly_fee', 'max_ai_autonomy_level',
                     'exclusive_events_access', 'priority_support', 'sort_order']
    list_editable = ['sort_order']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(UserMembership)
class UserMembershipAdmin(admin.ModelAdmin):
    list_display    = ['user', 'tier', 'exclusive_events_access',
                       'max_ai_autonomy_level', 'created_at']
    list_filter     = ['tier', 'exclusive_events_access', 'max_ai_autonomy_level']
    search_fields   = ['user__telegram_username', 'user__first_name', 'user__phone']
    raw_id_fields   = ['user']
    readonly_fields = ['max_ai_autonomy_level', 'exclusive_events_access',
                       'commission_discount_percent', 'created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': ('user', 'tier'),
        }),
        ("Tier'dan ko'chirilgan (avtomatik)", {
            'fields': ('max_ai_autonomy_level', 'exclusive_events_access', 'commission_discount_percent'),
            'classes': ('collapse',),
            'description': "Bu maydonlar tier saqlanganda avtomatik yangilanadi.",
        }),
        ('Vaqtlar', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.sync_from_tier()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['tier'].help_text = (
            "Tier tanlanganida AI autonomiya, chegirma va events access avtomatik yangilanadi."
        )
        return form


@admin.register(WaitlistApplication)
class WaitlistApplicationAdmin(admin.ModelAdmin):
    list_display  = ['user', 'status', 'promo_code', 'created_at', 'reviewed_at']
    list_filter   = ['status']
    search_fields = ['user__telegram_username', 'user__first_name', 'user__phone', 'promo_code']
    readonly_fields = ['created_at', 'reviewed_at']
    actions = ['approve_selected', 'reject_selected']

    def approve_selected(self, request, queryset):
        from .models import UserMembership, MembershipTier
        now     = timezone.now()
        pending = queryset.filter(status='pending').select_related('user')

        # Default tier — eng arzon/birinchi tier
        default_tier = MembershipTier.objects.order_by('sort_order', 'monthly_fee').first()
        if not default_tier:
            self.message_user(request, 'Hech qanday MembershipTier topilmadi. Avval tier yarating.', level='error')
            return

        count = 0
        for app in pending:
            app.status      = WaitlistApplication.Status.APPROVED
            app.reviewed_by = request.user
            app.reviewed_at = now
            app.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])

            # UserMembership yaratish yoki yangilash
            um, created = UserMembership.objects.get_or_create(
                user=app.user,
                defaults={'tier': default_tier},
            )
            if not created:
                um.tier = default_tier
                um.save(update_fields=['tier', 'updated_at'])
            um.sync_from_tier()

            # Foydalanuvchiga bildirishnoma
            try:
                from apps.notifications.tasks import notify_user
                notify_user(
                    app.user,
                    notification_type='waitlist_approved',
                    title="A'zolikka qabul qilindingiz!",
                    body=f"Tabriklaymiz! {default_tier.name} darajasiga qabul qilindingiz.",
                    metadata={'tier_name': default_tier.name},
                )
            except Exception:
                pass  # Notification xatosi asosiy jarayonni to'xtatmasin

            count += 1

        self.message_user(request, f'{count} ta ariza tasdiqlandi va UserMembership yaratildi.')
    approve_selected.short_description = 'Tanlangan arizalarni tasdiqlash + a\'zolik yaratish'

    def reject_selected(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(status='pending').update(
            status='rejected',
            reviewed_by=request.user,
            reviewed_at=now,
        )
        self.message_user(request, f'{updated} ta ariza rad etildi.')
    reject_selected.short_description = 'Tanlangan arizalarni rad etish'


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display  = ['code', 'tier', 'max_uses', 'used_count', 'is_active', 'expires_at']
    list_filter   = ['is_active', 'tier']
    search_fields = ['code']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'tier', 'status', 'current_period_end',
                     'retry_count', 'created_at']
    list_filter   = ['status', 'tier']
    search_fields = ['user__telegram_username', 'user__phone']
    readonly_fields = ['created_at', 'updated_at', 'last_payment_attempt']
