"""Parvoz qidiruv validatsiyasi va Bookhara mapping testlari."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.ai_assistant.tool_handlers import handle_search_flights
from apps.integrations.adapters.bookhara import BookharaAdapter, normalize_bookhara_seat_class
from apps.users.models import User


class BookharaSeatClassTests(TestCase):
    def test_economy_maps_to_e(self):
        self.assertEqual(normalize_bookhara_seat_class('economy'), 'E')

    def test_business_maps_to_b(self):
        self.assertEqual(normalize_bookhara_seat_class('business'), 'B')

    def test_adapter_search_uses_bookhara_class(self):
        adapter = BookharaAdapter()
        tomorrow = (timezone.now().date() + timedelta(days=1)).isoformat()
        with patch.object(adapter.client, 'get', return_value={'data': []}) as mock_get:
            adapter.search('TAS', 'DXB', tomorrow, seat_class='economy')
            params = mock_get.call_args.kwargs['params']
            self.assertEqual(params['service_class'], 'E')


class FlightSearchValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(phone='+998901238000', is_phone_verified=True)

    @patch('apps.integrations.errors.is_bookhara_configured', return_value=True)
    @patch('apps.integrations.adapters.bookhara.BookharaAdapter.search', return_value=[])
    def test_past_date_rejected_before_api_call(self, mock_search, _configured):
        yesterday = (timezone.now().date() - timedelta(days=1)).isoformat()
        result = handle_search_flights(
            self.user,
            origin='TAS',
            destination='DXB',
            departure_date=yesterday,
            lang='uz',
        )
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_code'], 'past_date')
        mock_search.assert_not_called()

    @patch('apps.integrations.errors.is_bookhara_configured', return_value=True)
    @patch('apps.integrations.adapters.bookhara.BookharaAdapter.search', return_value=[])
    def test_city_names_normalized(self, mock_search, _configured):
        tomorrow = (timezone.now().date() + timedelta(days=1)).isoformat()
        handle_search_flights(
            self.user,
            origin='Toshkent',
            destination='Dubay',
            departure_date=tomorrow,
            lang='uz',
        )
        mock_search.assert_called_once()
        kwargs = mock_search.call_args.kwargs
        self.assertEqual(kwargs['origin'], 'TAS')
        self.assertEqual(kwargs['destination'], 'DXB')
