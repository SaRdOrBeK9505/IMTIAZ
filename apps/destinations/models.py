"""Destinations — sodda model."""

from django.core.validators import FileExtensionValidator
from django.db import models

from apps.core.models import BaseModel


class Destination(BaseModel):
    """Sayohat destinatsiyasi — kod, nom, guruh va bayroq rasmi."""

    class Group(models.TextChoices):
        POPULAR   = 'popular',   'Популярные'
        SIGNATURE = 'signature', 'IMTIAZ Signature'

    code = models.CharField(
        max_length=20,
        unique=True,
        help_text='ISO 3166-1 alpha-2 kod (tr, ae, jp ...)',
    )
    name = models.CharField(
        max_length=100,
        help_text='Название',
    )
    group = models.CharField(
        max_length=20,
        choices=Group.choices,
        default=Group.POPULAR,
        help_text='Популярные yoki IMTIAZ Signature',
    )
    flag_image = models.ImageField(
        upload_to='destinations/flags/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'svg'])],
        help_text='Bayroq rasmi',
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Destinatsiya'
        verbose_name_plural = 'Destinatsiyalar'
        ordering = ['group', 'order', 'name']
        indexes = [
            models.Index(fields=['group']),
            models.Index(fields=['is_active']),
            models.Index(fields=['code']),
        ]

    def __str__(self):
        return f'[{self.get_group_display()}] {self.code.upper()} — {self.name}'
