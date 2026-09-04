"""
Notifications app — Telegram bot orqali bildirishnomalar.
Celery orqali navbatlashtiriladi.
TZ 3.7 bo'limiga mos.
"""

from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class Notification(BaseModel):
    """Foydalanuvchiga yuboriladigan bildirishnoma."""

    class NotificationType(models.TextChoices):
        BOOKING_CONFIRMED = 'booking_confirmed', 'Bron tasdiqlandi'
        BOOKING_CANCELLED = 'booking_cancelled', 'Bron bekor qilindi'
        PAYMENT_SUCCESS = 'payment_success', 'To\'lov muvaffaqiyatli'
        PAYMENT_FAILED = 'payment_failed', 'To\'lov amalga oshmadi'
        BOOKING_REMINDER = 'booking_reminder', 'Bron eslatmasi'
        AI_SUGGESTION = 'ai_suggestion', 'AI taklifi'
        SUBSCRIPTION_RENEWAL = 'subscription_renewal', 'Obuna yangilandi'
        SUBSCRIPTION_PAST_DUE = 'subscription_past_due', 'Obuna to\'lovi o\'tmadi'
        WAITLIST_APPROVED = 'waitlist_approved', 'A\'zolik tasdiqlandi'
        NEW_LEAD = 'new_lead', 'Yangi lead (CRM)'
        PROMO_DISCOUNT = 'promo_discount', 'Chegirma taklifi'
        QR_SCAN_SUCCESS = 'qr_scan_success', 'QR skan muvaffaqiyatli'
        GENERAL = 'general', 'Umumiy'

    class Channel(models.TextChoices):
        TELEGRAM = 'telegram', 'Telegram'
        PUSH = 'push', 'Push bildirishnoma'
        IN_APP = 'in_app', 'Ilova ichida'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Navbatda'
        SENT = 'sent', 'Yuborildi'
        FAILED = 'failed', 'Amalga oshmadi'
        READ = 'read', 'O\'qildi'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=40, choices=NotificationType.choices)
    channel = models.CharField(
        max_length=20, choices=Channel.choices, default=Channel.TELEGRAM
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    # Telegram xabar ID (keyin tahrirlash/o'chirish uchun)
    telegram_message_id = models.BigIntegerField(null=True, blank=True)
    # Qo'shimcha ma'lumot (booking_id, event_id va h.k.)
    metadata = models.JSONField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    # Muayyan vaqtda yuborish
    scheduled_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Bildirishnoma'
        verbose_name_plural = 'Bildirishnomalar'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'scheduled_at']),
        ]

    def __str__(self):
        return f'{self.user} | {self.notification_type} | {self.status}'


class PromoDiscount(BaseModel):
    """CRM staff tomonidan mijozlarga yuboriladigan chegirma takliflari."""
    
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Foiz'
        FIXED = 'fixed', 'Qat\'iy summa'
    
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Faol'
        EXPIRED = 'expired', 'Muddati tugagan'
        CANCELLED = 'cancelled', 'Bekor qilingan'
    
    organization = models.ForeignKey(
        'crm.Organization', on_delete=models.CASCADE, related_name='promo_discounts'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_promos'
    )
    customer_phone = models.CharField(max_length=20, help_text='Mijoz telefon raqami')
    customer_name = models.CharField(max_length=200, blank=True, help_text='Mijoz ismi (ixtiyoriy)')
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, help_text='Foiz yoki summa')
    title = models.CharField(max_length=255, help_text='Chegirma sarlavhasi')
    description = models.TextField(blank=True, help_text='Chegirma tavsifi')
    valid_until = models.DateTimeField(null=True, blank=True, help_text='Chegirma muddati')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    is_sent = models.BooleanField(default=False, help_text='Bildirishnoma yuborildi')
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Chegirma taklifi'
        verbose_name_plural = 'Chegirma takliflari'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['customer_phone', 'status']),
        ]
    
    def __str__(self):
        return f'{self.customer_phone} - {self.title}'
