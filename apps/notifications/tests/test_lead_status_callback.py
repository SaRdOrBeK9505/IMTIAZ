"""
Tests for Telegram lead status inline keyboard buttons and callback handler.
"""

from unittest.mock import MagicMock, patch
from django.test import TestCase
from apps.crm.models import TourLead, RestaurantLead, ServiceLead, ServiceLeadCategory, Organization
from apps.crm.tasks import (
    build_lead_keyboard,
    build_lead_status_selection_keyboard,
    format_tour_lead_card,
    format_restaurant_lead_card,
    format_service_lead_card,
)
from apps.notifications.bot_handlers import _handle_lead_status_callback


class LeadKeyboardAndStatusCallbackTestCase(TestCase):

    def setUp(self):
        self.org = Organization.objects.create(name="Test Agency", org_type="tour_company")
        self.tour_lead = TourLead.objects.create(
            organization=self.org,
            full_name="Sardorbek",
            phone="+998907765431",
            passengers=3,
        )
        self.restaurant_lead = RestaurantLead.objects.create(
            organization=self.org,
            full_name="Sardorbek Rest",
            phone="+998907765432",
            guests=2,
        )
        self.service_lead = ServiceLead.objects.create(
            category=ServiceLeadCategory.FLIGHT,
            full_name="Sardorbek Flight",
            phone="+998907765433",
            service_name="TAS-DXB Flight",
        )

    def test_build_lead_keyboard_has_tel_and_callback(self):
        kb = build_lead_keyboard('tour', str(self.tour_lead.id), self.tour_lead.phone, 'new')
        buttons = kb.get('inline_keyboard', [])
        self.assertEqual(len(buttons), 2)
        # Call button uses https://t.me/ URL scheme for Telegram API compatibility
        self.assertTrue(buttons[0][0]['url'].startswith('https://t.me/'))
        # Status button opens menu
        self.assertEqual(buttons[1][0]['callback_data'], f'st_menu:tour:{self.tour_lead.id}')

    def test_build_lead_status_selection_keyboard(self):
        kb = build_lead_status_selection_keyboard('tour', str(self.tour_lead.id))
        rows = kb.get('inline_keyboard', [])
        self.assertEqual(len(rows), 3)
        self.assertIn('st_set:tour:', rows[0][0]['callback_data'])
        self.assertIn('st_back:tour:', rows[2][0]['callback_data'])

    def test_format_lead_cards(self):
        text, markup = format_tour_lead_card(self.tour_lead)
        self.assertIn("YANGI TUR SO'ROVI KELDI!", text)
        self.assertIn("https://t.me/+998907765431", markup['inline_keyboard'][0][0]['url'])

        text_serv, markup_serv = format_service_lead_card(self.service_lead)
        self.assertIn("YANGI PARVOZ BILETI SO'ROVI!", text_serv)
        self.assertIn("https://t.me/+998907765433", markup_serv['inline_keyboard'][0][0]['url'])

    @patch('apps.notifications.bot_handlers.get_bot')
    def test_handle_lead_status_callback_st_set(self, mock_get_bot):
        mock_bot = MagicMock()
        mock_get_bot.return_value = mock_bot

        callback = {
            'id': 'cb_123',
            'data': f'st_set:tour:{self.tour_lead.id}:contacted',
            'message': {
                'chat': {'id': -100123456789, 'type': 'supergroup'},
                'message_id': 55,
            },
            'from': {'username': 'operator_sardor', 'first_name': 'Sardor'},
        }

        res = _handle_lead_status_callback(callback)
        self.assertTrue(res)

        self.tour_lead.refresh_from_db()
        self.assertEqual(self.tour_lead.status, 'contacted')
        self.assertEqual(self.tour_lead.assigned_staff_name, 'operator_sardor')
        mock_bot.edit_message_text.assert_called_once()
        mock_bot.answer_callback_query.assert_called_once()
