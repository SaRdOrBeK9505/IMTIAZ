"""Destination Management — countries, destinations, and images."""

import os
from io import BytesIO
from django.db import models
from django.core.validators import FileExtensionValidator
from django.core.files.base import ContentFile
from PIL import Image

from apps.core.models import BaseModel

# Thumbnail settings
THUMBNAIL_SIZE = (300, 200)  # Width, Height
THUMBNAIL_QUALITY = 85


class Country(BaseModel):
    """Country model for destinations."""
    
    name = models.CharField(max_length=100, unique=True)
    name_uz = models.CharField(max_length=100, blank=True, help_text='Uzbek name')
    code = models.CharField(max_length=3, unique=True, help_text='ISO 3166-1 alpha-2 code (e.g., UZ, TR)')
    flag_emoji = models.CharField(max_length=10, blank=True, help_text='Country flag emoji')
    currency = models.CharField(max_length=10, blank=True, help_text='Currency code (e.g., USD, EUR)')
    calling_code = models.CharField(max_length=10, blank=True, help_text='Phone calling code (e.g., +998)')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = 'Mamlakat'
        verbose_name_plural = 'Mamlakatlar'
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f'{self.flag_emoji} {self.name}' if self.flag_emoji else self.name


class Destination(BaseModel):
    """Destination model (cities, regions, tourist spots)."""
    
    class Category(models.TextChoices):
        CITY = 'city', 'Shahar'
        BEACH = 'beach', 'Dengiz sohili'
        MOUNTAIN = 'mountain', 'Tog\''
        HISTORICAL = 'historical', 'Tarixiy joy'
        NATURE = 'nature', 'Tabiat'
        ADVENTURE = 'adventure', 'Sarguzasht'
        CULTURAL = 'cultural', 'Madaniyat'
        MODERN = 'modern', 'Zamonaviy'
    
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='destinations')
    name = models.CharField(max_length=255)
    name_uz = models.CharField(max_length=255, blank=True, help_text='Uzbek name')
    description = models.TextField(blank=True)
    description_uz = models.TextField(blank=True, help_text='Uzbek description')
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.CITY)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0, help_text='Average rating (0-5)')
    review_count = models.PositiveIntegerField(default=0)
    is_popular = models.BooleanField(default=False, help_text='Popular destination')
    is_active = models.BooleanField(default=True)
    featured_image = models.ImageField(
        upload_to='destinations/featured/',
        null=True, blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])]
    )
    featured_image_thumbnail = models.ImageField(
        upload_to='destinations/featured/thumbnails/',
        null=True, blank=True,
        help_text='Auto-generated thumbnail'
    )
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = 'Manzil'
        verbose_name_plural = 'Manzillar'
        ordering = ['-is_popular', 'order', 'name']
        indexes = [
            models.Index(fields=['country', 'is_active']),
            models.Index(fields=['category']),
            models.Index(fields=['is_popular']),
        ]
    
    def __str__(self):
        return f'{self.name}, {self.country.name}'
    
    def update_rating(self, new_rating):
        """Update average rating."""
        total_score = self.rating * self.review_count + new_rating
        self.review_count += 1
        self.rating = total_score / self.review_count
        self.save(update_fields=['rating', 'review_count', 'updated_at'])
    
    def generate_thumbnail(self):
        """Generate thumbnail for featured image."""
        if not self.featured_image:
            return
        
        try:
            # Open the image
            img = Image.open(self.featured_image)
            
            # Convert to RGB if necessary (for JPEG)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Create thumbnail
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            
            # Save to BytesIO
            thumb_io = BytesIO()
            img.save(thumb_io, format='JPEG', quality=THUMBNAIL_QUALITY)
            thumb_io.seek(0)
            
            # Generate filename
            filename = f"thumb_{os.path.basename(self.featured_image.name)}"
            if not filename.lower().endswith('.jpg'):
                filename = f"{filename.rsplit('.', 1)[0]}.jpg"
            
            # Save thumbnail
            self.featured_image_thumbnail.save(
                filename,
                ContentFile(thumb_io.getvalue()),
                save=False
            )
        except Exception as e:
            # Log error but don't fail the save
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f'Failed to generate thumbnail for destination {self.id}: {e}')
    
    def save(self, *args, **kwargs):
        # Generate thumbnail on save if featured image is new
        if self.featured_image and (not self.featured_image_thumbnail or self._state.adding):
            self.generate_thumbnail()
        super().save(*args, **kwargs)


class DestinationImage(BaseModel):
    """Multiple images for a destination."""
    
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(
        upload_to='destinations/images/',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])]
    )
    thumbnail = models.ImageField(
        upload_to='destinations/images/thumbnails/',
        null=True, blank=True,
        help_text='Auto-generated thumbnail'
    )
    caption = models.CharField(max_length=255, blank=True)
    caption_uz = models.CharField(max_length=255, blank=True, help_text='Uzbek caption')
    is_primary = models.BooleanField(default=False, help_text='Primary image for destination')
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = 'Manzil rasmi'
        verbose_name_plural = 'Manzil rasmlari'
        ordering = ['-is_primary', 'order', 'created_at']
        indexes = [
            models.Index(fields=['destination', 'is_primary']),
        ]
    
    def __str__(self):
        return f'{self.destination.name} - {self.caption or "Image"}'
    
    def generate_thumbnail(self):
        """Generate thumbnail for image."""
        if not self.image:
            return
        
        try:
            # Open the image
            img = Image.open(self.image)
            
            # Convert to RGB if necessary (for JPEG)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Create thumbnail
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            
            # Save to BytesIO
            thumb_io = BytesIO()
            img.save(thumb_io, format='JPEG', quality=THUMBNAIL_QUALITY)
            thumb_io.seek(0)
            
            # Generate filename
            filename = f"thumb_{os.path.basename(self.image.name)}"
            if not filename.lower().endswith('.jpg'):
                filename = f"{filename.rsplit('.', 1)[0]}.jpg"
            
            # Save thumbnail
            self.thumbnail.save(
                filename,
                ContentFile(thumb_io.getvalue()),
                save=False
            )
        except Exception as e:
            # Log error but don't fail the save
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f'Failed to generate thumbnail for destination image {self.id}: {e}')
    
    def save(self, *args, **kwargs):
        # Generate thumbnail on save if image is new
        if self.image and (not self.thumbnail or self._state.adding):
            self.generate_thumbnail()
        
        # Ensure only one primary image per destination
        if self.is_primary:
            DestinationImage.objects.filter(
                destination=self.destination,
                is_primary=True
            ).exclude(id=self.id).update(is_primary=False)
        super().save(*args, **kwargs)
