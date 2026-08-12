# Generated manually — restaurant menu models

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0003_organization_business_type_and_owner'),
    ]

    operations = [
        migrations.CreateModel(
            name='MenuCategory',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('order', models.PositiveIntegerField(default=0)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='menu_categories', to='crm.branch')),
            ],
            options={
                'verbose_name': 'Menyu kategoriyasi',
                'verbose_name_plural': 'Menyu kategoriyalari',
                'ordering': ['order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='MenuItem',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=150)),
                ('description', models.TextField(blank=True)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('image', models.ImageField(blank=True, null=True, upload_to='menu_items/')),
                ('is_available', models.BooleanField(default=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='crm_restaurant.menucategory')),
            ],
            options={
                'verbose_name': 'Menyu elementi',
                'verbose_name_plural': 'Menyu elementlari',
                'ordering': ['category__order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='FeaturedItem',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('custom_title', models.CharField(blank=True, max_length=150)),
                ('order', models.PositiveIntegerField(default=0)),
                ('active_from', models.DateTimeField(blank=True, null=True)),
                ('active_until', models.DateTimeField(blank=True, null=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='featured_items', to='crm.branch')),
                ('menu_item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='crm_restaurant.menuitem')),
            ],
            options={
                'verbose_name': 'Tavsiya etilgan taklif',
                'verbose_name_plural': 'Tavsiya etilgan takliflar',
                'ordering': ['order'],
            },
        ),
    ]
