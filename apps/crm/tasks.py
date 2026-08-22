"""
CRM — Celery tasks.
    calculate_staff_performance    — kunlik 00:00
    send_tour_lead_to_crm          — AI lead yaratilgach hamkor webhook'iga yuborish
    notify_telegram_tour_lead      — yangi lead haqida Telegram guruhga xabar yuborish
"""

import hashlib
import hmac
import json
import logging

import httpx
from celery import shared_task
from django.conf import settings

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
        # Webhook bo'lmasa ham Telegram guruhga xabar yuboriladi
        notify_telegram_tour_lead.delay(str(lead.id))
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

        # Telegram guruhga ham xabar yuborish
        notify_telegram_tour_lead.delay(str(lead.id))

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


# ─── Telegram Lead Notification Helpers ─────────────────────────────────────

def build_lead_keyboard(lead_type: str, lead_id: str, phone: str, current_status: str) -> dict:
    """Lead uchun Telegram inline klaviaturasi (Telefon dialer + Status menyusi)."""
    clean_phone = (phone or '').strip()
    if clean_phone and not clean_phone.startswith('+') and clean_phone.isdigit():
        clean_phone = '+' + clean_phone

    status_labels = {
        'new': '🆕 Yangi',
        'sent': '🆕 Yangi',
        'contacted': '⏳ Jarayonda',
        'in_progress': '⏳ Jarayonda',
        'converted': '✅ Bajarildi',
        'confirmed': '✅ Bajarildi',
        'declined': '❌ Rad etildi',
        'failed': '⚠️ Xato',
    }
    st_text = status_labels.get(current_status, '🆕 Yangi')

    call_btn_text = "📞 Mijoz bilan bog'lanish"
    if lead_type == 'roadside':
        call_btn_text = "🤝 Yordamni qabul qilish"
    elif lead_type == 'flight':
        call_btn_text = "💬 Mijozga murojaat qilish"

    return {
        'inline_keyboard': [
            [
                {'text': call_btn_text, 'url': f'tel:{clean_phone}'}
            ],
            [
                {'text': f'⚙️ Status: {st_text}', 'callback_data': f'st_menu:{lead_type}:{lead_id}'}
            ]
        ]
    }


def build_lead_status_selection_keyboard(lead_type: str, lead_id: str) -> dict:
    """Statusni o'zgartirish sub-menyusi klaviaturasi."""
    return {
        'inline_keyboard': [
            [
                {'text': '🆕 Yangi', 'callback_data': f'st_set:{lead_type}:{lead_id}:new'},
                {'text': '⏳ Jarayonda', 'callback_data': f'st_set:{lead_type}:{lead_id}:contacted'},
            ],
            [
                {'text': '✅ Bajarildi', 'callback_data': f'st_set:{lead_type}:{lead_id}:converted'},
                {'text': '❌ Rad etildi', 'callback_data': f'st_set:{lead_type}:{lead_id}:declined'},
            ],
            [
                {'text': '⬅️ Orqaga', 'callback_data': f'st_back:{lead_type}:{lead_id}'}
            ]
        ]
    }


def format_tour_lead_card(lead) -> tuple[str, dict]:
    """TourLead uchun Telegram karta matni va klaviaturasi."""
    departure = (
        lead.preferred_departure_date.strftime('%d.%m.%Y')
        if lead.preferred_departure_date else '—'
    )
    package_info = lead.package.title if lead.package else '—'
    destination_info = '—'
    if lead.package and lead.package.destination:
        dest = lead.package.destination
        destination_info = f'{dest.name} ({dest.country})'

    user_info = '—'
    if lead.user:
        user_info = f'{lead.user.full_name or getattr(lead.user, "phone", "") or str(lead.user)}'

    note_section = f'\n💬 <b>Izoh:</b> {lead.note}' if lead.note else ''
    created_str  = lead.created_at.strftime('%d.%m.%Y %H:%M') if lead.created_at else '—'
    lead_short   = str(lead.id)[:8].upper()

    status_labels = {
        'new': '🆕 Yangi',
        'sent': '🆕 Yangi',
        'contacted': '⏳ Jarayonda',
        'converted': '✅ Bajarildi',
        'declined': '❌ Rad etildi',
    }
    st_display = status_labels.get(lead.status, '🆕 Yangi')

    staff_sec = f"\n👤 <b>Mas'ul xodim:</b> @{lead.assigned_staff_name}" if lead.assigned_staff_name else ''

    text = (
        "🔔 <b>YANGI TUR SO'ROVI KELDI!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Ism:</b>          {lead.full_name or '—'}\n"
        f"📞 <b>Telefon:</b>     <code>{lead.phone}</code>\n"
        f"🌍 <b>Tur paketi:</b>  {package_info}\n"
        f"📍 <b>Yo'nalish:</b>   {destination_info}\n"
        f"📅 <b>Jo'nash:</b>     {departure}\n"
        f"👥 <b>Yo'lovchilar:</b> {lead.passengers} kishi\n"
        f"🏢 <b>Kompaniya:</b>   {lead.organization.name if lead.organization else '—'}"
        f"{note_section}\n\n"
        "──────────────────────────\n"
        f"🕐 <b>Vaqt:</b> {created_str}\n"
        f"👤 <b>Foydalanuvchi:</b> {user_info}\n"
        f"🆔 <b>Lead ID:</b> <code>{lead_short}</code>\n"
        f"📊 <b>Status:</b> {st_display}"
        f"{staff_sec}\n\n"
        "<i>IMTIAZ — AI Travel Assistant</i>"
    )

    markup = build_lead_keyboard('tour', str(lead.id), lead.phone, lead.status)
    return text, markup


def format_restaurant_lead_card(lead) -> tuple[str, dict]:
    """RestaurantLead uchun Telegram karta matni va klaviaturasi."""
    pref_date = lead.preferred_date.strftime('%d.%m.%Y') if lead.preferred_date else '—'
    pref_time = lead.preferred_time.strftime('%H:%M') if lead.preferred_time else '—'
    org_name  = lead.organization.name if lead.organization else '—'
    branch_name = lead.branch.name if lead.branch else 'Asosiy filial'
    created_str = lead.created_at.strftime('%d.%m.%Y %H:%M') if lead.created_at else '—'
    lead_short = str(lead.id)[:8].upper()

    note_sec = f"\n💬 <b>Izoh / So'rov:</b> {lead.note}" if lead.note else ''

    status_labels = {
        'new': '🆕 Yangi',
        'sent': '🆕 Yangi',
        'contacted': '⏳ Jarayonda',
        'confirmed': '✅ Bajarildi',
        'declined': '❌ Rad etildi',
    }
    st_display = status_labels.get(lead.status, '🆕 Yangi')

    staff_sec = f"\n👤 <b>Mas'ul xodim:</b> @{lead.assigned_staff_name}" if lead.assigned_staff_name else ''

    text = (
        "🍴 <b>YANGI RESTORAN STOL BRONI!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Ism:</b>          {lead.full_name or '—'}\n"
        f"📞 <b>Telefon:</b>     <code>{lead.phone}</code>\n"
        f"🏛️ <b>Restoran:</b>    {org_name} ({branch_name})\n"
        f"📅 <b>Sana va Vaqt:</b> {pref_date} soat {pref_time}\n"
        f"👥 <b>Mehmonlar:</b>   {lead.guests} kishi"
        f"{note_sec}\n\n"
        "──────────────────────────\n"
        f"🕐 <b>Vaqt:</b> {created_str}\n"
        f"🆔 <b>Lead ID:</b> <code>{lead_short}</code>\n"
        f"📊 <b>Status:</b> {st_display}"
        f"{staff_sec}\n\n"
        "<i>IMTIAZ — Restoran Konsyerj</i>"
    )

    markup = build_lead_keyboard('restaurant', str(lead.id), lead.phone, lead.status)
    return text, markup


def format_service_lead_card(lead) -> tuple[str, dict]:
    """ServiceLead (Parvoz, Yo'lda yordam, Umumiy/Boshqa va b.) uchun Telegram karta matni va klaviaturasi."""
    from apps.crm.models import ServiceLeadCategory

    category_config = {
        ServiceLeadCategory.FLIGHT: ("✈️ <b>YANGI PARVOZ BILETI SO'ROVI!</b>", "flight"),
        ServiceLeadCategory.ROADSIDE: ("🚨 <b>YANGI YO'LDA YORDAM SO'ROVI! [URGENT]</b>", "roadside"),
        ServiceLeadCategory.MEDICAL: ("🩺 <b>YANGI TIBBIYOT KONSYERJ SO'ROVI!</b>", "service"),
        ServiceLeadCategory.INSURANCE: ("🛡️ <b>YANGI SUG'URTA SO'ROVI!</b>", "service"),
        ServiceLeadCategory.FAMILY_OFFICE: ("💼 <b>YANGI FAMILY OFFICE SO'ROVI!</b>", "service"),
        ServiceLeadCategory.LEISURE: ("🎭 <b>YANGI DAM OLISH SO'ROVI!</b>", "service"),
        ServiceLeadCategory.RESTAURANT: ("🍴 <b>YANGI RESTORAN SO'ROVI!</b>", "service"),
        ServiceLeadCategory.TRAVEL: ("🌍 <b>YANGI SAYOHAT SO'ROVI!</b>", "service"),
        ServiceLeadCategory.OTHER: ("🌟 <b>YANGI UMUMIY XIZMAT SO'ROVI! (Boshqa / Maxsus)</b>", "service"),
    }
    header, lead_ktype = category_config.get(
        lead.category,
        ("🌟 <b>YANGI UMUMIY XIZMAT SO'ROVI! (Boshqa / Maxsus)</b>", "service")
    )

    created_str = lead.created_at.strftime('%d.%m.%Y %H:%M') if lead.created_at else '—'
    lead_short = str(lead.id)[:8].upper()

    analysis_sec = f"\n🧠 <b>AI Mijoz Tahlili:</b>\n<i>{lead.customer_analysis}</i>\n" if lead.customer_analysis else ''
    note_sec = f"\n💬 <b>So'rov Tafsilotlari:</b>\n{lead.note}" if lead.note else ''

    status_labels = {
        'new': '🆕 Yangi',
        'sent': '🆕 Yangi',
        'contacted': '⏳ Jarayonda',
        'converted': '✅ Bajarildi',
        'declined': '❌ Rad etildi',
    }
    st_display = status_labels.get(lead.status, '🆕 Yangi')

    staff_sec = f"\n👤 <b>Mas'ul xodim:</b> @{lead.assigned_staff_name}" if lead.assigned_staff_name else ''

    text = (
        f"{header}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏷️ <b>Xizmat Turi:</b> {lead.get_category_display()}\n"
        f"📌 <b>Nomi:</b>        {lead.service_name or '—'}\n"
        f"👤 <b>Ism:</b>        {lead.full_name or '—'}\n"
        f"📞 <b>Telefon:</b>     <code>{lead.phone}</code>"
        f"{analysis_sec}"
        f"{note_sec}\n\n"
        "──────────────────────────\n"
        f"🕐 <b>Vaqt:</b> {created_str}\n"
        f"🆔 <b>Lead ID:</b> <code>{lead_short}</code>\n"
        f"📊 <b>Status:</b> {st_display}"
        f"{staff_sec}\n\n"
        "<i>IMTIAZ — AI Lifestyle Concierge</i>"
    )

    markup = build_lead_keyboard(lead_ktype, str(lead.id), lead.phone, lead.status)
    return text, markup


# ─── Telegram Lead Notification ───────────────────────────────────────────────

def send_telegram_tour_lead_notification(lead_id: str) -> dict:
    """Yangi TourLead haqida Telegram guruhga to'liq ma'lumot yuboradi (sinxron helper)."""
    from apps.crm.models import TourLead
    from apps.notifications.telegram import get_bot

    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    raw_chat_id = getattr(settings, 'TELEGRAM_TOUR_LEADS_CHAT_ID', None)

    if not bot_token:
        logger.warning('[crm.telegram] TELEGRAM_BOT_TOKEN sozlanmagan — xabar yuborilmadi')
        return {'status': 'no_token'}

    if not raw_chat_id:
        logger.warning('[crm.telegram] TELEGRAM_TOUR_LEADS_CHAT_ID sozlanmagan — xabar yuborilmadi')
        return {'status': 'no_chat_id'}

    # Inline izohlarni (#...) va bo'sh joylarni tozalash
    chat_str = str(raw_chat_id).split('#')[0].strip()
    if not chat_str:
        logger.warning('[crm.telegram] TELEGRAM_TOUR_LEADS_CHAT_ID bo\'sh — xabar yuborilmadi')
        return {'status': 'no_chat_id'}

    try:
        chat_id = int(chat_str)
    except (ValueError, TypeError):
        logger.error('[crm.telegram] TELEGRAM_TOUR_LEADS_CHAT_ID noto\'g\'ri format: %r', raw_chat_id)
        return {'status': 'invalid_chat_id'}

    try:
        lead = TourLead.objects.select_related(
            'organization', 'package', 'package__destination', 'user',
        ).get(id=lead_id)
    except TourLead.DoesNotExist:
        logger.error('[crm.telegram] TourLead topilmadi: id=%s', lead_id)
        return {'status': 'not_found'}

    text, reply_markup = format_tour_lead_card(lead)

    # ── Yuborish ──────────────────────────────────────────────────────────────
    try:
        bot = get_bot()
        msg_id = bot.send_message(chat_id=int(chat_id), text=text, parse_mode='HTML', reply_markup=reply_markup)

        if msg_id:
            logger.info(
                '[crm.telegram] Tour lead %s Telegram guruhga yuborildi: chat_id=%s, msg_id=%s',
                lead_id, chat_id, msg_id,
            )
            return {'status': 'sent', 'message_id': msg_id}
        else:
            logger.warning('[crm.telegram] Telegram xabar yuborilmadi (bot None qaytardi): lead=%s', lead_id)
            return {'status': 'failed'}

    except Exception as exc:
        logger.error('[crm.telegram] Telegram xabarda xato: lead=%s, exc=%s', lead_id, exc)
        return {'status': 'error', 'error': str(exc)}


@shared_task(name='crm.notify_telegram_tour_lead', bind=True, max_retries=2, default_retry_delay=30)
def notify_telegram_tour_lead(self, lead_id: str):
    """Yangi TourLead haqida Telegram guruhga Celery task orqali yuboradi."""
    res = send_telegram_tour_lead_notification(lead_id)
    if res.get('status') == 'error':
        countdown = 30 * (2 ** self.request.retries)
        raise self.retry(exc=Exception(res.get('error')), countdown=countdown)
    return res


# ── Restoran Lead Notification ───────────────────────────────────────────────

def send_telegram_restaurant_lead_notification(lead_id: str) -> dict:
    """Yangi RestaurantLead haqida Telegram guruhga xabar yuboradi."""
    from apps.crm.models import RestaurantLead
    from apps.notifications.telegram import get_bot

    raw_chat_id = getattr(settings, 'TELEGRAM_TOUR_LEADS_CHAT_ID', None)
    if not raw_chat_id:
        return {'status': 'no_chat_id'}

    try:
        chat_id = int(str(raw_chat_id).split('#')[0].strip())
    except (ValueError, TypeError):
        return {'status': 'invalid_chat_id'}

    try:
        lead = RestaurantLead.objects.select_related('organization', 'branch', 'user').get(id=lead_id)
    except RestaurantLead.DoesNotExist:
        return {'status': 'not_found'}

    text, reply_markup = format_restaurant_lead_card(lead)

    try:
        bot = get_bot()
        msg_id = bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML', reply_markup=reply_markup)
        if msg_id:
            lead.status = 'sent'
            lead.save(update_fields=['status', 'updated_at'])
            return {'status': 'sent', 'message_id': msg_id}
        return {'status': 'failed'}
    except Exception as exc:
        logger.error('[crm.telegram] Restaurant lead error: %s', exc)
        return {'status': 'error', 'error': str(exc)}


@shared_task(name='crm.notify_telegram_restaurant_lead', bind=True, max_retries=2, default_retry_delay=30)
def notify_telegram_restaurant_lead(self, lead_id: str):
    return send_telegram_restaurant_lead_notification(lead_id)


# ── Universal Service & Flight Lead Notification ─────────────────────────────

def send_telegram_service_lead_notification(lead_id: str) -> dict:
    """Yangi ServiceLead (Parvoz, Yo'lda yordam, Tibbiyot, Sug'urta, Family Office va b.) haqida Telegram guruhga xabar yuboradi."""
    from apps.crm.models import ServiceLead
    from apps.notifications.telegram import get_bot

    raw_chat_id = getattr(settings, 'TELEGRAM_TOUR_LEADS_CHAT_ID', None)
    if not raw_chat_id:
        return {'status': 'no_chat_id'}

    try:
        chat_id = int(str(raw_chat_id).split('#')[0].strip())
    except (ValueError, TypeError):
        return {'status': 'invalid_chat_id'}

    try:
        lead = ServiceLead.objects.select_related('organization', 'user').get(id=lead_id)
    except ServiceLead.DoesNotExist:
        return {'status': 'not_found'}

    text, reply_markup = format_service_lead_card(lead)

    try:
        bot = get_bot()
        msg_id = bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML', reply_markup=reply_markup)
        if msg_id:
            lead.status = 'sent'
            lead.save(update_fields=['status', 'updated_at'])
            return {'status': 'sent', 'message_id': msg_id}
        return {'status': 'failed'}
    except Exception as exc:
        logger.error('[crm.telegram] Service lead notification error: %s', exc)
        return {'status': 'error', 'error': str(exc)}


@shared_task(name='crm.notify_telegram_service_lead', bind=True, max_retries=2, default_retry_delay=30)
def notify_telegram_service_lead(self, lead_id: str):
    return send_telegram_service_lead_notification(lead_id)


# ── Kunlik AI Analitika va Statistik Xabarnoma ────────────────────────────────

@shared_task(name='crm.daily_ai_lead_stats_summary', bind=True, max_retries=2)
def daily_ai_lead_stats_summary(self):
    """
    So'nggi 24 soat ichida kelgan barcha leadlarni tahlil qilib,
    guruhga AI statistika va analitika hisobotini yuboradi.
    """
    from datetime import timedelta
    from django.utils import timezone
    from apps.crm.models import TourLead, RestaurantLead, ServiceLead, ServiceLeadCategory
    from apps.notifications.telegram import get_bot

    raw_chat_id = getattr(settings, 'TELEGRAM_TOUR_LEADS_CHAT_ID', None)
    if not raw_chat_id:
        logger.warning('[daily_stats] TELEGRAM_TOUR_LEADS_CHAT_ID sozlanmagan')
        return {'status': 'no_chat_id'}

    try:
        chat_id = int(str(raw_chat_id).split('#')[0].strip())
    except (ValueError, TypeError):
        return {'status': 'invalid_chat_id'}

    now = timezone.now()
    since = now - timedelta(days=1)

    tour_leads = TourLead.objects.filter(created_at__gte=since)
    rest_leads = RestaurantLead.objects.filter(created_at__gte=since)
    serv_leads = ServiceLead.objects.filter(created_at__gte=since)

    total_leads_count = tour_leads.count() + rest_leads.count() + serv_leads.count()

    cat_counts = {
        'travel': tour_leads.count() + serv_leads.filter(category=ServiceLeadCategory.TRAVEL).count(),
        'restaurant': rest_leads.count() + serv_leads.filter(category=ServiceLeadCategory.RESTAURANT).count(),
        'flight': serv_leads.filter(category=ServiceLeadCategory.FLIGHT).count(),
        'roadside': serv_leads.filter(category=ServiceLeadCategory.ROADSIDE).count(),
        'medical': serv_leads.filter(category=ServiceLeadCategory.MEDICAL).count(),
        'insurance': serv_leads.filter(category=ServiceLeadCategory.INSURANCE).count(),
        'family_office': serv_leads.filter(category=ServiceLeadCategory.FAMILY_OFFICE).count(),
        'leisure': serv_leads.filter(category=ServiceLeadCategory.LEISURE).count(),
        'other': serv_leads.filter(category=ServiceLeadCategory.OTHER).count(),
    }

    # Platdormalarda hali bo'lmagan, so'ralgan xizmatlarni aniqlash
    unhandled_services = list(serv_leads.filter(category=ServiceLeadCategory.OTHER).values_list('service_name', flat=True)[:5])
    unhandled_str = ", ".join(s for s in unhandled_services if s) if unhandled_services else "Barcha so'rovlar qamrab olindi"

    report_text = (
        "📊 <b>IMTIAZ AI — KUNLIK LEAD VA ANALITIKA STATISTIKASI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 <b>Sana:</b> {now.strftime('%d.%m.%Y')}\n"
        f"📈 <b>Oxirgi 24 soatdagi jami leadlar:</b> <b>{total_leads_count} ta</b>\n\n"
        "📂 <b>Yo'nalishlar bo'yicha taqsimot:</b>\n"
        f"  • 🌍 <b>Sayohatlar:</b> {cat_counts['travel']} ta\n"
        f"  • 🍴 <b>Stol band qilish:</b> {cat_counts['restaurant']} ta\n"
        f"  • ✈️ <b>Parvoz biletlari:</b> {cat_counts['flight']} ta\n"
        f"  • 🚗 <b>Yo'lda yordam:</b> {cat_counts['roadside']} ta\n"
        f"  • 🩺 <b>Tibbiyot:</b> {cat_counts['medical']} ta\n"
        f"  • 🛡️ <b>Sug'urta:</b> {cat_counts['insurance']} ta\n"
        f"  • 💼 <b>Family Office:</b> {cat_counts['family_office']} ta\n"
        f"  • 🎭 <b>Dam olish:</b> {cat_counts['leisure']} ta\n"
        f"  • 🌟 <b>Maxsus/Boshqa:</b> {cat_counts['other']} ta\n\n"
        "💡 <b>Tahlil va Tavsiyalar:</b>\n"
        f"  📌 <i>Qo'shish tavsiya etiladigan xizmatlar:</i> {unhandled_str}\n"
        "  🧠 <i>AI xulosasi:</i> Mijozlar faolligi barqaror. Premium concierge va sayohat so'rovlari yuqori ulushga ega.\n\n"
        "<i>IMTIAZ — AI Automated Analytics System</i>"
    )

    try:
        bot = get_bot()
        msg_id = bot.send_message(chat_id=chat_id, text=report_text, parse_mode='HTML')
        return {'status': 'sent', 'message_id': msg_id, 'total_leads': total_leads_count}
    except Exception as exc:
        logger.error('[daily_stats] Telegram report send error: %s', exc)
        return {'status': 'error', 'error': str(exc)}


