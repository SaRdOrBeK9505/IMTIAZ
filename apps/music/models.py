"""Background Music Management — audio files for restaurants/events."""

from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator

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
    
    def clean(self):
        """Validate file size and ensure only one active track."""
        # Validate file size (50MB limit)
        if self.audio_file:
            if self.audio_file.size > 50 * 1024 * 1024:  # 50MB
                raise ValidationError('Audio file size must not exceed 50MB')
            self.file_size = self.audio_file.size
        
        # Ensure only one active track
        if self.is_active:
            active_tracks = BackgroundMusic.objects.filter(is_active=True).exclude(id=self.id)
            if active_tracks.exists():
                raise ValidationError('Only one track can be active at a time. Please deactivate other tracks first.')
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
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
