"""
Services — ServiceIcon, ServiceColor, Service modellari.

ServiceIcon  — ikonkalar kutubxonasi (lucide-react slug yoki SVG/rasm)
ServiceColor — rang palitasi (hex kod)
Service      — foydalanuvchiga ko'rsatiladigan xizmat kartochkasi
"""

from django.db import models
from django.utils.text import slugify

from apps.core.models import BaseModel


class ServiceIcon(BaseModel):
    """
    Bazadagi tayyor ikonkalar to'plami.
    Frontend lucide-react ishlatsa — slug maydoni icon nomini saqlaydi (masalan: 'plane').
    """

    name = models.CharField(
        max_length=100,
        verbose_name='Nomi',
    )
    slug = models.SlugField(
        unique=True,
        blank=True,
        help_text="Frontendda ishlatiladigan icon kaliti (masalan: 'plane', 'fork-knife', 'car')",
    )
    svg = models.TextField(
        blank=True,
        null=True,
        help_text='SVG kod sifatida saqlash (ixtiyoriy)',
    )
    image = models.ImageField(
        upload_to='service_icons/',
        blank=True,
        null=True,
        help_text='Rasm fayl sifatida saqlash (ixtiyoriy)',
    )

    class Meta:
        verbose_name = 'Icon'
        verbose_name_plural = 'Iconlar'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ServiceColor(BaseModel):
    """Bazadagi tayyor ranglar to'plami — rang tanlash palitasi."""

    name = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Nomi (ixtiyoriy)',
        help_text="Masalan: 'Binafsha', 'Ko'k'",
    )
    hex_code = models.CharField(
        max_length=7,
        unique=True,
        help_text='Masalan: #8B5CF6',
    )

    class Meta:
        verbose_name = 'Rang'
        verbose_name_plural = 'Ranglar'
        ordering = ['name', 'hex_code']

    def __str__(self):
        return f"{self.name or ''} ({self.hex_code})".strip()


class Service(BaseModel):
    """
    Foydalanuvchiga ko'rsatiladigan xizmat kartochkasi.
    Masalan: Путешествия, Медицина, Рестораны va h.k.
    """

    name = models.CharField(
        max_length=255,
        verbose_name='Nomi',
    )
    slug = models.SlugField(
        unique=True,
        blank=True,
        help_text='Avtomatik name dan generatsiya qilinadi',
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Tavsif',
    )
    icon = models.ForeignKey(
        ServiceIcon,
        on_delete=models.PROTECT,
        related_name='services',
        verbose_name='Icon',
    )
    color = models.ForeignKey(
        ServiceColor,
        on_delete=models.PROTECT,
        related_name='services',
        verbose_name='Rang',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Aktiv',
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text='Tartib raqami — pastroq raqam oldinroq chiqadi',
        verbose_name='Tartib',
    )

    class Meta:
        verbose_name = 'Xizmat'
        verbose_name_plural = 'Xizmatlar'
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['order']),
            models.Index(fields=['slug']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
