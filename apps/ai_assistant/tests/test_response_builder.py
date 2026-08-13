"""Response builder — aqlli javob formatlash testlari."""

from django.test import TestCase

from apps.ai_assistant.response_builder import (
    build_reply_from_tools,
    should_use_local_reply,
)


class FlightFormatTests(TestCase):
    def test_flight_shows_departure_arrival_times(self):
        reply = build_reply_from_tools([{
            'tool_name': 'search_flights',
            'result': {
                'status': 'ok',
                'origin': 'TAS',
                'destination': 'IST',
                'departure_date': '2026-08-14',
                'offers': [
                    {
                        'airline': 'AZAL',
                        'flight_number': '532',
                        'departure_at': '2026-08-14T08:30:00',
                        'arrival_at': '2026-08-14T12:45:00',
                        'price': 2994616,
                        'currency': 'UZS',
                        'baggage': True,
                    },
                ],
            },
        }], lang='uz')
        self.assertIn('08:30', reply)
        self.assertIn('12:45', reply)
        self.assertIn('AZAL', reply)

    def test_detail_question_uses_llm_not_local(self):
        tool_results = [{
            'tool_name': 'search_flights',
            'result': {'status': 'ok', 'offers': [{'price': 1}]},
        }]
        self.assertFalse(should_use_local_reply(tool_results, 'Soati?', 'uz'))
        self.assertFalse(should_use_local_reply(tool_results, 'To\'liqroq ma\'lumot', 'uz'))
        self.assertTrue(should_use_local_reply(tool_results, 'Parvoz qidiring', 'uz'))


class TourEmptyFormatTests(TestCase):
    def test_empty_tours_shows_partners_not_scary_message(self):
        reply = build_reply_from_tools([{
            'tool_name': 'search_tour_packages',
            'result': {
                'status': 'ok',
                'results': [],
                'partners': [
                    {'name': 'Lead Tour', 'package_count': 2},
                    {'name': 'Yangi Kompaniya', 'package_count': 0},
                ],
                'popular_destinations': [
                    {'name': 'Samarqand', 'country': 'O\'zbekiston'},
                ],
            },
        }], lang='uz')
        self.assertIn('Lead Tour', reply)
        self.assertIn('Samarqand', reply)
        self.assertNotEqual(reply.strip(), 'Mos tur paket topilmadi.')

    def test_empty_tours_forces_llm_reply(self):
        tool_results = [{
            'tool_name': 'search_tour_packages',
            'result': {'status': 'ok', 'results': [], 'partners': []},
        }]
        self.assertFalse(should_use_local_reply(tool_results, 'Tur haqida', 'uz'))
