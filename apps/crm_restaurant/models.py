"""Restaurant vertikaliga xos modellar."""

from django.db import models

from apps.core.models import BaseModel


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
