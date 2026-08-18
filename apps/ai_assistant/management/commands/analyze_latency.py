import json
import os
import re
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = "AI latency (P50, P90, P99) percentile hisoboti va tahlili (logs/analyze.log faylidan o'qiydi)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help="Oxirgi N soat uchun loglarni tahlil qilish"
        )
        parser.add_argument(
            '--date',
            type=str,
            help="Muayyan kun uchun tahlil (YYYY-MM-DD formatida)"
        )
        parser.add_argument(
            '--log-file',
            type=str,
            help="Maxsus log fayl yo'li (agar ko'rsatilmasa logs/analyze.log ishlatiladi)"
        )

    def handle(self, *args, **options):
        log_file = options['log_file']
        if not log_file:
            log_file = os.path.join(settings.BASE_DIR, 'logs', 'analyze.log')

        if not os.path.exists(log_file):
            self.stdout.write(self.style.ERROR(f"Log fayli topilmadi: {log_file}"))
            return

        hours = options['hours']
        date_str = options['date']

        now = datetime.now()
        start_time = None
        target_date = None

        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                self.stdout.write(f"Tahlil qilinmoqda: {target_date} kuni")
            except ValueError:
                self.stdout.write(self.style.ERROR("Sana formati noto'g'ri. YYYY-MM-DD bo'lishi kerak."))
                return
        else:
            start_time = now - timedelta(hours=hours)
            self.stdout.write(f"Tahlil qilinmoqda: Oxirgi {hours} soat (boshlanish: {start_time.strftime('%Y-%m-%d %H:%M:%S')})")

        total_latencies = []
        provider_latencies = []
        tools_latencies = []
        errors_count = 0
        requests_count = 0
        slow_requests = []

        # JSON log qatorlarini o'qish
        # Har bir JSON formatter chiqishi: {"levelname": "INFO", "asctime": "2026-08-18 21:14:00,123", "name": "...", "message": "AI chat timing", "data": {...}}
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    log_data = json.loads(line)
                    # "AI chat timing" xabarini qidirish
                    msg = log_data.get('message', '')
                    if 'AI chat timing' not in msg:
                        continue

                    # Vaqtni tekshirish
                    # logging formatida asctime ko'pincha "2026-08-18 21:14:00,123" yoki ISO format
                    asctime = log_data.get('asctime', '')
                    if not asctime:
                        # Ba'zida timestamp boshqa nom bilan kelishi mumkin
                        continue

                    # asctime formatini tozalash (masalan, millisekund vergulini nuqtaga o'zgartirish)
                    clean_time_str = asctime.replace(',', '.')
                    try:
                        log_time = datetime.strptime(clean_time_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        try:
                            log_time = datetime.fromisoformat(clean_time_str)
                        except ValueError:
                            continue

                    if target_date:
                        if log_time.date() != target_date:
                            continue
                    elif start_time:
                        if log_time < start_time:
                            continue

                    requests_count += 1
                    data = log_data.get('data', {})
                    if not data:
                        continue

                    # Natijada xatolik bormi
                    ok = data.get('ok', True)
                    # Agar timer o'zi emas, log message orqali provider xatosi bo'lsa
                    if 'provider xatosi' in msg:
                        errors_count += 1
                        ok = False

                    total_ms = data.get('total_ms', 0)
                    total_latencies.append(total_ms)

                    steps = data.get('steps', [])
                    prov_ms = 0
                    tools_ms = 0

                    for step in steps:
                        step_name = step.get('step', '')
                        duration = step.get('duration_ms', 0)
                        if step_name == 'provider_call' or step_name == 'followup_provider_call':
                            prov_ms += duration
                        elif step_name == 'tools_total':
                            tools_ms += duration
                        elif step_name.startswith('tool:'):
                            # Agar alohida tool bo'lsa
                            pass

                        # Agar biron bir qadam xato bo'lsa, xatolar sonini oshiramiz (agar oldin oshirilmagan bo'lsa)
                        if not step.get('ok', True) and ok:
                            errors_count += 1
                            ok = False

                    if prov_ms > 0:
                        provider_latencies.append(prov_ms)
                    if tools_ms > 0:
                        tools_latencies.append(tools_ms)

                    # Eng sekin so'rovlar ro'yxati
                    slow_requests.append({
                        'request_id': data.get('request_id', '?'),
                        'total_ms': total_ms,
                        'prov_ms': prov_ms,
                        'tools_ms': tools_ms,
                        'time': asctime,
                        'ok': ok
                    })

                except Exception as e:
                    # JSON parse xatosi yoki boshqa kutilmagan holat
                    continue

        if requests_count == 0:
            self.stdout.write(self.style.WARNING("Belgilangan vaqt oralig'ida AI timing loglari topilmadi."))
            return

        # Percentile hisoblash helper
        def percentile(data_list, percent):
            if not data_list:
                return 0
            sorted_list = sorted(data_list)
            k = (len(sorted_list) - 1) * percent
            f = math_floor(k)
            c = math_ceil(k)
            if f == c:
                return sorted_list[int(k)]
            d0 = sorted_list[int(f)] * (c - k)
            d1 = sorted_list[int(c)] * (k - f)
            return int(d0 + d1)

        def math_floor(x):
            return int(x)

        def math_ceil(x):
            return int(x) + (1 if x > int(x) else 0)

        p50_total = percentile(total_latencies, 0.50)
        p90_total = percentile(total_latencies, 0.90)
        p99_total = percentile(total_latencies, 0.99)

        p50_prov = percentile(provider_latencies, 0.50)
        p90_prov = percentile(provider_latencies, 0.90)
        p99_prov = percentile(provider_latencies, 0.99)

        p50_tools = percentile(tools_latencies, 0.50)
        p90_tools = percentile(tools_latencies, 0.90)
        p99_tools = percentile(tools_latencies, 0.99)

        self.stdout.write("━" * 50)
        self.stdout.write(self.style.SUCCESS("           AI LATENCY PERCENTILE HISOBOTI"))
        self.stdout.write("━" * 50)
        self.stdout.write(f"Umumiy so'rovlar soni : {requests_count}")
        self.stdout.write(f"Muvaffaqiyatsiz       : {errors_count} ({errors_count/requests_count*100:.1f}%)")
        self.stdout.write("-" * 50)
        
        self.stdout.write("TOTAL Latency (ms):")
        self.stdout.write(f"  P50 (Median) : {p50_total:>6} ms")
        self.stdout.write(f"  P90          : {p90_total:>6} ms")
        self.stdout.write(f"  P99          : {p99_total:>6} ms")
        
        if provider_latencies:
            self.stdout.write("\nPROVIDER (LLM) Latency (ms):")
            self.stdout.write(f"  P50 (Median) : {p50_prov:>6} ms")
            self.stdout.write(f"  P90          : {p90_prov:>6} ms")
            self.stdout.write(f"  P99          : {p99_prov:>6} ms")

        if tools_latencies:
            self.stdout.write("\nTOOLS (Amallar) Latency (ms):")
            self.stdout.write(f"  P50 (Median) : {p50_tools:>6} ms")
            self.stdout.write(f"  P90          : {p90_tools:>6} ms")
            self.stdout.write(f"  P99          : {p99_tools:>6} ms")

        self.stdout.write("-" * 50)
        self.stdout.write("Eng sekin 5 ta so'rov:")
        slow_requests = sorted(slow_requests, key=lambda x: x['total_ms'], reverse=True)[:5]
        for idx, req in enumerate(slow_requests, 1):
            status = "OK" if req['ok'] else "ERROR"
            self.stdout.write(
                f"  {idx}. ID: {req['request_id']} | Total: {req['total_ms']}ms "
                f"(LLM: {req['prov_ms']}ms, Tools: {req['tools_ms']}ms) | Status: {status} | Vaqt: {req['time']}"
            )
        self.stdout.write("━" * 50)
