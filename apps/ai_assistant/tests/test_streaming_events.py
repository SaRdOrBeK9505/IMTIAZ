from unittest.mock import patch, MagicMock
from django.test import TestCase
from apps.users.models import User
from apps.ai_assistant.services import AIAssistantService
from apps.ai_assistant.providers.base import BaseAIProvider, AIMessage, AIResponse

class MockAIProvider(BaseAIProvider):
    def get_model_name(self) -> str:
        return "mock-model"

    def chat(self, messages, tools=None, system=None, max_tokens=None, log_context=None) -> AIResponse:
        return AIResponse(content="Mock response", tool_calls=[])

    def chat_stream(self, messages, tools=None, system=None, max_tokens=None, log_context=None):
        # Tool call qaytaramiz
        yield {
            '__final': True,
            'tokens_used': 100,
            'tool_calls': [
                {
                    'id': 'call-1',
                    'name': 'search_flights',
                    'input': {'origin': 'TAS', 'destination': 'DXB', 'departure_date': '2026-08-20'}
                }
            ]
        }

class StreamingToolEventsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create(phone='+998901239999', is_phone_verified=True)
        self.provider = MockAIProvider()
        self.service = AIAssistantService(provider=self.provider)

    @patch('apps.ai_assistant.services.get_all_tools', return_value=[])
    @patch('apps.ai_assistant.services.AIAssistantService._dispatch_tool', return_value={'flights': []})
    def test_chat_stream_yields_tool_start_and_end_events(self, mock_dispatch, mock_get_tools):
        events = list(self.service.chat_stream(
            user=self.user,
            message="Toshkentdan Dubayga parvozlar",
            session_id=None
        ))

        # Eventlar ro'yxatida tool_processing, tool_start, tool_end va done bo'lishi kerak
        event_types = [e.get('type') for e in events]
        
        self.assertIn('tool_processing', event_types)
        self.assertIn('tool_start', event_types)
        self.assertIn('tool_end', event_types)
        self.assertIn('done', event_types)

        # tool_start detallarini tekshirish
        tool_start_event = next(e for e in events if e.get('type') == 'tool_start')
        self.assertEqual(tool_start_event['tool_name'], 'search_flights')
        self.assertEqual(tool_start_event['input']['origin'], 'TAS')

        # tool_end detallarini tekshirish
        tool_end_event = next(e for e in events if e.get('type') == 'tool_end')
        self.assertEqual(tool_end_event['tool_name'], 'search_flights')
        self.assertEqual(tool_end_event['status'], 'success')
