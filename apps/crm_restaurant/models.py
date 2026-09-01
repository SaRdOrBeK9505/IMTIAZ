"""Restaurant vertikaliga xos modellar."""

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone

from apps.core.models import BaseModel
from apps.crm.models import Branch


class RestaurantStaff(BaseModel):
    """Restoran xodimi — faqat o'z restoraniga tegishli leadlarni ko'radi."""
    
    class Role(models.TextChoices):
        MANAGER = 'manager', 'Menejer'
        STAFF = 'staff', 'Xodim'
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='restaurant_staff_profile'
    )
    restaurant = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='restaurant_staff'
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Restoran xodimi'
        verbose_name_plural = 'Restoran xodimlari'
        unique_together = ['user', 'restaurant']
    
    def __str__(self):
        return f'{self.user} @ {self.restaurant.name}'


class RestaurantBookingLead(BaseModel):
    """Restoran bron leadlari — mijoz so'rovlari va ularni qabul qilish/rad etish."""
    
    # Lead expiry settings (in hours)
    LEAD_EXPIRY_HOURS = 24  # Leads expire after 24 hours if not accepted
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        ACCEPTED = 'accepted', 'Qabul qilingan'
        REJECTED = 'rejected', 'Rad etilgan'
        CUSTOMER_NEGOTIATING = 'customer_negotiating', 'Mijoz bilan muzokara'
        CONFIRMED = 'confirmed', 'Tasdiqlangan'
        EXPIRED = 'expired', 'Muddati tugagan'
    
    restaurant = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='booking_leads'
    )
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=20)
    party_size = models.PositiveSmallIntegerField(help_text='Nechta kishi')
    preferred_time = models.TimeField(help_text='Tanlangan vaqt (HH:MM)')
    restaurant_type = models.CharField(
        max_length=20,
        choices=[
            ('casual', 'Casual'),
            ('fine_dining', 'Fine Dining'),
            ('fast_food', 'Fast Food'),
            ('delivery', 'Delivery'),
        ],
        default='casual'
    )
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    accepted_by = models.ForeignKey(
        RestaurantStaff, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='accepted_booking_leads'
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    actual_time = models.TimeField(null=True, blank=True, help_text='Muzokaradan keyingi haqiqiy vaqt')
    notes = models.TextField(blank=True, help_text='Xodim izohlari')
    special_requests = models.TextField(blank=True)
    is_ai_generated = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Restoran bron leadi'
        verbose_name_plural = 'Restoran bron leadlari'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['restaurant', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f'{self.customer_name} - {self.restaurant.name} [{self.get_status_display()}]'
    
    def accept(self, staff):
        """Leadni qabul qilish."""
        if self.status != self.Status.PENDING:
            raise ValueError(f"Lead status {self.status} bo'lganda qabul qilib bo'lmaydi")
        
        self.status = self.Status.ACCEPTED
        self.accepted_by = staff
        self.accepted_at = timezone.now()
        self.save(update_fields=['status', 'accepted_by', 'accepted_at', 'updated_at'])
    
    def reject(self, reason):
        """Leadni rad etish."""
        if self.status != self.Status.PENDING:
            raise ValueError(f"Lead status {self.status} bo'lganda rad etib bo'lmaydi")
        
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.save(update_fields=['status', 'rejection_reason', 'updated_at'])
    
    def update_actual_time(self, new_time):
        """Muzokaradan keyin haqiqiy vaqtni yangilash."""
        if self.status not in [self.Status.ACCEPTED, self.Status.CUSTOMER_NEGOTIATING]:
            raise ValueError("Lead qabul qilingan yoki muzokara bosqichida bo'lishi kerak")
        
        self.actual_time = new_time
        self.status = self.Status.CONFIRMED
        self.save(update_fields=['actual_time', 'status', 'updated_at'])
    
    def expire(self):
        """Mark lead as expired."""
        if self.status != self.Status.PENDING:
            raise ValueError(f"Lead status {self.status} bo'lganda expire qilib bo'lmaydi")
        
        self.status = self.Status.EXPIRED
        self.save(update_fields=['status', 'updated_at'])
    
    @classmethod
    def expire_old_leads(cls):
        """Expire pending leads older than LEAD_EXPIRY_HOURS."""
        from datetime import timedelta
        expiry_threshold = timezone.now() - timedelta(hours=cls.LEAD_EXPIRY_HOURS)
        
        expired_count = cls.objects.filter(
            status=cls.Status.PENDING,
            created_at__lt=expiry_threshold
        ).update(status=cls.Status.EXPIRED)
        
        return expired_count


class MenuCategory(BaseModel):
    branch = models.ForeignKey(
        'crm.Branch', on_delete=models.CASCADE, related_name='menu_categories',
    )
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Menyu kategoriyasi'
        verbose_name_plural = 'Menyu kategoriyalari'
        ordering = ['order', 'name']

    def __str__(self):
        return f'{self.branch.name} — {self.name}'


class MenuItem(BaseModel):
    category = models.ForeignKey(
        MenuCategory, on_delete=models.CASCADE, related_name='items',
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='menu_items/', blank=True, null=True)
    is_available = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Menyu elementi'
        verbose_name_plural = 'Menyu elementlari'
        ordering = ['category__order', 'name']

    def __str__(self):
        return self.name


class FeaturedItem(BaseModel):
    branch = models.ForeignKey(
        'crm.Branch', on_delete=models.CASCADE, related_name='featured_items',
    )
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, null=True, blank=True,
    )
    custom_title = models.CharField(max_length=150, blank=True)
    order = models.PositiveIntegerField(default=0)
    active_from = models.DateTimeField(null=True, blank=True)
    active_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Tavsiya etilgan taklif'
        verbose_name_plural = 'Tavsiya etilgan takliflar'
        ordering = ['order']

    def __str__(self):
        return self.custom_title or (self.menu_item.name if self.menu_item else str(self.id))


@receiver(post_save, sender=RestaurantBookingLead)
def create_inquiry_from_lead(sender, instance, created, **kwargs):
    """AI yaratgan lead bo'lsa, UserInquiry ham yaratish."""
    if not created:
        return
    
    # Faqat AI yaratgan leadlar uchun
    if not instance.is_ai_generated:
        return
    
    # User topishga harakat qilish (customer_phone orqali)
    try:
        from apps.users.models import User
        from apps.support.models import UserInquiry
        
        user = User.objects.filter(phone=instance.customer_phone).first()
        
        if user:
            # UserInquiry yaratish
            UserInquiry.objects.create(
                user=user,
                category=UserInquiry.Category.BOOKING,
                priority=UserInquiry.Priority.MEDIUM,
                subject=f"Restoron bron so'rovi - {instance.restaurant.name}",
                message=f"""
Mijoz: {instance.customer_name}
Telefon: {instance.customer_phone}
Restoran: {instance.restaurant.name}
Kishilar soni: {instance.party_size}
Tanlangan vaqt: {instance.preferred_time}
Restoran turi: {instance.get_restaurant_type_display()}
Maxsus so'rovlar: {instance.special_requests or 'Yo\'q'}

Bu so'rov AI tomonidan yaratilgan.
                """.strip(),
                status=UserInquiry.Status.OPEN
            )
    except Exception as e:
        # Signal xatoliklari lead yaratishga to'sqinlik qilmasligi kerak
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f'Lead {instance.id} uchun UserInquiry yaratib bo\'lmadi: {e}')
