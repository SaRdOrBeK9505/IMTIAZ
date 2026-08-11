"""
VPS da oldin qo'llangan migratsiya (django_migrations yozuvi bilan mos).

Fresh install: bo'sh (hech narsa qilmaydi).
VPS: allaqachon qo'llangan — qayta ishlamaydi.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = []
