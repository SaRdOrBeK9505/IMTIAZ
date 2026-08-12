# Generated manually — remove unused provider choices, AlifPay only

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_alter_payment_provider'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='provider',
            field=models.CharField(
                choices=[('alifpay', 'AlifPay')],
                help_text="To'lov provayderi (hozir faqat AlifPay)",
                max_length=20,
            ),
        ),
    ]
