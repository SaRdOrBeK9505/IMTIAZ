"""Gemini API test skript — audit uchun."""
import os, sys, time
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

import django
django.setup()

from django.conf import settings
from apps.ai_assistant.providers.gemini_provider import GeminiProvider
from apps.ai_assistant.providers.base import AIMessage

print(f"AI_PROVIDER: {settings.AI_PROVIDER}")
print(f"GEMINI_MODEL: {settings.GEMINI_MODEL}")
print(f"GEMINI_API_KEY set: {bool(settings.GEMINI_API_KEY)}")

tests = [
    ("Sen kimsan?", "Test 1 - o'zini tanishtirish"),
    ("Menga Python'da web scraper yozib ber", "Test 2 - mavzudan chalg'itish"),
]

try:
    provider = GeminiProvider()
    system = """Sen IMTIAZ — premium lifestyle concierge platformasining AI assistantisan.
MUHIM QOIDALAR:
1. FAQAT IMTIAZ mavzularida: sayohat, restoran, tadbirlar, xizmatlar
2. Boshqa mavzularda: "Men faqat IMTIAZ xizmatlari haqida yordam bera olaman."
"""

    for msg_text, label in tests:
        print(f"\n{'='*60}")
        print(f"{label}")
        print(f"Savol: {msg_text}")
        start = time.time()
        resp = provider.chat(
            messages=[AIMessage(role='user', content=msg_text)],
            system=system,
            tools=None,
        )
        elapsed = time.time() - start
        print(f"Javob ({elapsed:.2f}s): {resp.content[:500]}")
        print(f"Tokens: {resp.tokens_used}")
except Exception as e:
    print(f"XATO: {e}")
    import traceback; traceback.print_exc()
