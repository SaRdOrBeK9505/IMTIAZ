"""
Management command: Celery Beat periodic tasks ni DB'ga yozadi.

Ishlatish:
    python manage.py setup_periodic_tasks

Deploy script ichida migrate dan keyin chaqiriladi:
    python manage.py migrate
    python manage.py setup_periodic_tasks
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Celery Beat periodic tasks ni ro'yxatga oladi"

    def handle(self, *args, **options):
        from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule

        created_count = 0

        # ── Har daqiqa: pending notifications ────────────────────────────────
        interval_1m, _ = IntervalSchedule.objects.get_or_create(
            every=1, period=IntervalSchedule.MINUTES
        )
        _, created = PeriodicTask.objects.update_or_create(
            name='Pending bildirishnomalarni yuborish',
            defaults={
                'task':     'notifications.process_scheduled',
                'interval': interval_1m,
                'enabled':  True,
            },
        )
        if created:
            created_count += 1
            self.stdout.write(self.style.SUCCESS('  [+] process_scheduled — har daqiqa'))

        # ── Har soat: bron eslatmalari ────────────────────────────────────────
        interval_1h, _ = IntervalSchedule.objects.get_or_create(
            every=1, period=IntervalSchedule.HOURS
        )
        _, created = PeriodicTask.objects.update_or_create(
            name="Bron eslatmalarini yuborish",
            defaults={
                'task':     'notifications.send_booking_reminders',
                'interval': interval_1h,
                'enabled':  True,
            },
        )
        if created:
            created_count += 1
            self.stdout.write(self.style.SUCCESS('  [+] send_booking_reminders — har soat'))

        # ── Har kunda 09:00: obuna qayta to'lov ──────────────────────────────
        cron_daily, _ = CrontabSchedule.objects.get_or_create(
            minute='0', hour='9',
            day_of_week='*', day_of_month='*', month_of_year='*',
        )
        _, created = PeriodicTask.objects.update_or_create(
            name="Obuna to'lovlarini qayta urinish",
            defaults={
                'task':    'notifications.retry_subscriptions',
                'crontab': cron_daily,
                'enabled': True,
            },
        )
        if created:
            created_count += 1
            self.stdout.write(self.style.SUCCESS("  [+] retry_subscriptions — har kunda 09:00"))

        # ── Har dushanba 03:00: eski bildirishnomalar ─────────────────────────
        cron_weekly, _ = CrontabSchedule.objects.get_or_create(
            minute='0', hour='3',
            day_of_week='1', day_of_month='*', month_of_year='*',
        )
        _, created = PeriodicTask.objects.update_or_create(
            name='Eski bildirishnomalarni tozalash',
            defaults={
                'task':    'notifications.cleanup_old',
                'crontab': cron_weekly,
                'enabled': True,
            },
        )
        if created:
            created_count += 1
            self.stdout.write(self.style.SUCCESS('  [+] cleanup_old — har dushanba 03:00'))

        # ── Har kunda 01:00: QR analitika ─────────────────────────────────────
        cron_0100, _ = CrontabSchedule.objects.get_or_create(
            minute='0', hour='1',
            day_of_week='*', day_of_month='*', month_of_year='*',
        )
        _, created = PeriodicTask.objects.update_or_create(
            name='QR kodlar kunlik analitikasi',
            defaults={
                'task':    'qr_codes.calculate_daily_analytics',
                'crontab': cron_0100,
                'enabled': True,
            },
        )
        if created:
            created_count += 1
            self.stdout.write(self.style.SUCCESS('  [+] qr_codes.calculate_daily_analytics — har kunda 01:00'))

        # ── Har soat: muddati o'tgan QR kodlar ────────────────────────────────
        _, created = PeriodicTask.objects.update_or_create(
            name='Muddati o\'tgan QR kodlarni o\'chirish',
            defaults={
                'task':     'qr_codes.expire_codes',
                'interval': interval_1h,
                'enabled':  True,
            },
        )
        if created:
            created_count += 1
            self.stdout.write(self.style.SUCCESS('  [+] qr_codes.expire_codes — har soat'))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nJami {PeriodicTask.objects.count()} ta periodic task mavjud "
                f"({created_count} ta yangi qo'shildi)."
            )
        )
