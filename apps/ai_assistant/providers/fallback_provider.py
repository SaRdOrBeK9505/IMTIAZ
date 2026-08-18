"""
AI Provider Fallback Wrapper.
Primary provayder xatoga uchrasa, avtomatik ravishda Secondary (zaxira) provayderga o'tadi.
"""

from __future__ import annotations

import logging
from .base import BaseAIProvider, AIMessage, AIResponse

logger = logging.getLogger(__name__)

class FallbackProvider(BaseAIProvider):
    """
    Primary provayderdan javob ololmasa, secondary provayderga failover qiluvchi wrapper.
    """

    def __init__(self, primary: BaseAIProvider, fallback: BaseAIProvider):
        self.primary = primary
        self.fallback = fallback

    def get_model_name(self) -> str:
        return f"{self.primary.get_model_name()} (zaxira: {self.fallback.get_model_name()})"

    def chat(
        self,
        messages: list[AIMessage],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
        log_context: dict | None = None,
    ) -> AIResponse:
        try:
            logger.info("Primary AI Provider (%s) orqali so'rov yuborilmoqda...", self.primary.get_model_name())
            return self.primary.chat(messages, tools, system, max_tokens, log_context)
        except Exception as e:
            logger.warning(
                "Asosiy AI provayder xatoga uchradi. Zaxiradagi provayderga (%s) o'tilmoqda. Xato: %s",
                self.fallback.get_model_name(), e
            )
            # Zaxira provayderga murojaat
            return self.fallback.chat(messages, tools, system, max_tokens, log_context)

    def chat_stream(
        self,
        messages: list[AIMessage],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
        log_context: dict | None = None,
    ):
        """
        Streaming so'rovlar uchun failover.
        Oqim boshlanishida (birinchi token kelguncha) xato bo'lsa, zaxiraga o'tadi.
        """
        try:
            logger.info("Primary AI Provider (%s) orqali stream boshlanmoqda...", self.primary.get_model_name())
            primary_stream = self.primary.chat_stream(messages, tools, system, max_tokens, log_context)
            iterator = iter(primary_stream)
        except Exception as e:
            logger.warning(
                "Asosiy AI stream boshlanishida xato. Zaxiraga (%s) o'tilmoqda. Xato: %s",
                self.fallback.get_model_name(), e
            )
            yield from self.fallback.chat_stream(messages, tools, system, max_tokens, log_context)
            return

        # Birinchi tokenni olishga urinish
        first_chunk = None
        has_first = False
        try:
            first_chunk = next(iterator)
            has_first = True
        except StopIteration:
            pass
        except Exception as e:
            logger.warning(
                "Asosiy AI stream birinchi tokenida xato. Zaxiraga (%s) o'tilmoqda. Xato: %s",
                self.fallback.get_model_name(), e
            )
            yield from self.fallback.chat_stream(messages, tools, system, max_tokens, log_context)
            return

        if has_first:
            yield first_chunk
            try:
                for chunk in iterator:
                    yield chunk
            except Exception as e:
                # Oqim o'rtasida xato bo'lsa, zaxiraga o'tib bo'lmaydi (chunki allaqachon qisman javob ketgan)
                logger.error("Asosiy AI stream oqim o'rtasida uzildi: %s", e)
                raise
