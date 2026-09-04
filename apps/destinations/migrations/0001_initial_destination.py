# Generated manually — simplified Destination model

import django.core.validators
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Destination',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(
                    max_length=10, unique=True,
                    help_text='ISO 3166-1 alpha-2 kod (tr, ae, jp ...)',
                )),
                ('name', models.CharField(max_length=100, help_text='Название')),
                ('group', models.CharField(
                    max_length=20,
                    choices=[('popular', 'Популярные'), ('signature', 'IMTIAZ Signature')],
                    default='popular',
                )),
                ('flag_image', models.ImageField(
                    upload_to='destinations/flags/',
                    null=True, blank=True,
                    validators=[django.core.validators.FileExtensionValidator(
                        allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'svg']
                    )],
                )),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Destinatsiya',
                'verbose_name_plural': 'Destinatsiyalar',
                'ordering': ['group', 'order', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='destination',
            index=models.Index(fields=['group'], name='destination_group_idx'),
        ),
        migrations.AddIndex(
            model_name='destination',
            index=models.Index(fields=['is_active'], name='destination_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='destination',
            index=models.Index(fields=['code'], name='destination_code_idx'),
        ),
    ]
