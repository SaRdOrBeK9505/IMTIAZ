from django.test import TestCase
from unittest.mock import MagicMock
from apps.ai_assistant.providers.fallback_provider import FallbackProvider
from apps.ai_assistant.providers.base import BaseAIProvider, AIMessage, AIResponse

class MockProvider(BaseAIProvider):
    def __init__(self, name: str, should_fail: bool = False):
        self.name = name
        self.should_fail = should_fail
        self.chat_called = 0
        self.stream_called = 0

    def get_model_name(self) -> str:
        return self.name

    def chat(self, messages, tools=None, system=None, max_tokens=None, log_context=None) -> AIResponse:
        self.chat_called += 1
        if self.should_fail:
            raise Exception(f"Provider {self.name} simulation error")
        return AIResponse(content=f"Response from {self.name}", tool_calls=[])

    def chat_stream(self, messages, tools=None, system=None, max_tokens=None, log_context=None):
        self.stream_called += 1
        if self.should_fail:
            raise Exception(f"Provider {self.name} stream simulation error")
        yield f"Stream chunk from {self.name}"

class FallbackProviderTests(TestCase):

    def test_fallback_provider_uses_primary_when_healthy(self):
        primary = MockProvider("Primary")
        fallback = MockProvider("Fallback")
        provider = FallbackProvider(primary, fallback)

        response = provider.chat([AIMessage(role="user", content="hello")])
        self.assertEqual(response.content, "Response from Primary")
        self.assertEqual(primary.chat_called, 1)
        self.assertEqual(fallback.chat_called, 0)

    def test_fallback_provider_falls_back_on_primary_chat_error(self):
        primary = MockProvider("Primary", should_fail=True)
        fallback = MockProvider("Fallback")
        provider = FallbackProvider(primary, fallback)

        response = provider.chat([AIMessage(role="user", content="hello")])
        self.assertEqual(response.content, "Response from Fallback")
        self.assertEqual(primary.chat_called, 1)
        self.assertEqual(fallback.chat_called, 1)

    def test_fallback_provider_stream_uses_primary_when_healthy(self):
        primary = MockProvider("Primary")
        fallback = MockProvider("Fallback")
        provider = FallbackProvider(primary, fallback)

        chunks = list(provider.chat_stream([AIMessage(role="user", content="hello")]))
        self.assertEqual(chunks, ["Stream chunk from Primary"])
        self.assertEqual(primary.stream_called, 1)
        self.assertEqual(fallback.stream_called, 0)

    def test_fallback_provider_stream_falls_back_on_primary_stream_init_error(self):
        primary = MockProvider("Primary", should_fail=True)
        fallback = MockProvider("Fallback")
        provider = FallbackProvider(primary, fallback)

        chunks = list(provider.chat_stream([AIMessage(role="user", content="hello")]))
        self.assertEqual(chunks, ["Stream chunk from Fallback"])
        self.assertEqual(primary.stream_called, 1)
        self.assertEqual(fallback.stream_called, 1)
