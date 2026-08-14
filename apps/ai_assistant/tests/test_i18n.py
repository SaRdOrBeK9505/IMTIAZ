"""Ko'p tilli AI qo'llab-quvvatlash testlari."""

from django.test import TestCase

from apps.ai_assistant.i18n import (
    build_confirmation_summary,
    build_system_prompt,
    detect_language_from_text,
    normalize_language,
    resolve_language,
    t,
)
from apps.ai_assistant.response_builder import build_reply_from_tools
from apps.users.models import User


class LanguageDetectionTests(TestCase):

    def test_detect_russian_cyrillic(self):
        self.assertEqual(
            detect_language_from_text('Привет, найди рейс в Дубай'),
            'ru',
        )

    def test_detect_english(self):
        self.assertEqual(
            detect_language_from_text('Hello, please find a flight to Dubai'),
            'en',
        )

    def test_detect_uzbek_latin_returns_none_or_uz(self):
        result = detect_language_from_text('Salom, Toshkentga parvoz qidiring')
        self.assertIn(result, (None, 'uz'))

    def test_normalize_language(self):
        self.assertEqual(normalize_language('ru-RU'), 'ru')
        self.assertEqual(normalize_language('fr'), 'uz')

    def test_resolve_from_message_overrides_profile(self):
        user = User.objects.create(
            phone='+998901112233',
            language_code='uz',
        )
        self.assertEqual(
            resolve_language(user, 'Find me a restaurant please'),
            'en',
        )


class TranslationTests(TestCase):

    def test_system_prompt_russian(self):
        prompt = build_system_prompt('ru', '500,000', 'manual')
        self.assertIn('русский', prompt)
        self.assertIn('IMTIAZ', prompt)

    def test_system_prompt_english(self):
        prompt = build_system_prompt('en', '500,000', 'manual')
        self.assertIn('English', prompt)

    def test_confirmation_summary_english(self):
        summary = build_confirmation_summary(
            'book_flight',
            {'origin': 'TAS', 'destination': 'DXB', 'departure_date': '2026-09-01', 'passengers': 2},
            None,
            lang='en',
        )
        self.assertIn('Flight booking request', summary)
        self.assertIn('Confirm', summary)

    def test_response_builder_russian_error(self):
        reply = build_reply_from_tools([{
            'tool_name': 'search_flights',
            'result': {
                'status': 'error',
                'message': 'Сервис временно недоступен.',
            },
        }], lang='ru')
        self.assertIn('Сервис', reply)

    def test_flight_not_found_english(self):
        reply = build_reply_from_tools([{
            'tool_name': 'search_flights',
            'result': {
                'status': 'ok',
                'origin': 'TAS',
                'destination': 'DXB',
                'departure_date': '2026-09-01',
                'offers': [],
            },
        }], lang='en')
        self.assertIn('No direct flights', reply)
