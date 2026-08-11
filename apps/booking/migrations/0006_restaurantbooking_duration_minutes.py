from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0005_tourbooking_availability_tourbooking_booking_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='restaurantbooking',
            name='duration_minutes',
            field=models.PositiveSmallIntegerField(
                default=120,
                help_text='Bron davomiyligi (daqiqa)',
            ),
        ),
    ]
