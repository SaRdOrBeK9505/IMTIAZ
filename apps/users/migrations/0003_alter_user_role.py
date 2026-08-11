"""
VPS da oldin qo'llangan migratsiya (django_migrations yozuvi bilan mos).

Fresh install: bo'sh.
VPS: allaqachon qo'llangan.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_fix_missing_columns'),
    ]

    operations = []
