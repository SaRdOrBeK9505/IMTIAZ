"""
AI Provider registry.

Mavjud provayderlar:
    claude  — Anthropic Claude (default)
    gemini  — Google Gemini Flash
"""

from .base import BaseAIProvider, AIMessage, AIResponse

__all__ = [
    'BaseAIProvider', 'AIMessage', 'AIResponse',
    'ClaudeProvider', 'GeminiProvider',
]


def __getattr__(name: str):
    if name == 'ClaudeProvider':
        from .claude_provider import ClaudeProvider
        return ClaudeProvider
    if name == 'GeminiProvider':
        from .gemini_provider import GeminiProvider
        return GeminiProvider
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
