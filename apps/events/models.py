"""
Events app — Eksklyuziv va ochiq tadbirlar katalogi.
Tier darajasiga bog'liq ko'rinuvchanlik.
TZ 3.7 bo'limiga mos.
"""

from django.db import models
from apps.core.models import BaseModel


class EventCategory(BaseModel):
    """Tadbir kategoriyasi (konsert, sport, gala dinner va h.k.)."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=50, blank=True, help_text='Emoji yoki icon nomi')

    class Meta:
        verbose_name = 'Tadbir kategoriyasi'
        verbose_name_plural = 'Tadbir kategoriyalari'

    def __str__(self):
        return self.name


class Event(BaseModel):
    """Tadbir — ochiq yoki eksklyuziv."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Qoralama'
        PUBLISHED = 'published', 'Chop etilgan'
        CANCELLED = 'cancelled', 'Bekor qilingan'
        SOLD_OUT = 'sold_out', 'Chiptalar tugagan'
        COMPLETED = 'completed', 'O\'tib ketdi'

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    category = models.ForeignKey(
        EventCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='events'
    )
    branch = models.ForeignKey(
        'crm.Branch', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='events',
        help_text='Qaysi filialda o\'tkaziladi'
    )
    venue_name = models.CharField(max_length=255, blank=True)
    venue_address = models.TextField(blank=True)

    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)

    # Chiptalar
    total_capacity = models.PositiveIntegerField(default=0)
    available_tickets = models.PositiveIntegerField(default=0)
    ticket_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='UZS')

    # Eksklyuzivlik — faqat tier.exclusive_events_access=True bo'lgan foydalanuvchilarga ko'rinadi
    is_exclusive = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )

    cover_image = models.ImageField(upload_to='events/', null=True, blank=True)
    tags = models.JSONField(default=list)

    class Meta:
        verbose_name = 'Tadbir'
        verbose_name_plural = 'Tadbirlar'
        ordering = ['starts_at']
        indexes = [
            models.Index(fields=['status', 'starts_at']),
            models.Index(fields=['is_exclusive', 'status']),
        ]

    def __str__(self):
        return f'{self.title} ({self.starts_at.date()})'

    @property
    def is_available(self):
        return self.status == self.Status.PUBLISHED and self.available_tickets > 0
