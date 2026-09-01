"""
Management command to expire old pending restaurant booking leads.

Usage:
    python manage.py expire_old_leads

This command will mark all pending leads older than LEAD_EXPIRY_HOURS (default: 24 hours)
as expired to prevent CRM clutter.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Expire old pending restaurant booking leads'

    def handle(self, *args, **options):
        from apps.crm_restaurant.models import RestaurantBookingLead
        
        self.stdout.write('Starting lead expiry task...')
        
        try:
            expired_count = RestaurantBookingLead.expire_old_leads()
            
            if expired_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully expired {expired_count} old pending leads.'
                    )
                )
                logger.info(f'Expired {expired_count} old restaurant booking leads')
            else:
                self.stdout.write('No old pending leads found to expire.')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error expiring leads: {str(e)}')
            )
            logger.exception('Error expiring old restaurant booking leads')
            raise
