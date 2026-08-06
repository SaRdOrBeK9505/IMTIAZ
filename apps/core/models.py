"""
Core — umumiy abstract modellar va yordamchi sinflar.
Barcha boshqa app'lar shu modulga tayanadi.
"""

import uuid
from django.db import models


class TimeStampedModel(models.Model):
    """Har bir model uchun created_at / updated_at avtomatik qo'shadi."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Primary key sifatida UUID ishlatadigan abstract model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    """UUID + timestamps — loyihadagi asosiy abstract model."""

    class Meta:
        abstract = True
