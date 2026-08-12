"""Celery Beat setup_periodic_tasks testlari."""

from django.core.management import call_command
from django.test import TestCase


class SetupPeriodicTasksTests(TestCase):
    REQUIRED_TASKS = {
        'notifications.process_scheduled',
        'notifications.send_booking_reminders',
        'payments.check_bookhara_deposit',
        'payments.process_pending_refunds',
        'crm.calculate_staff_performance',
        'qr_codes.calculate_daily_analytics',
    }

    def test_setup_registers_payment_and_crm_tasks(self):
        call_command('setup_periodic_tasks')
        from django_celery_beat.models import PeriodicTask

        registered = set(PeriodicTask.objects.values_list('task', flat=True))
        for task_name in self.REQUIRED_TASKS:
            self.assertIn(task_name, registered)

    def test_setup_is_idempotent(self):
        call_command('setup_periodic_tasks')
        from django_celery_beat.models import PeriodicTask

        count_after_first = PeriodicTask.objects.count()
        call_command('setup_periodic_tasks')
        self.assertEqual(PeriodicTask.objects.count(), count_after_first)

    def test_payment_tasks_enabled(self):
        call_command('setup_periodic_tasks')
        from django_celery_beat.models import PeriodicTask

        deposit = PeriodicTask.objects.get(task='payments.check_bookhara_deposit')
        refunds = PeriodicTask.objects.get(task='payments.process_pending_refunds')
        self.assertTrue(deposit.enabled)
        self.assertTrue(refunds.enabled)
        self.assertIsNotNone(deposit.interval)
        self.assertIsNotNone(refunds.interval)
