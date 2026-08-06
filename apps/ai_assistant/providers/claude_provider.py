"""
Claude (Anthropic) AI Provider implementatsiyasi.
"""

import logging
from django.conf import settings
import anthropic

from .base import BaseAIProvider, AIMessage, AIResponse

logger = logging.getLogger(__name__)


class ClaudeProvider(BaseAIProvider):
    """Anthropic Claude API orqali AI xizmati."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model or settings.AI_MODEL
        self._client = anthropic.Anthropic(api_key=self.api_key)

    def get_model_name(self) -> str:
        return self.model

    def chat(
        self,
        messages: list[AIMessage],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> AIResponse:
        if max_tokens is None:
            max_tokens = settings.AI_MAX_TOKENS

        # AIMessage → Anthropic format
        formatted_messages = [
            {'role': msg.role, 'content': msg.content}
            for msg in messages
            if msg.role != 'system'  # system alohida parametr
        ]

        kwargs: dict = {
            'model': self.model,
            'max_tokens': max_tokens,
            'messages': formatted_messages,
        }
        if system:
            kwargs['system'] = system
        if tools:
            kwargs['tools'] = tools

        try:
            response = self._client.messages.create(**kwargs)
        except anthropic.APIError as e:
            logger.error('Claude API xatosi: %s', e)
            raise

        # Javobni parse qilish
        text_content = ''
        tool_calls = []
        for block in response.content:
            if block.type == 'text':
                text_content = block.text
            elif block.type == 'tool_use':
                tool_calls.append({
                    'id': block.id,
                    'name': block.name,
                    'input': block.input,
                })

        return AIResponse(
            content=text_content,
            tool_calls=tool_calls,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            stop_reason=response.stop_reason or 'end_turn',
            raw=response,
        )
