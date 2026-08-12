"""Platform migratsiyalarini tekshirish va qo'llash."""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


CRITICAL_APPS = (
    'users',
    'crm',
    'crm_core',
    'booking',
    'payments',
    'notifications',
    'tours',
    'crm_restaurant',
    'crm_travel',
)


class Command(BaseCommand):
    help = 'Kritik migratsiyalar holati + ixtiyoriy qo\'llash (--apply)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Kutilayotgan migratsiyalarni qo\'llash (migrate --skip-checks)',
        )

    def handle(self, *args, **options):
        executor = MigrationExecutor(connection)
        pending = []

        for app_label in CRITICAL_APPS:
            targets = executor.loader.graph.leaf_nodes(app_label)
            plan = executor.migration_plan(targets)
            unapplied = [m for m, _ in plan if m not in executor.loader.applied_migrations]
            if unapplied:
                pending.append((app_label, [m.name for m in unapplied]))

        if not pending:
            self.stdout.write(self.style.SUCCESS('Barcha kritik migratsiyalar qo\'llangan.'))
            return

        self.stdout.write(self.style.WARNING('Kutilayotgan migratsiyalar:'))
        for app_label, names in pending:
            self.stdout.write(f'  {app_label}: {", ".join(names)}')

        if options['apply']:
            self.stdout.write('Migratsiyalar qo\'llanmoqda...')
            call_command('migrate', skip_checks=True, verbosity=1)
            self.stdout.write(self.style.SUCCESS('Tugadi.'))
