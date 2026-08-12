"""Lead pipeline migratsiyasi."""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0009_booking_settlement_saga'),
        ('crm', '0003_organization_business_type_and_owner'),
        ('crm_core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Lead',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('vertical', models.CharField(choices=[('restaurant', 'Restoran'), ('travel', 'Sayohat')], db_index=True, max_length=20)),
                ('stage', models.CharField(choices=[('new', 'Yangi'), ('contacted', 'Bog\'lanildi'), ('qualified', 'Tasdiqlangan'), ('won', 'Yutildi'), ('lost', 'Yo\'qotildi')], db_index=True, default='new', max_length=20)),
                ('title', models.CharField(max_length=255)),
                ('customer_name', models.CharField(blank=True, max_length=150)),
                ('customer_phone', models.CharField(blank=True, max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_leads', to=settings.AUTH_USER_MODEL)),
                ('booking', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='crm_lead', to='booking.booking')),
                ('branch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leads', to='crm.branch')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leads', to='crm.organization')),
            ],
            options={
                'verbose_name': 'CRM lead',
                'verbose_name_plural': 'CRM leadlar',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['organization', 'vertical', 'stage'], name='crm_core_le_org_vert_stage_idx'),
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['organization', 'created_at'], name='crm_core_le_org_created_idx'),
        ),
    ]
