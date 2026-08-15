from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ai_assistant.i18n import build_system_prompt
from apps.ai_assistant.models import AIActionLog, ConversationSession, UserAIProfile
from apps.ai_assistant.providers.base import AIResponse, BaseAIProvider
from apps.ai_assistant.services import AIAssistantService


class DummyProvider(BaseAIProvider):
    def chat(self, messages, tools=None, system=None, max_tokens=4096):
        return AIResponse(content='ok')

    def get_model_name(self):
        return 'dummy'


class AIPersistentMemoryTests(TestCase):
    def test_build_system_prompt_includes_persistent_profile(self):
        prompt = build_system_prompt(
            lang='uz',
            price_limit='500000',
            autonomy_level='manual',
            session_summary='Current topic: flights',
            user_profile_summary='Foydalanuvchi odatda business klassini tanlaydi.',
        )
        self.assertIn('Current topic: flights', prompt)
        self.assertIn('Doimiy foydalanuvchi profili', prompt)
        self.assertIn('business klassini', prompt)

    def test_refresh_user_profile_stores_long_term_preferences(self):
        User = get_user_model()
        user = User.objects.create_user(phone='+998901234567', password='secret123')
        session = ConversationSession.objects.create(user=user, title='Test session')

        AIActionLog.objects.create(
            user=user,
            session=session,
            action_type=AIActionLog.ActionType.SEARCH,
            payload={'destination': 'Dubai', 'seat_class': 'business'},
            status=AIActionLog.ActionStatus.SUCCESS,
        )

        service = AIAssistantService(provider=DummyProvider())
        service._refresh_user_ai_profile(user, session)

        profile = UserAIProfile.objects.get(user=user)
        self.assertEqual(profile.preferred_seat_class, 'business')
        self.assertIn('Dubai', profile.summary_text)
