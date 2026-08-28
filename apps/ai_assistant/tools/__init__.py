"""
AI function-calling tools ta'riflari.
Har bir xizmat turi uchun alohida tool — Claude bu tool'lardan foydalanib bron qiladi.
"""

from .definitions import get_all_tools, get_all_tools_for_bot

__all__ = ['get_all_tools', 'get_all_tools_for_bot']
