from django.apps import AppConfig


class CrmCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.crm_core'
    verbose_name = 'CRM Core'

    def ready(self):
        from apps.crm_core.verticals import registry  # noqa: F401
