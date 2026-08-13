"""
CRM — Celery tasks.
    calculate_staff_performance — kunlik 00:00
    send_tour_lead_to_crm      — AI lead yaratilgach hamkor webhook'iga yuborish
"""

import hashlib
import hmac
import json
import logging

import httpx
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


@shared_task(name='crm.send_tour_lead_to_crm', bind=True, max_retries=3, default_retry_delay=60)
def send_tour_lead_to_crm(self, lead_id: str):
    """TourLead ni hamkor tashkilotning crm_webhook_url'iga POST qiladi."""
    from django.utils import timezone

    from apps.crm.models import TourLead, TourLeadStatus

    try:
        lead = TourLead.objects.select_related('organization', 'package').get(id=lead_id)
    except TourLead.DoesNotExist:
        logger.error('[crm] TourLead topilmadi: id=%s', lead_id)
        return {'status': 'not_found'}

    org = lead.organization

    if not org.crm_webhook_url:
        logger.info(
            '[crm] Organization %s crm_webhook_url sozlanmagan — lead ichki holda qoladi',
            org.id,
        )
        lead.status = TourLeadStatus.NEW
        lead.save(update_fields=['status', 'updated_at'])
        return {'status': 'no_webhook_configured'}

    payload = {
        'source': 'imtiaz_ai_assistant',
        'lead_id': str(lead.id),
        'full_name': lead.full_name,
        'phone': lead.phone,
        'tour_package': lead.package.title if lead.package else None,
        'tour_package_id': str(lead.package_id) if lead.package_id else None,
        'preferred_departure_date': (
            lead.preferred_departure_date.isoformat() if lead.preferred_departure_date else None
        ),
        'passengers': lead.passengers,
        'note': lead.note,
        'created_at': lead.created_at.isoformat(),
    }

    headers = {'Content-Type': 'application/json'}
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if org.crm_webhook_secret:
        signature = hmac.new(
            org.crm_webhook_secret.encode('utf-8'), body, hashlib.sha256,
        ).hexdigest()
        headers['X-Signature'] = signature

    try:
        resp = httpx.post(org.crm_webhook_url, content=body, headers=headers, timeout=10.0)
        resp.raise_for_status()

        lead.status = TourLeadStatus.SENT
        lead.sent_at = timezone.now()
        try:
            lead.crm_response = resp.json()
        except ValueError:
            lead.crm_response = {'raw': resp.text[:500]}
        lead.save(update_fields=['status', 'sent_at', 'crm_response', 'updated_at'])
        logger.info('[crm] Tour lead %s hamkor CRM ga yuborildi: org=%s', lead.id, org.id)
        return {'status': 'sent'}

    except Exception as exc:
        lead.retry_count += 1
        lead.crm_response = {'error': str(exc)}
        if self.request.retries >= self.max_retries:
            lead.status = TourLeadStatus.FAILED
        lead.save(update_fields=['status', 'retry_count', 'crm_response', 'updated_at'])
        logger.warning(
            '[crm] Tour lead %s yuborishda xato (urinish %s): %s',
            lead.id, lead.retry_count, exc,
        )
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
