"""ServiceLead va Telegram notification/analytics testlari."""

from datetime import date
from unittest.mock import patch
from django.test import TestCase, override_settings

from apps.ai_assistant.tool_handlers import handle_submit_flight_lead, handle_submit_service_lead
from apps.crm.models import ServiceLead, ServiceLeadCategory, TourLead, RestaurantLead, Organization, BusinessType
from apps.crm.tasks import daily_ai_lead_stats_summary
from apps.users.models import User, UserRole


@override_settings(TELEGRAM_TOUR_LEADS_CHAT_ID='-100123456789')
class ServiceLeadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone='+998901112233',
            role=UserRole.CUSTOMER,
            first_name='Anvar',
            last_name='Karimov',
        )

    @patch('apps.notifications.telegram.TelegramBotClient.send_message')
    def test_submit_service_lead_roadside(self, mock_send):
        mock_send.return_value = 101
        res = handle_submit_service_lead(
            self.user,
            phone='998901112233',
            category='roadside',
            service_name="Evakuator va g'ildirak almashtirish",
            customer_analysis="Shoshilinch yo'lda yordamga muhtoj mijoz.",
            note="Toshkent-Samarqand yo'li 45-km",
            lang='uz',
        )
        self.assertEqual(res['status'], 'ok')
        lead = ServiceLead.objects.get()
        self.assertEqual(lead.category, ServiceLeadCategory.ROADSIDE)
        self.assertEqual(lead.phone, '+998901112233')
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        sent_text = kwargs.get('text') or (args[1] if len(args) > 1 else '')
        self.assertIn("YO'LDA YORDAM", sent_text)

    @patch('apps.notifications.telegram.TelegramBotClient.send_message')
    def test_submit_flight_lead(self, mock_send):
        mock_send.return_value = 102
        res = handle_submit_flight_lead(
            self.user,
            phone='998901112233',
            origin='Toshkent',
            destination='Dubay',
            departure_date='2026-10-01',
            passengers=2,
            seat_class='biznes',
            customer_analysis="Biznes klass reys qidirayotgan VIP mijoz.",
            lang='uz',
        )
        self.assertEqual(res['status'], 'ok')
        lead = ServiceLead.objects.get(category=ServiceLeadCategory.FLIGHT)
        self.assertEqual(lead.phone, '+998901112233')
        self.assertIn("Dubay", lead.service_name)
        mock_send.assert_called_once()

    @patch('apps.notifications.telegram.TelegramBotClient.send_message')
    def test_daily_ai_lead_stats_summary(self, mock_send):
        mock_send.return_value = 103
        ServiceLead.objects.create(
            category=ServiceLeadCategory.MEDICAL,
            phone='+998901112233',
            service_name='VIP Chekap',
        )
        res = daily_ai_lead_stats_summary()
        self.assertEqual(res['status'], 'sent')
        self.assertEqual(res['total_leads'], 1)
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        sent_text = kwargs.get('text') or (args[1] if len(args) > 1 else '')
        self.assertIn("KUNLIK LEAD VA ANALITIKA STATISTIKASI", sent_text)
