"""
Integrations app — Tashqi API provayderlar logi.
Adapter pattern: AviakassaAdapter, RailwayAdapter.
TZ 3.4 bo'limiga mos.
"""

from django.db import models
from apps.core.models import BaseModel


class ExternalProviderLog(BaseModel):
    """
    Har bir tashqi API chaqiruvi qayd etiladi —
    debug va monitoring uchun.
    """

    class Provider(models.TextChoices):
        AVIAKASSA = 'aviakassa', 'Aviakassa'
        BOOKHARA  = 'bookhara',  'Bookhara GDS'
        RAILWAY   = 'railway',   "Temir yo'l"
        OTHER     = 'other',     'Boshqa'

    class Method(models.TextChoices):
        SEARCH = 'search', 'Qidiruv'
        GET_PRICE = 'get_price', 'Narx olish'
        CREATE_BOOKING = 'create_booking', 'Bron yaratish'
        CANCEL_BOOKING = 'cancel_booking', 'Bron bekor qilish'
        CHECK_STATUS = 'check_status', 'Holat tekshirish'

    provider = models.CharField(max_length=30, choices=Provider.choices)
    method = models.CharField(max_length=30, choices=Method.choices)
    request_payload = models.JSONField(null=True, blank=True)
    response_payload = models.JSONField(null=True, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    is_success = models.BooleanField(default=False)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    # Qaysi booking uchun
    booking_id = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Tashqi API logi'
        verbose_name_plural = 'Tashqi API loglari'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider', 'method', 'is_success']),
        ]

    def __str__(self):
        return f'{self.provider} | {self.method} | {"OK" if self.is_success else "FAIL"}'
