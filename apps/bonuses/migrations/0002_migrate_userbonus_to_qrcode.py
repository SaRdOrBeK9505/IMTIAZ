from django.db import migrations


def migrate_userbonus_forward(apps, schema_editor):
    UserBonus = apps.get_model('bonuses', 'UserBonus')
    QRCode = apps.get_model('qr_codes', 'QRCode')
    QRCodeRedemption = apps.get_model('qr_codes', 'QRCodeRedemption')

    for ub in UserBonus.objects.select_related('bonus_category', 'user').all():
        cat = ub.bonus_category
        qr = QRCode.objects.create(
            organization=None,   # eski UserBonus'lar tashkilotga bog'lanmagan edi
            source_template=cat,
            assigned_user=ub.user,
            code=(ub.qr_code or f'MIGR-{ub.id.hex[:12].upper()}')[:20],
            qr_image=ub.qr_code_image,
            title=cat.name,
            description=cat.description,
            qr_type='discount_percent' if cat.discount_percentage else 'discount_fixed',
            discount_value=cat.discount_percentage or cat.discount_amount or 0,
            minimum_order_amount=cat.min_purchase,
            applicable_services=[cat.service_type],
            service_type=cat.service_type,
            max_total_uses=cat.max_usage_count,
            max_uses_per_user=1,
            total_used_count=1 if ub.is_used else 0,
            valid_from=cat.valid_from,
            valid_until=cat.valid_until,
            is_active=cat.is_active,
        )
        if ub.is_used:
            QRCodeRedemption.objects.create(
                qr_code=qr,
                user=ub.user,
                booking=ub.booking,
                service_type=cat.service_type,
                status='applied',
            )


def migrate_userbonus_backward(apps, schema_editor):
    pass  # bir tomonlama migratsiya — orqaga qaytarish shart emas


class Migration(migrations.Migration):
    dependencies = [
        ('bonuses', '0001_initial'),
        ('qr_codes', '0003_qrcode_assigned_user_qrcode_service_type_and_more'),
    ]
    operations = [
        migrations.RunPython(migrate_userbonus_forward, migrate_userbonus_backward),
    ]
