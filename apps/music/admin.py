"""Background Music admin configuration."""

from django.contrib import admin

from .models import BackgroundMusic


@admin.register(BackgroundMusic)
class BackgroundMusicAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'artist', 'mood', 'is_active', 'volume',
        'duration_seconds', 'file_size_mb', 'created_at'
    ]
    list_filter = ['mood', 'is_active', 'created_at']
    search_fields = ['title', 'artist', 'description']
    readonly_fields = ['file_size', 'duration_seconds', 'created_at', 'updated_at']
    list_editable = ['is_active', 'volume']
    
    def file_size_mb(self, obj):
        """Display file size in MB."""
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return None
    file_size_mb.short_description = 'Size (MB)'
