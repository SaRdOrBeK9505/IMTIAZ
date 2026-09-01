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


class UserBonus(BaseModel):
    """User-specific bonus with QR code."""
    
    bonus_category = models.ForeignKey(
        BonusCategory, on_delete=models.CASCADE,
        related_name='user_bonuses'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='bonuses'
    )
    qr_code = models.CharField(
        max_length=255, unique=True,
        help_text='Noyob QR kod identifikatori'
    )
    qr_code_image = models.ImageField(
        upload_to='qrcodes/bonuses/',
        null=True, blank=True,
        help_text='QR kod rasm fayli'
    )
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    booking = models.ForeignKey(
        'booking.Booking', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='applied_bonuses'
    )
    
    class Meta:
        verbose_name = 'Foydalanuvchi bonusi'
        verbose_name_plural = 'Foydalanuvchi bonuslari'
        ordering = ['-created_at']
        unique_together = ['user', 'bonus_category']
        indexes = [
            models.Index(fields=['user', 'is_used']),
            models.Index(fields=['qr_code']),
        ]
    
    def __str__(self):
        return f'{self.user} - {self.bonus_category.name}'
    
    def generate_qr_code(self):
        """Generate QR code for this bonus using QRCodeService."""
        from .services import QRCodeService
        QRCodeService.generate_bonus_qr(self)
    
    def mark_as_used(self, booking=None):
        """Mark bonus as used."""
        self.is_used = True
        self.used_at = timezone.now()
        self.booking = booking
        self.save(update_fields=['is_used', 'used_at', 'booking', 'updated_at'])
        
        # Increment category usage count
        self.bonus_category.increment_usage()
