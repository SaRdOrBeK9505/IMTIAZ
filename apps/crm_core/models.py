"""
crm_core — vertikallar o'rtasida umumiy CRM logikasi.
Lead pipeline + StaffActionLog proxy.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.crm.models import StaffActivityLog


class Lead(BaseModel):
    """CRM lead pipeline — restoran va tur bronlaridan keladi."""

    class Stage(models.TextChoices):
        NEW = 'new', 'Yangi'
        CONTACTED = 'contacted', 'Bog\'lanildi'
        QUALIFIED = 'qualified', 'Tasdiqlangan'
        WON = 'won', 'Yutildi'
        LOST = 'lost', 'Yo\'qotildi'

    class Vertical(models.TextChoices):
        RESTAURANT = 'restaurant', 'Restoran'
        TRAVEL = 'travel', 'Sayohat'

    organization = models.ForeignKey(
        'crm.Organization', on_delete=models.CASCADE, related_name='leads',
    )
    branch = models.ForeignKey(
        'crm.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='leads',
    )
    booking = models.OneToOneField(
        'booking.Booking', on_delete=models.CASCADE, null=True, blank=True, related_name='crm_lead',
    )
    vertical = models.CharField(max_length=20, choices=Vertical.choices, db_index=True)
    stage = models.CharField(
        max_length=20, choices=Stage.choices, default=Stage.NEW, db_index=True,
    )
    title = models.CharField(max_length=255)
    customer_name = models.CharField(max_length=150, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_leads',
    )
    metadata = models.JSONField(default=dict, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'CRM lead'
        verbose_name_plural = 'CRM leadlar'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'vertical', 'stage']),
            models.Index(fields=['organization', 'created_at']),
        ]

    def __str__(self):
        return f'{self.title} ({self.get_stage_display()})'


class StaffActionLog(StaffActivityLog):
    """Xodim audit jurnali — o'zgartirish mumkin emas (proxy)."""

    class Meta:
        proxy = True
        verbose_name = 'Xodim amali (audit)'
        verbose_name_plural = 'Xodim amallari (audit)'
