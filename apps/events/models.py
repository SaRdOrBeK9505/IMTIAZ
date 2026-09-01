"""
Events app — Eksklyuziv va ochiq tadbirlar katalogi.
Tier darajasiga bog'liq ko'rinuvchanlik.
TZ 3.7 bo'limiga mos.
"""

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
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
    total_capacity = models.PositiveIntegerField(default=0, help_text='Umumiy sig\'im')
    available_tickets = models.PositiveIntegerField(default=0, help_text='Qolgan chiptalar')
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


class EventRegistration(BaseModel):
    """Event registration/ticket booking."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        CONFIRMED = 'confirmed', 'Tasdiqlangan'
        CANCELLED = 'cancelled', 'Bekor qilingan'
        CHECKED_IN = 'checked_in', 'Kelgan'
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='event_registrations'
    )
    ticket_count = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text='Chipta soni (max 10)'
    )
    total_price = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    booking_reference = models.CharField(max_length=50, unique=True, help_text='Bron raqami')
    special_requests = models.TextField(blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Tadbir ro\'yxati'
        verbose_name_plural = 'Tadbir ro\'yxatlari'
        ordering = ['-created_at']
        unique_together = ['event', 'user']
        indexes = [
            models.Index(fields=['event', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['booking_reference']),
        ]
    
    def __str__(self):
        return f'{self.user} - {self.event.title} ({self.ticket_count} tickets)'
    
    def clean(self):
        """Validate registration."""
        # Check if event has enough capacity
        if self.event.available_tickets < self.ticket_count:
            raise ValidationError(
                f'Yetarli chipta yo\'q. Qolgan: {self.event.available_tickets}'
            )
        
        # Check if event is available
        if not self.event.is_available:
            raise ValidationError('Bu tadbirga ro\'yxatga olish mumkin emas')
    
    def save(self, *args, **kwargs):
        self.clean()
        
        # Calculate total price
        if not self.total_price:
            self.total_price = self.event.ticket_price * self.ticket_count
        
        # Generate booking reference if not set
        if not self.booking_reference:
            import uuid
            self.booking_reference = f"EVT-{uuid.uuid4().hex[:12].upper()}"
        
        super().save(*args, **kwargs)
    
    def confirm(self):
        """Confirm registration and update event capacity with race condition protection."""
        if self.status != self.Status.PENDING:
            raise ValueError('Faqat kutilayotgan ro\'yxatlarni tasdiqlash mumkin')
        
        from django.db import transaction
        
        with transaction.atomic():
            # Lock the event row to prevent race conditions
            event = Event.objects.select_for_update().get(id=self.event.id)
            
            # Double-check capacity after acquiring lock
            if event.available_tickets < self.ticket_count:
                raise ValueError(
                    f'Yetarli chipta yo\'q. Qolgan: {event.available_tickets}, '
                    f'So\'ralgan: {self.ticket_count}'
                )
            
            # Update registration status
            self.status = self.Status.CONFIRMED
            self.save(update_fields=['status', 'updated_at'])
            
            # Update event capacity
            event.available_tickets -= self.ticket_count
            event.save(update_fields=['available_tickets', 'updated_at'])
    
    def cancel(self):
        """Cancel registration and restore event capacity."""
        if self.status == self.Status.CANCELLED:
            raise ValueError('Ro\'yxat allaqachon bekor qilingan')
        
        if self.status == self.Status.CHECKED_IN:
            raise ValueError('Kelgan ro\'yxatni bekor qilib bo\'lmaydi')
        
        old_status = self.status
        self.status = self.Status.CANCELLED
        self.save(update_fields=['status', 'updated_at'])
        
        # Restore event capacity if was confirmed
        if old_status == self.Status.CONFIRMED:
            self.event.available_tickets += self.ticket_count
            self.event.save(update_fields=['available_tickets', 'updated_at'])
    
    def check_in(self):
        """Mark user as checked in."""
        if self.status != self.Status.CONFIRMED:
            raise ValueError('Faqat tasdiqlangan ro\'yxatlarni belgilash mumkin')
        
        from django.utils import timezone
        self.status = self.Status.CHECKED_IN
        self.checked_in_at = timezone.now()
        self.save(update_fields=['status', 'checked_in_at', 'updated_at'])
