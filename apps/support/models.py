"""User Inquiry/Support System — support tickets and inquiries."""

from django.db import models
from django.conf import settings
from django.utils import timezone

from apps.core.models import BaseModel


class UserInquiry(BaseModel):
    """User support inquiry/ticket."""
    
    class Category(models.TextChoices):
        GENERAL = 'general', 'Umumiy'
        BOOKING = 'booking', 'Bron'
        PAYMENT = 'payment', 'To\'lov'
        TECHNICAL = 'technical', 'Texnik'
        ACCOUNT = 'account', 'Hisob'
        FEEDBACK = 'feedback', 'Fikr-mulohaza'
    
    class Priority(models.TextChoices):
        LOW = 'low', 'Past'
        MEDIUM = 'medium', 'O\'rtacha'
        HIGH = 'high', 'Yuqori'
        URGENT = 'urgent', 'Shoshilinch'
    
    class Status(models.TextChoices):
        OPEN = 'open', 'Ochiq'
        IN_PROGRESS = 'in_progress', 'Jarayonda'
        RESOLVED = 'resolved', 'Hal qilingan'
        CLOSED = 'closed', 'Yopiq'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='inquiries'
    )
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    
    # Admin response
    admin_response = models.TextField(blank=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='responded_inquiries',
        help_text='Admin who responded'
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    
    # Resolution
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Attachments (store as JSON array of file paths)
    attachments = models.JSONField(default=list, blank=True)
    
    class Meta:
        verbose_name = 'Foydalanuvchi so\'rovi'
        verbose_name_plural = 'Foydalanuvchi so\'rovlari'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return f'{self.user} - {self.subject} ({self.status})'
    
    def respond(self, admin_user, response):
        """Add admin response to inquiry."""
        self.admin_response = response
        self.responded_by = admin_user
        self.responded_at = timezone.now()
        self.status = self.Status.IN_PROGRESS
        self.save(update_fields=['admin_response', 'responded_by', 'responded_at', 'status', 'updated_at'])
        
        # Send notification to user
        from apps.notifications.tasks import send_telegram_notification
        send_telegram_notification.delay(
            chat_id=self.user.phone,
            message=f"📝 Sizning so'rovingizga javob berildi!\n\nMavzu: {self.subject}\nJavob: {response}"
        )
    
    def resolve(self, notes=''):
        """Mark inquiry as resolved."""
        self.status = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save(update_fields=['status', 'resolved_at', 'resolution_notes', 'updated_at'])
        
        # Send notification to user
        from apps.notifications.tasks import send_telegram_notification
        send_telegram_notification.delay(
            chat_id=self.user.phone,
            message=f"✅ Sizning so'rovingiz hal qilindi!\n\nMavzu: {self.subject}"
        )
    
    def close(self):
        """Close inquiry."""
        self.status = self.Status.CLOSED
        self.save(update_fields=['status', 'updated_at'])
    
    @classmethod
    def get_user_inquiries(cls, user):
        """Get all inquiries for a user."""
        return cls.objects.filter(user=user).order_by('-created_at')
    
    @classmethod
    def get_open_inquiries(cls):
        """Get all open inquiries."""
        return cls.objects.filter(status__in=[cls.Status.OPEN, cls.Status.IN_PROGRESS]).order_by('-priority', 'created_at')
