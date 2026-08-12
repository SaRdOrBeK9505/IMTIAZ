# Generated manually — travel vertical skeleton

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0003_organization_business_type_and_owner'),
    ]

    operations = [
        migrations.CreateModel(
            name='TourPackageStub',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('is_active', models.BooleanField(default=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='travel_package_stubs', to='crm.organization')),
            ],
            options={
                'verbose_name': 'Tur paketi (stub)',
                'verbose_name_plural': 'Tur paketlari (stub)',
            },
        ),
    ]
