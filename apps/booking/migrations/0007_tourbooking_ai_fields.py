from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0006_restaurantbooking_duration_minutes'),
    ]

    operations = [
        migrations.AddField(
            model_name='tourbooking',
            name='ai_analysis',
            field=models.TextField(
                blank=True,
                help_text='AI tomonidan shakllangan mijoz/tur tahlili matni',
            ),
        ),
        migrations.AddField(
            model_name='tourbooking',
            name='ai_reprocessed',
            field=models.BooleanField(
                default=False,
                help_text='AI qayta ishlagan ariza belgisi',
            ),
        ),
    ]
