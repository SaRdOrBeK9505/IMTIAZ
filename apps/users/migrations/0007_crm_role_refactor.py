# CRM role refactor — owner_restaurant, restaurant_staff, owner_tour, tour_staff

from django.db import migrations, models


def migrate_roles_forward(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Organization = apps.get_model('crm', 'Organization')
    BranchStaff = apps.get_model('crm', 'BranchStaff')

    for user in User.objects.filter(role='owner'):
        try:
            org = Organization.objects.get(owner_id=user.id)
        except Organization.DoesNotExist:
            user.role = 'owner_restaurant'
            user.save(update_fields=['role'])
            continue
        if org.business_type == 'travel':
            user.role = 'owner_tour'
        else:
            user.role = 'owner_restaurant'
        user.save(update_fields=['role'])

    for profile in BranchStaff.objects.select_related('user', 'branch__organization'):
        org = profile.branch.organization
        if org.business_type == 'travel':
            profile.user.role = 'tour_staff'
        else:
            profile.user.role = 'restaurant_staff'
        profile.user.save(update_fields=['role'])


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0003_organization_business_type_and_owner'),
        ('users', '0006_otpcode_users_otpco_phone_159373_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('customer', 'Mijoz'),
                    ('owner_restaurant', 'Restoran egasi'),
                    ('restaurant_staff', 'Restoran xodimi'),
                    ('owner_tour', 'Tur kompaniyasi egasi'),
                    ('tour_staff', 'Tur kompaniyasi xodimi'),
                    ('admin', 'Admin'),
                    ('owner', 'Tashkilot egasi (eski)'),
                    ('branch_staff', 'Filial xodimi (eski)'),
                ],
                db_index=True,
                default='customer',
                max_length=32,
            ),
        ),
        migrations.RunPython(migrate_roles_forward, migrations.RunPython.noop),
    ]
