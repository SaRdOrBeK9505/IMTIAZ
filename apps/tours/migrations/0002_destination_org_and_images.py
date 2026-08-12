"""Yo'nalishlar — kompaniyaga bog'liq + galereya rasmlari."""

import django.db.models.deletion as deletion
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0003_organization_business_type_and_owner'),
        ('tours', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tourdestination',
            name='slug',
            field=models.SlugField(blank=True, max_length=170),
        ),
        migrations.AddField(
            model_name='tourdestination',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                help_text="Tur kompaniyasi — CRM orqali yaratilgan yo'nalishlar",
                null=True,
                on_delete=deletion.CASCADE,
                related_name='tour_destinations',
                to='crm.organization',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='tourdestination',
            unique_together=set(),
        ),
        migrations.CreateModel(
            name='TourDestinationImage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('image', models.ImageField(upload_to='tours/destinations/gallery/')),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('is_cover', models.BooleanField(default=False)),
                ('destination', models.ForeignKey(
                    on_delete=deletion.CASCADE,
                    related_name='images',
                    to='tours.tourdestination',
                )),
            ],
            options={
                'verbose_name': "Yo'nalish rasmi",
                'verbose_name_plural': "Yo'nalish rasmlari",
                'ordering': ['sort_order', 'created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='tourdestination',
            constraint=models.UniqueConstraint(
                condition=models.Q(('organization__isnull', False)),
                fields=('organization', 'country', 'city'),
                name='unique_org_destination_location',
            ),
        ),
        migrations.AddConstraint(
            model_name='tourdestination',
            constraint=models.UniqueConstraint(
                condition=models.Q(('organization__isnull', True)),
                fields=('country', 'city'),
                name='unique_global_destination_location',
            ),
        ),
    ]
