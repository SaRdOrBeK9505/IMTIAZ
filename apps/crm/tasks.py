"""
CRM — Celery tasks.
    calculate_staff_performance — kunlik 00:00
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='crm.calculate_staff_performance', bind=True, max_retries=3)
def calculate_staff_performance(self):
    """
    Barcha xodimlar uchun bugungi/haftalik/oylik
    StaffPerformanceSummary ni hisoblaydi va saqlaydi.
    """
    try:
        from datetime import timedelta
        from django.utils import timezone
        from django.db.models import Count

        from apps.crm.models import BranchStaff, StaffActivityLog, StaffPerformanceSummary

        today = timezone.now().date()
        week_start  = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        staff_qs = BranchStaff.objects.filter(is_active=True)
        updated  = 0

        for staff in staff_qs:
            for period_type, p_start, p_end in [
                ('daily',   today,       today),
                ('weekly',  week_start,  today),
                ('monthly', month_start, today),
            ]:
                logs = StaffActivityLog.objects.filter(
                    staff=staff,
                    created_at__date__gte=p_start,
                    created_at__date__lte=p_end,
                )

                StaffPerformanceSummary.objects.update_or_create(
                    staff=staff,
                    period_type=period_type,
                    period_start=p_start,
                    defaults={
                        'period_end': p_end,
                        'tour_bookings_confirmed': logs.filter(
                            action_type=StaffActivityLog.ActionType.CONFIRM_TOUR_BOOKING
                        ).count(),
                        'tour_bookings_rejected': logs.filter(
                            action_type=StaffActivityLog.ActionType.REJECT_TOUR_BOOKING
                        ).count(),
                        'vouchers_generated': logs.filter(
                            action_type=StaffActivityLog.ActionType.GENERATE_VOUCHER
                        ).count(),
                        'table_bookings_confirmed': logs.filter(
                            action_type=StaffActivityLog.ActionType.CONFIRM_TABLE_BOOKING
                        ).count(),
                        'table_bookings_cancelled': logs.filter(
                            action_type=StaffActivityLog.ActionType.CANCEL_TABLE_BOOKING
                        ).count(),
                        'login_count': logs.filter(
                            action_type=StaffActivityLog.ActionType.LOGIN
                        ).count(),
                        'total_actions': logs.count(),
                    }
                )
                updated += 1

        logger.info('[crm] Staff performance calculated: %d records', updated)
        return {'updated': updated}

    except Exception as exc:
        logger.error('[crm] calculate_staff_performance xato: %s', exc)
        raise self.retry(exc=exc, countdown=300)
