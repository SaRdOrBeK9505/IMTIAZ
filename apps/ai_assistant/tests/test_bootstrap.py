"""AI bootstrap va poyezd xizmati olib tashlanganligi testlari."""

from django.test import TestCase

from apps.ai_assistant.i18n import build_system_prompt, t
from apps.ai_assistant.services import AIAssistantService
from apps.ai_assistant.tools import get_all_tools
from apps.users.models import User


class TrainServiceRemovedTests(TestCase):

    def test_search_trains_not_in_tools(self):
        names = [tool['name'] for tool in get_all_tools()]
        self.assertNotIn('search_trains', names)

    def test_system_prompt_no_train_service_uz(self):
        prompt = build_system_prompt('uz', '500,000', 'manual')
        self.assertIn('parvoz, restoran', prompt)
        self.assertNotIn('parvoz, poyezd', prompt)
        self.assertIn('mavjud emas', prompt)

    def test_system_prompt_no_train_service_en(self):
        prompt = build_system_prompt('en', '500,000', 'manual')
        self.assertNotIn('trains', prompt.lower())
        self.assertIn('not available', prompt)


class SessionBootstrapTests(TestCase):

    def setUp(self):
        self.user = User.objects.create(
            phone='+998901112244',
            language_code='uz',
        )
        self.service = AIAssistantService()

    def test_bootstrap_creates_welcome_message(self):
        result = self.service.bootstrap_session(self.user)
        self.assertFalse(result['already_started'])
        self.assertIn('IMTIAZ', result['content'])
        self.assertIn('qanday yordam', result['content'].lower())

    def test_bootstrap_idempotent_for_existing_session(self):
        first = self.service.bootstrap_session(self.user)
        second = self.service.bootstrap_session(
            self.user, session_id=first['session_id'],
        )
        self.assertTrue(second['already_started'])

    def test_ai_welcome_no_trains(self):
        welcome = t('ai_welcome', 'uz')
        self.assertNotIn('poyezd', welcome.lower())
        self.assertNotIn('train', welcome.lower())
