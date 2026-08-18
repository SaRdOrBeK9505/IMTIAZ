import time
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.users.models import User
from apps.ai_assistant.providers.gemini_provider import GeminiProvider
from apps.ai_assistant.providers.openai_provider import OpenAIProvider
from apps.ai_assistant.providers.base import AIMessage
from apps.ai_assistant.tools import get_all_tools
from apps.ai_assistant.i18n import build_system_prompt

class Command(BaseCommand):
    help = "AI Assistant modellarini benchmark qilish (Gemini vs Flash-Lite vs OpenAI)"

    def handle(self, *args, **options):
        self.stdout.write("AI assistant benchmark boshlanmoqda...")

        # 1. Test foydalanuvchisi va test ma'lumotlarini tayyorlash
        user = User.objects.first()
        if not user:
            # Agar DB bo'sh bo'lsa
            user = User.objects.create(phone='+998901112233', language_code='uz')

        system = build_system_prompt(
            lang='uz',
            price_limit='5,000,000',
            autonomy_level='semi_auto',
            session_summary="Suhbat endi boshlandi.",
            user_profile_summary="Foydalanuvchi faqat aviachipta va restoranlar qidiradi."
        )
        tools = get_all_tools()

        # Test so'rovlari (simple vs complex reasoning)
        queries = [
            {
                "query": "Salom, siz kimsiz va menga nimalarda yordam bera olasiz?",
                "type": "simple_chat",
                "expected_tool": None
            },
            {
                "query": "Toshkentda 19:00 ga 4 kishilik restoran qidirib ber",
                "type": "tool_call",
                "expected_tool": "search_restaurants"
            },
            {
                "query": "Toshkentdan Dubayga 2026-08-25 sanaga chipta bormi?",
                "type": "tool_call",
                "expected_tool": "search_flights"
            },
            {
                "query": "Dubayga 2 kishilik 5 kunlik qiziqarli turlarni top",
                "type": "tool_call",
                "expected_tool": "search_tour_packages"
            },
            {
                "query": "Menga Toshkentdagi barcha qiziqarli konsert yoki tadbirlarni ko'rsat",
                "type": "tool_call",
                "expected_tool": "search_events"
            },
            {
                "query": "Mening oxirgi buyurtmalarimni bekor qilib bering",
                "type": "tool_call",
                "expected_tool": "cancel_booking"
            },
            {
                "query": "Dubayga chipta qidirib, u yerdagi eng zo'r restoranlardan stol band qilib ber",
                "type": "complex",
                "expected_tool": "multi" # birdan ortiq tool chaqiruvi kutiladi
            }
        ]

        # Baholanadigan modellar
        models_to_test = [
            {
                "name": "Gemini 2.5 Flash (Asosiy)",
                "provider_class": GeminiProvider,
                "model_name": "gemini-2.5-flash",
                # Narxlar 1M token uchun ($)
                "input_cost": 0.075,
                "output_cost": 0.30
            },
            {
                "name": "Gemini 2.0 Flash-Lite (Tezkor/Arzon)",
                "provider_class": GeminiProvider,
                "model_name": "gemini-2.0-flash-lite-preview-02-05",
                "input_cost": 0.075,
                "output_cost": 0.30
            },
            {
                "name": "GPT-4o-Mini (OpenAI Zaxira)",
                "provider_class": OpenAIProvider,
                "model_name": "gpt-4o-mini",
                "input_cost": 0.15,
                "output_cost": 0.60
            }
        ]

        results = {}

        # Testlarni ishga tushirish
        for m in models_to_test:
            self.stdout.write(f"\nSinovdan o'tkazilmoqda: {m['name']}...")
            try:
                provider = m['provider_class'](model=m['model_name'])
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Provayderni yaratib bo'lmadi ({m['name']}): {e}"))
                continue

            results[m['name']] = []

            for q in queries:
                messages = [AIMessage(role='user', content=q['query'])]
                t0 = time.monotonic()
                
                try:
                    response = provider.chat(
                        messages=messages,
                        tools=tools,
                        system=system,
                        max_tokens=400
                    )
                    latency = int((time.monotonic() - t0) * 1000)
                    
                    # Tool calling to'g'riligini tekshirish
                    called_tools = [tc['name'] for tc in response.tool_calls]
                    tool_ok = False
                    
                    if q['expected_tool'] is None:
                        tool_ok = len(called_tools) == 0
                    elif q['expected_tool'] == "multi":
                        tool_ok = len(called_tools) > 1
                    else:
                        tool_ok = q['expected_tool'] in called_tools

                    # Narxni hisoblash
                    tokens = response.tokens_used or 0
                    # Taxminan input/output token split: 80% input, 20% output deb hisoblaymiz (aniq ma'lumot bo'lmaganda)
                    input_tokens = int(tokens * 0.8)
                    output_tokens = int(tokens * 0.2)
                    cost = (input_tokens * m['input_cost'] + output_tokens * m['output_cost']) / 1000000

                    results[m['name']].append({
                        "query": q['query'],
                        "latency": latency,
                        "tool_ok": tool_ok,
                        "called_tools": called_tools,
                        "tokens": tokens,
                        "cost": cost,
                        "success": True
                    })
                    self.stdout.write(f"  Query: '{q['query'][:30]}...' -> {latency}ms | Tools: {called_tools} | Status: {'OK' if tool_ok else 'WRONG_TOOL'}")

                except Exception as e:
                    latency = int((time.monotonic() - t0) * 1000)
                    results[m['name']].append({
                        "query": q['query'],
                        "latency": latency,
                        "tool_ok": False,
                        "called_tools": [],
                        "tokens": 0,
                        "cost": 0.0,
                        "success": False,
                        "error": str(e)
                    })
                    self.stdout.write(self.style.WARNING(f"  Query: '{q['query'][:30]}...' -> FAILED ({latency}ms): {e}"))

        # Natijalar hisoboti
        self.stdout.write("\n" + "━" * 80)
        self.stdout.write("                   MODEL BENCHMARK NATIJALARI HISOBOTI")
        self.stdout.write("━" * 80)

        for m_name, m_results in results.items():
            if not m_results:
                continue

            success_runs = [r for r in m_results if r['success']]
            total_runs = len(m_results)

            if not success_runs:
                self.stdout.write(f"\nModel: {m_name} -> Barcha so'rovlar muvaffaqiyatsiz tugadi!")
                continue

            latencies = [r['latency'] for r in success_runs]
            avg_latency = int(sum(latencies) / len(latencies))
            p50_lat = sorted(latencies)[int(len(latencies) * 0.5)]
            p90_lat = sorted(latencies)[int(len(latencies) * 0.9)] if len(latencies) > 1 else latencies[0]

            correct_tools = sum(1 for r in m_results if r['tool_ok'])
            tool_accuracy = (correct_tools / total_runs) * 100

            total_cost_1k = sum(r['cost'] for r in success_runs) * (1000 / len(success_runs))

            self.stdout.write(f"\nModel: {self.style.SUCCESS(m_name)}")
            self.stdout.write(f"  Muvaffaqiyatli so'rovlar : {len(success_runs)}/{total_runs}")
            self.stdout.write(f"  Tool-calling to'g'riligi : {tool_accuracy:.1f}%")
            self.stdout.write(f"  P50 Latency (Median)     : {p50_lat} ms")
            self.stdout.write(f"  P90 Latency              : {p90_lat} ms")
            self.stdout.write(f"  O'rtacha Latency         : {avg_latency} ms")
            self.stdout.write(f"  1000 ta so'rov narxi (est): ${total_cost_1k:.4f}")
            self.stdout.write("-" * 80)

        self.stdout.write("━" * 80)
        self.stdout.write(
            "Tavsiya:\n"
            "  1. Agar Gemini 2.0 Flash-Lite to'g'rilik foizi 90%+ bo'lsa va P50 past bo'lsa, "
            "sodda qidiruvlar uchun routing'da unga o'tish tavsiya etiladi.\n"
            "  2. GPT-4o-Mini to'g'riligi va barqarorligi yuqori bo'lgani sababli Gemini 503 xatolarida "
            "zaxira provayder sifatida ishlash uchun juda mos."
        )
        self.stdout.write("━" * 80)
