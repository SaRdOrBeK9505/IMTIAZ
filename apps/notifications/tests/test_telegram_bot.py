"""Telegram bot webhook va handler testlari."""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.notifications.bot_content import (
    CB_ABOUT,
    CB_MENU,
    CB_SERVICES,
    welcome_text,
)
from apps.notifications.bot_handlers import handle_update


@override_settings(
    TELEGRAM_BOT_TOKEN='test-token',
    TELEGRAM_BOT_SECRET='test-secret',
    FRONTEND_URL='https://app.example.com',
)
class TelegramBotHandlerTests(TestCase):

    @patch('apps.notifications.bot_handlers.get_bot')
    def test_start_sends_welcome_and_keyboard(self, mock_get_bot):
        bot = MagicMock()
        mock_get_bot.return_value = bot

        handle_update({
            'message': {
                'message_id': 1,
                'chat': {'id': 12345, 'type': 'private'},
                'from': {'id': 12345, 'username': 'testuser'},
                'text': '/start',
            },
        })

        bot.send_message.assert_called_once()
        args, kwargs = bot.send_message.call_args
        self.assertEqual(args[0], 12345)
        self.assertIn('IMTIAZ', args[1])
        self.assertIn('inline_keyboard', kwargs['reply_markup'])

    @patch('apps.notifications.bot_handlers.AIAssistantService')
    @patch('apps.notifications.bot_handlers.get_bot')
    def test_text_message_triggers_ai_service(self, mock_get_bot, mock_ai_service_cls):
        bot = MagicMock()
        mock_get_bot.return_value = bot
        ai_service_inst = MagicMock()
        ai_service_inst.chat.return_value = {
            'session_id': 'sess-123',
            'content': 'Assalomu alaykum, qanday yordam bera olaman?',
            'requires_confirmation': False,
        }
        mock_ai_service_cls.return_value = ai_service_inst

        handle_update({
            'message': {
                'message_id': 2,
                'chat': {'id': 99999, 'type': 'private'},
                'from': {'id': 99999, 'username': 'aitestuser', 'first_name': 'AI User'},
                'text': 'Salom AI',
            },
        })

        bot.send_chat_action.assert_called_once_with(99999, 'typing')
        bot.send_message.assert_called_once()
        args, kwargs = bot.send_message.call_args
        self.assertEqual(args[0], 99999)
        self.assertIn('Assalomu alaykum', args[1])

    @patch('apps.notifications.bot_handlers.get_bot')
    def test_callback_about_edits_message(self, mock_get_bot):
        bot = MagicMock()
        mock_get_bot.return_value = bot

        handle_update({
            'callback_query': {
                'id': 'cb1',
                'data': CB_ABOUT,
                'message': {
                    'message_id': 10,
                    'chat': {'id': 12345},
                },
            },
        })

        bot.answer_callback_query.assert_called_once_with('cb1')
        bot.edit_message_text.assert_called_once()
        kwargs = bot.edit_message_text.call_args.kwargs
        self.assertIn('IMTIAZ', kwargs['text'])

    @patch('apps.notifications.bot_handlers.get_bot')
    def test_callback_menu_returns_welcome(self, mock_get_bot):
        bot = MagicMock()
        mock_get_bot.return_value = bot

        handle_update({
            'callback_query': {
                'id': 'cb2',
                'data': CB_MENU,
                'message': {
                    'message_id': 11,
                    'chat': {'id': 12345},
                },
            },
        })

        kwargs = bot.edit_message_text.call_args.kwargs
        self.assertEqual(kwargs['text'], welcome_text())


@override_settings(TELEGRAM_BOT_SECRET='test-secret')
class TelegramWebhookViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    @patch('apps.notifications.bot_handlers.handle_update')
    def test_webhook_accepts_valid_secret(self, mock_handle):
        resp = self.client.post(
            '/api/notifications/telegram/webhook/',
            {'message': {'text': '/start', 'chat': {'id': 1}}},
            format='json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='test-secret',
        )
        self.assertEqual(resp.status_code, 200)
        mock_handle.assert_called_once()

    def test_webhook_rejects_invalid_secret(self):
        resp = self.client.post(
            '/api/notifications/telegram/webhook/',
            {'message': {'text': '/start'}},
            format='json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='wrong',
        )
        self.assertEqual(resp.status_code, 403)

    @patch('apps.notifications.bot_handlers.handle_update')
    def test_webhook_without_secret_when_not_configured(self, mock_handle):
        with override_settings(TELEGRAM_BOT_SECRET=''):
            resp = self.client.post(
                '/api/notifications/telegram/webhook/',
                {'callback_query': {'data': CB_SERVICES}},
                format='json',
            )
            self.assertEqual(resp.status_code, 200)


class MiniAppUrlTests(TestCase):

    def test_mini_app_ai_url_custom_env(self):
        from apps.notifications.bot_content import mini_app_ai_url
        with override_settings(TELEGRAM_MINI_APP_AI_URL='https://custom-ai-chat.com/chat'):
            url = mini_app_ai_url()
            self.assertEqual(url, 'https://custom-ai-chat.com/chat')

    def test_mini_app_ai_url_fallback(self):
        from apps.notifications.bot_content import mini_app_ai_url
        with override_settings(TELEGRAM_MINI_APP_AI_URL='', FRONTEND_URL='https://frontend.com'):
            url = mini_app_ai_url('test_param')
            self.assertEqual(url, 'https://frontend.com/ai?welcome=1&start_param=test_param')

