"""
Abstract AI Provider interfeysi.
Kelajakda Claude API → lokal model almashtirish faqat yangi provider yozish bilan amalga oshadi.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIMessage:
    role: str  # 'user' | 'assistant' | 'system'
    content: str | list  # str yoki tool_use/tool_result bloklari ro'yxati


@dataclass
class AIResponse:
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    tokens_used: int = 0
    stop_reason: str = 'end_turn'
    raw: Any = None


class BaseAIProvider(ABC):
    """Barcha AI provayderlar shu interfeysni implement qilishi shart."""

    @abstractmethod
    def chat(
        self,
        messages: list[AIMessage],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
        use_thinking: bool = False,
    ) -> AIResponse:
        """
        Xabarlar ro'yxatini yuboradi va AI javobini qaytaradi.
        tools — Claude function-calling uchun tool ta'riflari ro'yxati.
        use_thinking — murakkab savollarda extended reasoning (Gemini Pro).
        """
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """Hozir ishlatiladigan model nomini qaytaradi."""
        ...
