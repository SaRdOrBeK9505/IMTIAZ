"""
VPS migratsiya holatini tekshirish.

Ishlatish:
    python manage.py check_migration_drift
"""

from django.core.management.base import BaseCommand
from django.db import connection


# Model → kutilayotgan jadval nomi
REQUIRED_TABLES = {
    'users': [
        'users_user',
        'users_otpcode',
        'users_userdevice',
        'users_wallettransaction',
    ],
    'booking': [
        'booking_booking',
        'booking_tourbooking',
        'booking_restaurantbooking',
        'booking_flightpayment',
    ],
    'crm': [
        'crm_organization',
        'crm_branch',
        'crm_restauranttable',
        'crm_staffactivitylog',
    ],
    'tours': [
        'tours_tourpackage',
        'tours_touravailability',
    ],
    'qr_codes': [
        'qr_codes_qrcode',
        'qr_codes_qrcoderedemption',
    ],
    'payments': [
        'payments_payment',
    ],
}

REQUIRED_COLUMNS = {
    'users_user': ['email', 'role', 'is_phone_verified', 'phone'],
}


class Command(BaseCommand):
    help = "DB jadvallari va migratsiya holatini tekshiradi"

    def handle(self, *args, **options):
        from django.db.migrations.recorder import MigrationRecorder

        tables = set(connection.introspection.table_names())
        recorder = MigrationRecorder(connection)
        applied = {
            (m.app, m.name)
            for m in recorder.migration_qs.all()
        }

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Qo\'llangan migratsiyalar (users) ==='))
        for app, name in sorted(applied):
            if app == 'users':
                self.stdout.write(f'  [X] {app}.{name}')

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Yetishmayotgan jadvallar ==='))
        missing_any = False
        for app, table_list in REQUIRED_TABLES.items():
            for table in table_list:
                if table not in tables:
                    missing_any = True
                    self.stdout.write(self.style.ERROR(f'  [ ] {table}  (app: {app})'))

        if not missing_any:
            self.stdout.write(self.style.SUCCESS('  Barcha asosiy jadvallar mavjud'))

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Yetishmayotgan ustunlar ==='))
        missing_cols = False
        with connection.cursor() as cursor:
            for table, columns in REQUIRED_COLUMNS.items():
                if table not in tables:
                    continue
                desc = connection.introspection.get_table_description(cursor, table)
                existing = {col.name for col in desc}
                for col in columns:
                    if col not in existing:
                        missing_cols = True
                        self.stdout.write(self.style.ERROR(f'  [ ] {table}.{col}'))

        if not missing_cols:
            self.stdout.write(self.style.SUCCESS('  Barcha asosiy ustunlar mavjud'))

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Users migratsiya zanjir tekshiruvi ==='))
        required_users_migrations = [
            '0001_initial',
            '0002_sync_otpcode_userdevice_and_user_fields',
            '0003_user_email',
            '0004_merge_vps_and_sync',
        ]
        for name in required_users_migrations:
            if ('users', name) in applied:
                self.stdout.write(self.style.SUCCESS(f'  [X] users.{name}'))
            else:
                self.stdout.write(self.style.ERROR(f'  [ ] users.{name} — QO\'LLANMAGAN'))

        if missing_any or missing_cols:
            self.stdout.write(self.style.WARNING(
                '\nTavsiya: python manage.py migrate users\n'
                'Yoki: python manage.py check_migration_drift dan keyin migrate'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('\nMigratsiya holati yaxshi ko\'rinadi.'))
