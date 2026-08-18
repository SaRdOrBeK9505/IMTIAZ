import json
import os
import tempfile
from django.core.management import call_command
from django.test import TestCase
from io import StringIO

class AnalyzeLatencyCommandTests(TestCase):

    def setUp(self):
        # Vaqtinchalik log fayl yaratamiz
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_path = os.path.join(self.temp_dir.name, 'analyze.log')

        # Test log yozuvlari
        self.log_entries = [
            # 1-so'rov: muvaffaqiyatli
            {
                "asctime": "2026-08-18 21:14:00,123",
                "message": "AI chat timing",
                "data": {
                    "request_id": "abc1",
                    "total_ms": 1200,
                    "ok": True,
                    "steps": [
                        {"step": "provider_call", "duration_ms": 1000, "ok": True},
                        {"step": "tools_total", "duration_ms": 150, "ok": True}
                    ]
                }
            },
            # 2-so'rov: muvaffaqiyatli, sekinroq
            {
                "asctime": "2026-08-18 21:14:05,456",
                "message": "AI chat timing",
                "data": {
                    "request_id": "abc2",
                    "total_ms": 2500,
                    "ok": True,
                    "steps": [
                        {"step": "provider_call", "duration_ms": 2000, "ok": True},
                        {"step": "tools_total", "duration_ms": 400, "ok": True}
                    ]
                }
            },
            # 3-so'rov: xatolik bilan tugagan
            {
                "asctime": "2026-08-18 21:14:10,789",
                "message": "AI chat timing (provider xatosi)",
                "data": {
                    "request_id": "abc3",
                    "total_ms": 500,
                    "ok": False,
                    "steps": [
                        {"step": "provider_call", "duration_ms": 500, "ok": False}
                    ]
                }
            }
        ]

        with open(self.log_path, 'w', encoding='utf-8') as f:
            for entry in self.log_entries:
                f.write(json.dumps(entry) + '\n')

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_analyze_latency_command_runs_successfully(self):
        out = StringIO()
        # Management commandni ishga tushiramiz
        call_command(
            'analyze_latency',
            log_file=self.log_path,
            hours=24,
            stdout=out
        )
        
        output_str = out.getvalue()
        
        # Chiqishda kerakli ma'lumotlar borligini tekshiramiz
        self.assertIn("AI LATENCY PERCENTILE HISOBOTI", output_str)
        self.assertIn("Umumiy so'rovlar soni : 3", output_str)
        self.assertIn("Muvaffaqiyatsiz       : 1 (33.3%)", output_str)
        self.assertIn("TOTAL Latency (ms):", output_str)
        
        # Percentile qiymatlarimiz to'g'ri hisoblanganini tekshiramiz (P50 total 1200 va 2500 va 500 dan)
        # 500, 1200, 2500 -> sorted: [500, 1200, 2500]
        # P50 -> 1200
        # P90 -> 2500
        # P99 -> 2500
        self.assertIn("P50 (Median) :   1200 ms", output_str)
        self.assertIn("P90          :   2240 ms", output_str)
        self.assertIn("P99          :   2474 ms", output_str)
        
        # Eng sekin so'rovlar ro'yxatini tekshirish
        self.assertIn("abc2", output_str)
        self.assertIn("abc1", output_str)
        self.assertIn("abc3", output_str)

    def test_analyze_latency_no_logs_found(self):
        # Bo'sh log fayl bilan sinaymiz
        empty_log_path = os.path.join(self.temp_dir.name, 'empty.log')
        with open(empty_log_path, 'w', encoding='utf-8') as f:
            pass

        out = StringIO()
        call_command(
            'analyze_latency',
            log_file=empty_log_path,
            hours=24,
            stdout=out
        )
        
        output_str = out.getvalue()
        self.assertIn("AI timing loglari topilmadi", output_str)
