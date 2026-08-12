"""crm_core — StaffActionLog proxy model."""

from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('crm', '0003_organization_business_type_and_owner'),
    ]

    operations = [
        migrations.CreateModel(
            name='StaffActionLog',
            fields=[],
            options={
                'verbose_name': 'Xodim amali (audit)',
                'verbose_name_plural': 'Xodim amallari (audit)',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('crm.staffactivitylog',),
        ),
    ]
