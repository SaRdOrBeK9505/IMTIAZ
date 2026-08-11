from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qr_codes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='qrcoderedemption',
            name='customer_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='qrcoderedemption',
            name='customer_phone',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
