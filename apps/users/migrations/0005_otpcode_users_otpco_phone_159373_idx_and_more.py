# Indekslar 0001_initial da allaqachon yaratilgan.
# makemigrations merge migratsiyalar tufayli ularni "yo'q" deb topdi va
# qayta AddIndex yaratdi — bu duplicate index xatosiga olib keladi.
# Bu migratsiya faqat django_migrations jadvalini sinxronlashtiradi.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_merge_vps_and_sync'),
    ]

    operations = []
