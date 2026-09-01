"""Restaurant vertikaliga xos modellar."""

from django.db import models
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
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        ACCEPTED = 'accepted', 'Qabul qilingan'
        REJECTED = 'rejected', 'Rad etilgan'
        CUSTOMER_NEGOTIATING = 'customer_negotiating', 'Mijoz bilan muzokara'
        CONFIRMED = 'confirmed', 'Tasdiqlangan'
    
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
