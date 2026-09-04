"""Background Music Management — audio files for restaurants/events."""

from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.conf import settings

from apps.core.models import BaseModel


class BackgroundMusic(BaseModel):
    """Background music tracks for restaurants and events."""
    
    class Mood(models.TextChoices):
        RELAXING = 'relaxing', 'Relaxing'
        ENERGETIC = 'energetic', 'Energetic'
        ROMANTIC = 'romantic', 'Romantic'
        CLASSICAL = 'classical', 'Classical'
        JAZZ = 'jazz', 'Jazz'
        POP = 'pop', 'Pop'
        AMBIENT = 'ambient', 'Ambient'
    
    # Storage quota settings (in bytes)
    MAX_STORAGE_QUOTA = getattr(settings, 'MUSIC_STORAGE_QUOTA', 5 * 1024 * 1024 * 1024)  # 5GB default
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file
    
    title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255, blank=True)
    mood = models.CharField(max_length=20, choices=Mood.choices, default=Mood.RELAXING)
    audio_file = models.FileField(
        upload_to='music/tracks/',
        validators=[FileExtensionValidator(allowed_extensions=['mp3', 'wav', 'ogg'])],
        help_text='Audio file (mp3, wav, ogg) - max 50MB'
    )
    duration_seconds = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Audio duration in seconds (auto-detected on upload)'
    )
    file_size = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='File size in bytes'
    )
    is_active = models.BooleanField(default=False, help_text='Only one track can be active at a time')
    volume = models.PositiveSmallIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Volume level (0-100)'
    )
    loop = models.BooleanField(default=True, help_text='Loop the track')
    fade_in_seconds = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(30)],
        help_text='Fade in duration (seconds)'
    )
    fade_out_seconds = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(30)],
        help_text='Fade out duration (seconds)'
    )
    tags = models.JSONField(default=list, blank=True, help_text='Tags for filtering')
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Fon musiqasi'
        verbose_name_plural = 'Fon musiqalari'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['mood']),
        ]
    
    def __str__(self):
        return f'{self.title} - {self.artist or "Unknown"}'
    
    @classmethod
    def get_total_storage_used(cls):
        """Calculate total storage used by all music files."""
        total = cls.objects.aggregate(total=models.Sum('file_size'))['total'] or 0
        return total
    
    @classmethod
    def get_storage_quota(cls):
        """Get the storage quota limit."""
        return cls.MAX_STORAGE_QUOTA
    
    @classmethod
    def get_storage_available(cls):
        """Calculate remaining storage available."""
        used = cls.get_total_storage_used()
        return max(0, cls.get_storage_quota() - used)
    
    @classmethod
    def get_storage_percentage(cls):
        """Get storage usage percentage."""
        quota = cls.get_storage_quota()
        used = cls.get_total_storage_used()
        return (used / quota * 100) if quota > 0 else 0
    
    def clean(self):
        """Validate file size and ensure only one active track."""
        # Validate file size (50MB limit)
        if self.audio_file:
            file_size = self.audio_file.size
            if file_size > self.MAX_FILE_SIZE:
                raise ValidationError(f'Audio file size must not exceed {self.MAX_FILE_SIZE / (1024*1024):.0f}MB')
            
            # Check storage quota
            current_used = self.__class__.get_total_storage_used()
            if self.id:
                # If updating, subtract old file size
                old_file = self.__class__.objects.filter(id=self.id).first()
                if old_file and old_file.file_size:
                    current_used -= old_file.file_size
            
            if current_used + file_size > self.MAX_STORAGE_QUOTA:
                available = self.__class__.get_storage_available()
                raise ValidationError(
                    f'Not enough storage space. Available: {available / (1024*1024):.1f}MB, '
                    f'Required: {file_size / (1024*1024):.1f}MB'
                )
            
            self.file_size = file_size
        
        # Ensure only one active track
        if self.is_active:
            active_tracks = BackgroundMusic.objects.filter(is_active=True).exclude(id=self.id)
            if active_tracks.exists():
                raise ValidationError('Only one track can be active at a time. Please deactivate other tracks first.')
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Delete file from storage when model is deleted — S3/Spaces bilan ham ishlaydi."""
        if self.audio_file:
            self.audio_file.delete(save=False)
        super().delete(*args, **kwargs)
    
    def activate(self):
        """Activate this track and deactivate all others."""
        BackgroundMusic.objects.filter(is_active=True).update(is_active=False)
        self.is_active = True
        self.save(update_fields=['is_active', 'updated_at'])
    
    def deactivate(self):
        """Deactivate this track."""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
    
    @classmethod
    def get_active_track(cls):
        """Get the currently active track."""
        return cls.objects.filter(is_active=True).first()
