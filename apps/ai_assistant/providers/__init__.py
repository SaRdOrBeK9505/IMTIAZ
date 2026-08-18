"""
AI Provider registry.

Mavjud provayderlar:
    gemini  — Google Gemini Flash (asosiy)
    openai  — OpenAI GPT-4o-mini (zaxira / ikkinchi provider)
    claude  — Anthropic Claude (uchinchi provider, ixtiyoriy)
"""

from .base import BaseAIProvider, AIMessage, AIResponse

__all__ = [
    'BaseAIProvider', 'AIMessage', 'AIResponse',
    'ClaudeProvider', 'GeminiProvider', 'OpenAIProvider', 'FallbackProvider',
]


def __getattr__(name: str):
    if name == 'ClaudeProvider':
        from .claude_provider import ClaudeProvider
        return ClaudeProvider
    if name == 'GeminiProvider':
        from .gemini_provider import GeminiProvider
        return GeminiProvider
    if name == 'OpenAIProvider':
        from .openai_provider import OpenAIProvider
        return OpenAIProvider
    if name == 'FallbackProvider':
        from .fallback_provider import FallbackProvider
        return FallbackProvider
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
