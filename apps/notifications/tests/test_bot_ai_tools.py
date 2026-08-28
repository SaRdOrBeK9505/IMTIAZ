"""Bot AI tools testlari - for_bot=True parametri bilan."""

from django.test import TestCase


class ToolsComparisonTests(TestCase):
    """Bot va Chat tools ro'yxatlarini solishtirish testlari."""

    def test_bot_has_more_tools_than_chat(self):
        """Botda chatdan ko'proq tool mavjud."""
        from apps.ai_assistant.tools import get_all_tools, get_all_tools_for_bot
        
        chat_tools = get_all_tools()
        bot_tools = get_all_tools_for_bot()
        
        chat_tool_names = {t['name'] for t in chat_tools}
        bot_tool_names = {t['name'] for t in bot_tools}
        
        # Botda chatda yo'q tool'lar bor
        extra_in_bot = bot_tool_names - chat_tool_names
        self.assertIn('search_restaurants', extra_in_bot)
        self.assertIn('search_tour_packages', extra_in_bot)
        self.assertIn('submit_restaurant_lead', extra_in_bot)
        self.assertIn('submit_tour_lead', extra_in_bot)
        self.assertIn('book_restaurant', extra_in_bot)
        
        # Chatdagi barcha tool'lar botda ham bor
        self.assertTrue(chat_tool_names.issubset(bot_tool_names))

    def test_bot_tools_count(self):
        """Bot tools ro'yxati soni."""
        from apps.ai_assistant.tools import get_all_tools_for_bot
        
        bot_tools = get_all_tools_for_bot()
        self.assertGreater(len(bot_tools), 10, "Botda kamida 10 ta tool bo'lishi kerak")

    def test_chat_tools_count(self):
        """Chat tools ro'yxati soni."""
        from apps.ai_assistant.tools import get_all_tools, get_all_tools_for_bot
        
        chat_tools = get_all_tools()
        bot_tools = get_all_tools_for_bot()
        # Chatda cheklangan ro'yxat (owner talabi asosida)
        self.assertLess(len(chat_tools), len(bot_tools))

    def test_bot_restaurant_tools_available(self):
        """Botda restoran bilan bog'liq tool'lar mavjud."""
        from apps.ai_assistant.tools import get_all_tools_for_bot
        
        tools = get_all_tools_for_bot()
        tool_names = [t['name'] for t in tools]
        
        self.assertIn('search_restaurants', tool_names)
        self.assertIn('book_restaurant', tool_names)
        self.assertIn('submit_restaurant_lead', tool_names)

    def test_bot_tour_tools_available(self):
        """Botda tur bilan bog'liq tool'lar mavjud."""
        from apps.ai_assistant.tools import get_all_tools_for_bot
        
        tools = get_all_tools_for_bot()
        tool_names = [t['name'] for t in tools]
        
        self.assertIn('search_tour_packages', tool_names)
        self.assertIn('submit_tour_lead', tool_names)

    def test_chat_missing_restaurant_tools(self):
        """Chatda restoran tool'lari yo'q."""
        from apps.ai_assistant.tools import get_all_tools
        
        tools = get_all_tools()
        tool_names = [t['name'] for t in tools]
        
        self.assertNotIn('search_restaurants', tool_names)
        self.assertNotIn('book_restaurant', tool_names)
        self.assertNotIn('submit_restaurant_lead', tool_names)

    def test_chat_missing_tour_tools(self):
        """Chatda tur tool'lari yo'q."""
        from apps.ai_assistant.tools import get_all_tools
        
        tools = get_all_tools()
        tool_names = [t['name'] for t in tools]
        
        self.assertNotIn('search_tour_packages', tool_names)
        self.assertNotIn('submit_tour_lead', tool_names)
