"""Bonuses app — service-based bonus/rewards system."""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import BaseModel


class BonusCategory(BaseModel):
    """Bonus categories per service type (flights, restaurants, events, hotels)."""
    
    class ServiceType(models.TextChoices):
        FLIGHT = 'flight', 'Parvoz'
        RESTAURANT = 'restaurant', 'Restoran'
        EVENT = 'event', 'Tadbir'
        HOTEL = 'hotel', 'Mehmonxona'
        TOUR = 'tour', 'Tur sayohat'
    
    service_type = models.CharField(
        max_length=20,
        choices=ServiceType.choices,
        db_index=True
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    discount_percentage = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Foiz chegirma (0-100)'
    )
    discount_amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True,
        help_text='Belgilangan chegirma (so\'m)'
    )
    min_purchase = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text='Minimal buyurtma miqdori'
    )
    max_usage_count = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Maksimal ishlatish soni (0=cheksiz)'
    )
    usage_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateField(default=timezone.now)
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = 'Bonus kategoriyasi'
        verbose_name_plural = 'Bonus kategoriyalari'
        ordering = ['order', 'service_type', 'name']
        indexes = [
            models.Index(fields=['service_type', 'is_active']),
            models.Index(fields=['valid_from', 'valid_until']),
        ]
    
    def __str__(self):
        return f'{self.name} ({self.get_service_type_display()})'
    
    def is_valid(self):
        """Check if bonus is currently valid."""
        now = timezone.now().date()
        if not self.is_active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_usage_count and self.usage_count >= self.max_usage_count:
            return False
        return True
    
    def increment_usage(self):
        """Increment usage count."""
        self.usage_count += 1
        self.save(update_fields=['usage_count', 'updated_at'])
