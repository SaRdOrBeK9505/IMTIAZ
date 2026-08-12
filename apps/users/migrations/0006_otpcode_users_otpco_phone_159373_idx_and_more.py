# Indekslar DB da 0001_initial orqali allaqachon mavjud.
# SeparateDatabaseAndState: Django state'ga qo'shamiz, DB ga tegmaymiz.
# Aks holda sqlite "index already exists" xatosi chiqadi.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_otpcode_users_otpco_phone_159373_idx_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name='otpcode',
                    index=models.Index(
                        fields=['phone', 'purpose', 'is_used', 'expires_at'],
                        name='users_otpco_phone_159373_idx',
                    ),
                ),
                migrations.AddIndex(
                    model_name='userdevice',
                    index=models.Index(
                        fields=['user', 'is_active'],
                        name='users_userd_user_id_a5f926_idx',
                    ),
                ),
                migrations.AddIndex(
                    model_name='userdevice',
                    index=models.Index(
                        fields=['refresh_token_jti'],
                        name='users_userd_refresh_95449e_idx',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
