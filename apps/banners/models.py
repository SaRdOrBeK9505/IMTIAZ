"""Banners app — reklama bannerlari uchun model."""

from django.db import models
from apps.core.models import BaseModel


class Banner(BaseModel):
    """Reklama bannerlari."""
    
    class LinkChoices(models.TextChoices):
        AI = '/ai', 'Imtiaz AI'
        TOURS = '/services/tours', 'Туры'
        TRAVEL = '/services/travel', 'Путешествия'
        RESTAURANT = '/services/restaurant', 'Рестораны'
        EVENTS = '/events', 'События'
        BONUSES = '/bonuses', 'Бонусы'
    
    title = models.CharField(max_length=255, help_text='Название')
    description = models.TextField(blank=True, help_text='Краткое описание')
    image_url = models.URLField(blank=True, help_text='Фото URL')
    link = models.CharField(
        max_length=50,
        choices=LinkChoices.choices,
        help_text='Ссылка (dropdown)'
    )
    order = models.IntegerField(default=0, help_text='Banner tartibi')
    is_active = models.BooleanField(default=True, help_text='Faollik')
    
    class Meta:
        verbose_name = 'Banner'
        verbose_name_plural = 'Bannerlar'
        ordering = ['order', '-created_at']
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]
    
    def __str__(self):
        return self.title
