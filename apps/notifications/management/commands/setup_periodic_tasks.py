"""
Management command: Celery Beat periodic tasks ni DB'ga yozadi.

Ishlatish:
    python manage.py setup_periodic_tasks

Deploy:
    python manage.py migrate
    python manage.py setup_periodic_tasks
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Celery Beat periodic tasks ni ro'yxatga oladi (idempotent)"

    def handle(self, *args, **options):
        from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask

        created_count = 0
        schedules = self._schedules(IntervalSchedule, CrontabSchedule)

        tasks = [
            # ── Bildirishnomalar ─────────────────────────────────────────────
            {
                'name': 'Pending bildirishnomalarni yuborish',
                'task': 'notifications.process_scheduled',
                'schedule': schedules['every_1m'],
                'label': 'process_scheduled — har daqiqa',
            },
            {
                'name': 'Bron eslatmalarini yuborish',
                'task': 'notifications.send_booking_reminders',
                'schedule': schedules['every_1h'],
                'schedule_kind': 'interval',
                'label': 'send_booking_reminders — har soat',
            },
            {
                'name': "Obuna to'lovlarini qayta urinish",
                'task': 'notifications.retry_subscriptions',
                'schedule': schedules['daily_09'],
                'schedule_kind': 'crontab',
                'label': "retry_subscriptions — har kunda 09:00",
            },
            {
                'name': 'Eski bildirishnomalarni tozalash',
                'task': 'notifications.cleanup_old',
                'schedule': schedules['weekly_mon_03'],
                'schedule_kind': 'crontab',
                'label': 'cleanup_old — har dushanba 03:00',
            },
            # ── QR kodlar ────────────────────────────────────────────────────
            {
                'name': 'QR kodlar kunlik analitikasi',
                'task': 'qr_codes.calculate_daily_analytics',
                'schedule': schedules['daily_01'],
                'schedule_kind': 'crontab',
                'label': 'qr_codes.calculate_daily_analytics — har kunda 01:00',
            },
            {
                'name': "Muddati o'tgan QR kodlarni o'chirish",
                'task': 'qr_codes.expire_codes',
                'schedule': schedules['every_1h'],
                'schedule_kind': 'interval',
                'label': 'qr_codes.expire_codes — har soat',
            },
            # ── To'lovlar (Bookhara saga) ────────────────────────────────────
            {
                'name': 'Bookhara depozit balansini tekshirish',
                'task': 'payments.check_bookhara_deposit',
                'schedule': schedules['every_15m'],
                'schedule_kind': 'interval',
                'label': 'check_bookhara_deposit — har 15 daqiqa',
            },
            {
                'name': 'Kutilayotgan refundlarni qayta ishlash',
                'task': 'payments.process_pending_refunds',
                'schedule': schedules['every_5m'],
                'schedule_kind': 'interval',
                'label': 'process_pending_refunds — har 5 daqiqa',
            },
            # ── CRM ──────────────────────────────────────────────────────────
            {
                'name': 'Xodimlar statistikasini hisoblash',
                'task': 'crm.calculate_staff_performance',
                'schedule': schedules['daily_00_05'],
                'schedule_kind': 'crontab',
                'label': 'calculate_staff_performance — har kunda 00:05',
            },
        ]

        for spec in tasks:
            schedule_kind = spec.get('schedule_kind', 'interval')
            defaults = {'task': spec['task'], 'enabled': True}
            if schedule_kind == 'crontab':
                defaults['crontab'] = spec['schedule']
                defaults['interval'] = None
            else:
                defaults['interval'] = spec['schedule']
                defaults['crontab'] = None

            _, created = PeriodicTask.objects.update_or_create(
                name=spec['name'],
                defaults=defaults,
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  [+] {spec["label"]}'))
            else:
                self.stdout.write(f'  [=] {spec["label"]}')

        total = PeriodicTask.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f'\nJami {total} ta periodic task mavjud ({created_count} ta yangi qo\'shildi).'
            )
        )

    @staticmethod
    def _schedules(interval_model, crontab_model):
        every_1m, _ = interval_model.objects.get_or_create(
            every=1, period=interval_model.MINUTES,
        )
        every_5m, _ = interval_model.objects.get_or_create(
            every=5, period=interval_model.MINUTES,
        )
        every_15m, _ = interval_model.objects.get_or_create(
            every=15, period=interval_model.MINUTES,
        )
        every_1h, _ = interval_model.objects.get_or_create(
            every=1, period=interval_model.HOURS,
        )
        daily_09, _ = crontab_model.objects.get_or_create(
            minute='0', hour='9',
            day_of_week='*', day_of_month='*', month_of_year='*',
        )
        daily_01, _ = crontab_model.objects.get_or_create(
            minute='0', hour='1',
            day_of_week='*', day_of_month='*', month_of_year='*',
        )
        daily_00_05, _ = crontab_model.objects.get_or_create(
            minute='5', hour='0',
            day_of_week='*', day_of_month='*', month_of_year='*',
        )
        weekly_mon_03, _ = crontab_model.objects.get_or_create(
            minute='0', hour='3',
            day_of_week='1', day_of_month='*', month_of_year='*',
        )
        return {
            'every_1m': every_1m,
            'every_5m': every_5m,
            'every_15m': every_15m,
            'every_1h': every_1h,
            'daily_09': daily_09,
            'daily_01': daily_01,
            'daily_00_05': daily_00_05,
            'weekly_mon_03': weekly_mon_03,
        }
