"""App Settings — dynamic configuration for AI assistant name and other settings."""

from django.db import models

from apps.core.models import BaseModel


class AppSetting(BaseModel):
    """Dynamic app settings (AI assistant name, etc.)."""
    
    class SettingType(models.TextChoices):
        AI_ASSISTANT_NAME = 'ai_assistant_name', 'AI Assistant Name'
        COMPANY_NAME = 'company_name', 'Company Name'
        SUPPORT_PHONE = 'support_phone', 'Support Phone'
        SUPPORT_EMAIL = 'support_email', 'Support Email'
        CURRENCY = 'currency', 'Default Currency'
        TIMEZONE = 'timezone', 'Default Timezone'
    
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.CharField(max_length=255)
    setting_type = models.CharField(max_length=30, choices=SettingType.choices)
    description = models.TextField(blank=True, help_text='Setting description')
    is_public = models.BooleanField(default=False, help_text='Can be accessed by public API')
    
    class Meta:
        verbose_name = 'Ilova sozlamasi'
        verbose_name_plural = 'Ilova sozlamalari'
        ordering = ['key']
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['setting_type']),
        ]
    
    def __str__(self):
        return f'{self.key}: {self.value}'
    
    @classmethod
    def get_value(cls, key, default=None):
        """Get setting value by key."""
        try:
            setting = cls.objects.get(key=key)
            return setting.value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_value(cls, key, value, setting_type, description=''):
        """Set setting value."""
        setting, created = cls.objects.update_or_create(
            key=key,
            defaults={
                'value': value,
                'setting_type': setting_type,
                'description': description,
            }
        )
        if not created:
            setting.value = value
            setting.setting_type = setting_type
            if description:
                setting.description = description
            setting.save()
        return setting
    
    @classmethod
    def get_ai_assistant_name(cls):
        """Get AI assistant name (default: 'Bike')."""
        return cls.get_value('ai_assistant_name', default='Bike')
    
    @classmethod
    def set_ai_assistant_name(cls, name):
        """Set AI assistant name."""
        return cls.set_value(
            key='ai_assistant_name',
            value=name,
            setting_type=cls.SettingType.AI_ASSISTANT_NAME,
            description='AI assistant display name'
        )
