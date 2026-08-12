# Generated manually for multi-vertical CRM — step 1

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def populate_business_type(apps, schema_editor):
    Organization = apps.get_model('crm', 'Organization')
    for org in Organization.objects.all():
        if org.org_type == 'tour_company':
            org.business_type = 'travel'
        else:
            org.business_type = 'restaurant'
        org.save(update_fields=['business_type'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('crm', '0002_alter_organization_org_type_restauranttable_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='business_type',
            field=models.CharField(
                choices=[('restaurant', 'Restoran'), ('travel', 'Sayohat kompaniyasi')],
                db_index=True,
                default='restaurant',
                help_text='CRM vertikali: qaysi panel va API namespace ishlatiladi',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='organization',
            name='owner',
            field=models.OneToOneField(
                blank=True,
                help_text='Tashkilot egasi (UserRole.OWNER)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='owned_organization',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(populate_business_type, migrations.RunPython.noop),
    ]
