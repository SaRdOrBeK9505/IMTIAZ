"""
CRM app — Hamkor tashkilotlar va filiallar.
Organization → Branch ierarxiyasi.
BranchStaff ruxsatlari.
TZ 3.6 bo'limiga mos.
"""

from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class Organization(BaseModel):
    """Hamkor tashkilot (restoran zanjiri, aviakassa va h.k.)."""

    class OrgType(models.TextChoices):
        RESTAURANT = 'restaurant', 'Restoran'
        AIRLINE = 'airline', 'Aviakompaniya'
        RAILWAY = 'railway', 'Temir yo\'l'
        EVENT_ORGANIZER = 'event_organizer', 'Tadbir tashkilotchisi'
        HOTEL = 'hotel', 'Mehmonxona'
        OTHER = 'other', 'Boshqa'

    name = models.CharField(max_length=200)
    org_type = models.CharField(max_length=30, choices=OrgType.choices)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='orgs/logos/', null=True, blank=True)
    website = models.URLField(blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Tashkilot'
        verbose_name_plural = 'Tashkilotlar'
        ordering = ['name']

    def __str__(self):
        return self.name


class Branch(BaseModel):
    """
    Tashkilot filiallari.
    Organization → Branch ierarxiyasi: bitta tashkilot ko'p filialga ega bo'lishi mumkin.
    """
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='branches'
    )
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Uzbekistan')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    working_hours = models.JSONField(
        default=dict,
        help_text='{"mon": "09:00-22:00", "tue": "09:00-22:00", ...}'
    )
    capacity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Filial'
        verbose_name_plural = 'Filiallar'
        ordering = ['organization', 'name']

    def __str__(self):
        return f'{self.organization.name} — {self.name}'


class BranchStaffPermission(models.TextChoices):
    VIEW_BOOKINGS = 'view_bookings', 'Bronlarni ko\'rish'
    MANAGE_BOOKINGS = 'manage_bookings', 'Bronlarni boshqarish'
    VIEW_ANALYTICS = 'view_analytics', 'Analitikani ko\'rish'
    MANAGE_STAFF = 'manage_staff', 'Xodimlarni boshqarish'


class BranchStaff(BaseModel):
    """
    Filial xodimi — faqat o'z branch_id'siga tegishli ma'lumotni ko'radi.
    Ruxsatlar permissions maydoni orqali boshqariladi.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='branch_staff_profile'
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='staff'
    )
    role = models.CharField(max_length=50, blank=True, help_text='Manager, Cashier va h.k.')
    permissions = models.JSONField(
        default=list,
        help_text='Ruxsatlar ro\'yxati: ["view_bookings", "view_analytics", ...]'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Filial xodimi'
        verbose_name_plural = 'Filial xodimlari'

    def __str__(self):
        return f'{self.user} @ {self.branch}'

    def has_permission(self, permission: str) -> bool:
        return permission in (self.permissions or [])
