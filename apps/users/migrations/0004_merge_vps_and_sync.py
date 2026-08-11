"""
VPS (0003_alter_user_role) va git (0003_user_email) tarmoqlarini birlashtirish.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_alter_user_role'),
        ('users', '0003_user_email'),
    ]

    operations = []
