"""
Management command to trigger daily AI lead statistics summary notification to Telegram group.

Usage:
    python manage.py send_daily_lead_stats
"""

from django.core.management.base import BaseCommand
from apps.crm.tasks import daily_ai_lead_stats_summary


class Command(BaseCommand):
    help = "Kunlik AI lead va analitika hisobotini Telegram guruhga yuboradi."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Kunlik AI statistika hisoboti yuborilmoqda..."))
        res = daily_ai_lead_stats_summary()
        self.stdout.write(self.style.SUCCESS(f"Natija: {res}"))
