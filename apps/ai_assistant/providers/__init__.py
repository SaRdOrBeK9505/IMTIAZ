"""
AI Provider registry.

Mavjud provayderlar:
    claude  — Anthropic Claude (default)
    gemini  — Google Gemini Flash

Yangi provider qo'shish:
    1. apps/ai_assistant/providers/<name>_provider.py
    2. BaseAIProvider implement qilish
    3. get_provider() ga qo'shish (services.py)
"""

from .base import BaseAIProvider, AIMessage, AIResponse
from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider

__all__ = [
    'BaseAIProvider', 'AIMessage', 'AIResponse',
    'ClaudeProvider', 'GeminiProvider',
]
