# Yangi CRM notification turlari — new_lead

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('booking_confirmed', 'Bron tasdiqlandi'),
                    ('booking_cancelled', 'Bron bekor qilindi'),
                    ('payment_success', 'To\'lov muvaffaqiyatli'),
                    ('payment_failed', 'To\'lov amalga oshmadi'),
                    ('booking_reminder', 'Bron eslatmasi'),
                    ('ai_suggestion', 'AI taklifi'),
                    ('subscription_renewal', 'Obuna yangilandi'),
                    ('subscription_past_due', 'Obuna to\'lovi o\'tmadi'),
                    ('waitlist_approved', 'A\'zolik tasdiqlandi'),
                    ('new_lead', 'Yangi lead (CRM)'),
                    ('general', 'Umumiy'),
                ],
                max_length=40,
            ),
        ),
    ]
