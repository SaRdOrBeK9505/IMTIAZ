"""Travel Content — Reels-uslubidagi ilhom kartochkalari va IMTIAZ Travels kuratsiyalangan turlar."""

from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator

from apps.core.models import BaseModel

VIDEO_EXTENSIONS = ['mp4', 'mov', 'webm']
MAX_VIDEO_SIZE_MB = 100
MAX_IMAGE_SIZE_MB = 10


def _validate_file_size(file_field, max_mb: int):
    if file_field and file_field.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Fayl hajmi {max_mb}MB dan oshmasligi kerak.")


class TravelReel(BaseModel):
    """'Вдохновение для ваших путешествий' bo'limi — qisqa reels-uslubidagi kartochka."""

    class MediaType(models.TextChoices):
        IMAGE = 'image', 'Rasm'
        VIDEO = 'video', 'Video'

    title = models.CharField(max_length=150, help_text='Masalan: "St. Moritz"')
    subtitle = models.CharField(
        max_length=255, blank=True,
        help_text='Qisqa tagline — kartochkada ko\'rinadi. Masalan: "Зима, лыжи и стиль"',
    )
    description = models.TextField(
        blank=True,
        help_text="To'liq matn — reels fullscreen ochilganda ko'rsatiladi",
    )
    media_type = models.CharField(max_length=5, choices=MediaType.choices, default=MediaType.IMAGE)

    cover_image = models.ImageField(
        upload_to='travel_content/reels/covers/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])],
        help_text="MAJBURIY — kartochka/thumbnail rasmi (video post uchun ham kerak)",
        blank=True, null=True,
    )
    video_file = models.FileField(
        upload_to='travel_content/reels/videos/',
        null=True, blank=True,
        validators=[FileExtensionValidator(VIDEO_EXTENSIONS)],
        help_text="media_type='video' bo'lganda MAJBURIY",
    )

    destination = models.ForeignKey(
        'destinations.Destination', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reels',
        help_text="Ixtiyoriy — qaysi manzilga tegishli ekanini bog'lash uchun",
    )

    view_count = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0, help_text="Kichik raqam — birinchi ko'rsatiladi")

    class Meta:
        verbose_name = 'Sayohat ilhomi (Reel)'
        verbose_name_plural = "Sayohat ilhomlari (Reels)"
        ordering = ['sort_order', '-created_at']
        indexes = [models.Index(fields=['is_active', 'sort_order'])]

    def __str__(self):
        return self.title

    def clean(self):
        if self.media_type == self.MediaType.VIDEO and not self.video_file:
            raise ValidationError({'video_file': "media_type='video' bo'lganda video_file majburiy."})
        if self.media_type == self.MediaType.IMAGE and self.video_file:
            raise ValidationError({'video_file': "media_type='image' bo'lganda video_file bo'sh bo'lishi kerak."})
        _validate_file_size(self.cover_image, MAX_IMAGE_SIZE_MB)
        _validate_file_size(self.video_file, MAX_VIDEO_SIZE_MB)

    def delete(self, *args, **kwargs):
        # Storage-agnostik o'chirish — S3/Spaces bilan ham ishlaydi (.path ISHLATMA)
        if self.cover_image:
            self.cover_image.delete(save=False)
        if self.video_file:
            self.video_file.delete(save=False)
        super().delete(*args, **kwargs)


class CuratedTrip(BaseModel):
    """'Путешествия IMTIAZ' — IMTIAZ jamoasi tomonidan tayyorlangan tayyor marshrut kartochkasi."""

    class PriceUnit(models.TextChoices):
        PER_ROUTE = 'route', 'Marshrut uchun'
        PER_PERSON = 'person', 'Kishi boshiga'

    title = models.CharField(max_length=150, help_text='Masalan: "IMTIAZ Dubai Luxury"')
    subtitle = models.CharField(max_length=255, blank=True, help_text='Masalan: "Дубай + сафари по пустыне"')
    short_description = models.CharField(
        max_length=500, blank=True,
        help_text='Kartochkada ko\'rinadigan qisqa matn: "Роскошь, шопинг и незабываемые приключения..."',
    )
    full_description = models.TextField(blank=True, help_text="Detail sahifada to'liq matn")

    cover_image = models.ImageField(
        upload_to='travel_content/curated_trips/covers/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])],
        help_text="Video ustida play tugmasi bilan ko'rinadigan asosiy rasm — MAJBURIY",
        blank=True, null=True,
    )
    video_file = models.FileField(
        upload_to='travel_content/curated_trips/videos/',
        null=True, blank=True,
        validators=[FileExtensionValidator(VIDEO_EXTENSIONS)],
        help_text="MAJBURIY — bu model uchun video har doim bo'lishi shart (image-only variant yo'q)",
    )

    destination = models.ForeignKey(
        'destinations.Destination', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='curated_trips',
    )

    duration_days_min = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)], help_text='Masalan 4 ("4-6 kun" bo\'lsa)')
    duration_days_max = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)], help_text='Masalan 6')
    group_size_min = models.PositiveSmallIntegerField(default=1)
    group_size_max = models.PositiveSmallIntegerField(default=2, help_text='Kartochkada ko\'rsatiladigan odam soni (masalan "2 kishi")')

    price_from = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    price_unit = models.CharField(max_length=10, choices=PriceUnit.choices, default=PriceUnit.PER_ROUTE)

    is_verified_by_imtiaz = models.BooleanField(
        default=True, help_text='"Проверено командой IMTIAZ" belgisini ko\'rsatish/yashirish',
    )
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Bosh sahifada tepada ko'rsatiladimi")
    sort_order = models.PositiveSmallIntegerField(default=0)

    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'IMTIAZ Travels — kuratsiyalangan tur'
        verbose_name_plural = 'IMTIAZ Travels — kuratsiyalangan turlar'
        ordering = ['sort_order', '-is_featured', '-created_at']
        indexes = [models.Index(fields=['is_active', 'sort_order'])]

    def __str__(self):
        return self.title

    @property
    def duration_display(self) -> str:
        if self.duration_days_min == self.duration_days_max:
            return f'{self.duration_days_min} kun'
        return f'{self.duration_days_min}-{self.duration_days_max} kun'

    def clean(self):
        if self.duration_days_max < self.duration_days_min:
            raise ValidationError({'duration_days_max': "Maksimal davomiylik minimaldan kichik bo'lmasligi kerak."})
        if self.group_size_max < self.group_size_min:
            raise ValidationError({'group_size_max': "Maksimal guruh hajmi minimaldan kichik bo'lmasligi kerak."})
        _validate_file_size(self.cover_image, MAX_IMAGE_SIZE_MB)
        _validate_file_size(self.video_file, MAX_VIDEO_SIZE_MB)

    def delete(self, *args, **kwargs):
        if self.cover_image:
            self.cover_image.delete(save=False)
        if self.video_file:
            self.video_file.delete(save=False)
        super().delete(*args, **kwargs)


class CuratedTripImage(BaseModel):
    """CuratedTrip uchun qo'shimcha galereya rasmlari (detail sahifada)."""

    trip = models.ForeignKey(CuratedTrip, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(
        upload_to='travel_content/curated_trips/gallery/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])],
        blank=True, null=True,
    )
    caption = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Kuratsiyalangan tur galereya rasmi'
        verbose_name_plural = 'Kuratsiyalangan tur galereya rasmlari'
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return f'{self.trip.title} — rasm #{self.sort_order}'

    def delete(self, *args, **kwargs):
        if self.image:
            self.image.delete(save=False)
        super().delete(*args, **kwargs)

