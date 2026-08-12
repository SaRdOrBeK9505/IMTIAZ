"""Travel vertikal skeleton — kelajakda kengaytiriladi."""

from django.db import models

from apps.core.models import BaseModel


class TourPackageStub(BaseModel):
    """
    Placeholder — haqiqiy TourPackage apps.tours.models da.
    Vertikal app mavjudligi va migratsiya zanjirini ta'minlaydi.
    """
    organization = models.ForeignKey(
        'crm.Organization', on_delete=models.CASCADE, related_name='travel_package_stubs',
    )
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Tur paketi (stub)'
        verbose_name_plural = 'Tur paketlari (stub)'

    def __str__(self):
        return self.name
