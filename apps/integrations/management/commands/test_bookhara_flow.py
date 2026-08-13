"""
Bookhara integratsiyasini uchidan-uchigacha (to'lovsiz) sinovdan
o'tkazuvchi buyruq.

AlifPay hali tayyor emasligi sababli, `pay_booking()` chaqirilmaydi —
faqat shu bosqichgacha bo'lgan zanjir (qidiruv -> bron -> to'lovga
tayyorgarlik tekshiruvlari) ishga tushiriladi.

Ishlatish:
    python manage.py test_bookhara_flow \\
        --origin TAS --destination IST --date 2026-09-15 \\
        --passengers 1

Faqat qidiruvni sinash (bron yaratmasdan):
    python manage.py test_bookhara_flow --origin TAS --destination IST \\
        --date 2026-09-15 --search-only

Bron yaratilgandan keyin uni avtomatik bekor qilmaslik uchun:
    ... --no-cleanup
"""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
from django.core.management.base import BaseCommand, CommandError

from apps.integrations.adapters.bookhara import (
    BookharaAdapter,
    BookharaError,
)
from apps.integrations.errors import IntegrationError, is_bookhara_configured

RESET = '\033[0m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'


class Command(BaseCommand):
    help = "Bookhara avia integratsiyasini to'liq (to'lovsiz) sinovdan o'tkazadi"

    def add_arguments(self, parser):
        parser.add_argument('--origin', default='TAS', help="Jo'nash aeroporti (IATA), default: TAS")
        parser.add_argument('--destination', default='IST', help='Manzil aeroporti (IATA), default: IST')
        parser.add_argument('--date', required=True, help='Jonash sanasi YYYY-MM-DD')
        parser.add_argument('--return-date', default=None, help='Qaytish sanasi (ixtiyoriy, YYYY-MM-DD)')
        parser.add_argument('--adults', type=int, default=1, help="Kattalar soni, default: 1")
        parser.add_argument('--children', type=int, default=0, help="2-12 yosh bolalar soni, default: 0")
        parser.add_argument('--infants', type=int, default=0, help="0-2 yosh (joysiz) chaqaloqlar, default: 0")
        parser.add_argument('--infants-with-seat', type=int, default=0, help="0-2 yosh (joyli) chaqaloqlar, default: 0")
        parser.add_argument('--seat-class', default='E', help="Klass: E=economy, B=business, A=any. Default: E")
        parser.add_argument(
            '--passenger-json', default=None,
            help=(
                "Bron qilish uchun YO'LOVCHILAR ro'yxatini JSON fayldan o'qiydi "
                "(create-avia-booking.md formatiga mos: first_name, last_name, "
                "age, birthdate, gender, citizenship, tel, doc_type, doc_number, "
                "doc_expire). MAJBURIY — Bookhara qoidasiga ko'ra soxta "
                "(o'ylab topilgan) ma'lumot bilan bron qilish TAQIQLANGAN, shu "
                "sabab bu buyruq placeholder yo'lovchi bilan ISHLAMAYDI."
            ),
        )
        parser.add_argument('--payer-name', default=None, help="To'lovchi F.I.Sh. (majburiy, --search-only bo'lmasa)")
        parser.add_argument('--payer-email', default=None, help="To'lovchi email (majburiy, --search-only bo'lmasa)")
        parser.add_argument('--payer-tel', default=None, help="To'lovchi telefon +XXXXXXXXXXXX (majburiy, --search-only bo'lmasa)")
        parser.add_argument('--search-only', action='store_true', help='Faqat qidiruv qadamini bajaradi va to‘xtaydi')
        parser.add_argument(
            '--no-cleanup', action='store_true',
            help="Test oxirida yaratilgan to'lanmagan bronni bekor qilmaydi (cancel-unpaid chaqirilmaydi)",
        )

    # ------------------------------------------------------------------
    # Yordamchi chop etish metodlari
    # ------------------------------------------------------------------

    def _step(self, n: int, title: str):
        self.stdout.write(f"\n{BOLD}{CYAN}[{n}] {title}{RESET}")

    def _ok(self, msg: str):
        self.stdout.write(f"  {GREEN}OK{RESET}  {msg}")

    def _fail(self, msg: str):
        self.stdout.write(f"  {RED}FAIL{RESET}  {msg}")

    def _warn(self, msg: str):
        self.stdout.write(f"  {YELLOW}WARN{RESET}  {msg}")

    def _dump(self, obj):
        try:
            self.stdout.write('  ' + json.dumps(obj, indent=2, ensure_ascii=False, default=str)[:2000])
        except TypeError:
            self.stdout.write(f'  {obj!r}')

    # ------------------------------------------------------------------

    def handle(self, *args, **opts):
        if not is_bookhara_configured():
            raise CommandError(
                "BOOKHARA_EMAIL / BOOKHARA_PASSWORD .env faylida sozlanmagan. "
                "Avval shularni to'ldiring."
            )

        adapter = BookharaAdapter()
        booking_id = None
        offer_id = None

        try:
            # 1. Balans -------------------------------------------------
            self._step(1, 'Balansni tekshirish (check_balance)')
            try:
                balance = adapter.check_balance()
                self._ok(f"deposit={balance.get('deposit')} credit={balance.get('credit')} {balance.get('currency')}")
            except (BookharaError, IntegrationError, httpx.HTTPStatusError) as exc:
                self._warn(f"Balans olinmadi (davom etamiz): {exc}")

            # 2. Qidiruv --------------------------------------------------
            self._step(2, f"Parvozlarni qidirish ({opts['origin']} -> {opts['destination']}, {opts['date']})")
            offers = adapter.search(
                origin=opts['origin'],
                destination=opts['destination'],
                departure_date=opts['date'],
                passengers=opts['adults'],
                seat_class=opts['seat_class'],
                return_date=opts['return_date'],
                children=opts['children'],
                infants=opts['infants'],
                infants_with_seat=opts['infants_with_seat'],
            )
            if not offers:
                self._fail('Hech qanday taklif topilmadi. Sana/yo‘nalishni tekshiring.')
                return
            self._ok(f'{len(offers)} ta taklif topildi')
            best = offers[0]
            offer_id = best.offer_id
            self._dump({
                'offer_id': best.offer_id,
                'airline': best.airline,
                'flight_number': best.flight_number,
                'price': str(best.price),
                'currency': best.currency,
                'available_seats': best.available_seats,
            })

            if opts['search_only']:
                self.stdout.write(f"\n{BOLD}{GREEN}Faqat qidiruv rejimi — to'xtatildi.{RESET}")
                return

            if not opts['passenger_json']:
                raise CommandError(
                    "Bron yaratish uchun --passenger-json MAJBURIY (Bookhara "
                    "soxta yo'lovchi ma'lumoti bilan bron qilishni taqiqlaydi). "
                    "Faqat qidirishni sinash uchun --search-only bering."
                )
            if not (opts['payer_name'] and opts['payer_email'] and opts['payer_tel']):
                raise CommandError(
                    "--payer-name, --payer-email va --payer-tel MAJBURIY "
                    "(Bookhara create-avia-booking uchun talab qiladi)."
                )

            # 3. Fare family ----------------------------------------------
            self._step(3, 'Tarif oilasini olish (get_fare_family)')
            try:
                fare_families = adapter.get_fare_family(offer_id)
                self._ok(f'{len(fare_families)} ta tarif varianti')
            except (BookharaError, IntegrationError, httpx.HTTPStatusError) as exc:
                self._warn(f"Tarif oilasi olinmadi (davom etamiz): {exc}")

            # 4. Narxni tekshirish -----------------------------------------
            self._step(4, 'Offer narxini olish (get_price)')
            try:
                price = adapter.get_price(offer_id)
                self._ok(f'Narx: {price}')
            except (BookharaError, IntegrationError, httpx.HTTPStatusError) as exc:
                self._warn(f"Narx olinmadi (davom etamiz): {exc}")

            # 5. Offer qoidalari --------------------------------------------
            self._step(5, "Tarif shartlarini olish (get_offer_rules)")
            try:
                rules = adapter.get_offer_rules(offer_id)
                if rules is None:
                    self._warn('Offer muddati tugagan (410) — qoidalar mavjud emas')
                else:
                    self._ok(f'{len(rules)} ta shart qatori')
            except (BookharaError, IntegrationError, httpx.HTTPStatusError) as exc:
                self._warn(f"Qoidalar olinmadi (davom etamiz): {exc}")

            # 6. Bron yaratish -----------------------------------------------
            self._step(6, 'Bron yaratish (create_booking)')
            passengers = self._load_passengers(opts)
            result = adapter.create_booking(
                offer_id,
                passengers,
                payer_name=opts['payer_name'],
                payer_email=opts['payer_email'],
                payer_tel=opts['payer_tel'],
            )
            if not result.success:
                self._fail(f"Bron yaratilmadi: [{result.error_code}] {result.error_message}")
                self._dump(result.raw)
                return
            booking_id = result.external_booking_id
            self._ok(f'Bron yaratildi: id={booking_id} pnr={result.confirmation_code}')

            # 7. Bron ma'lumotini olish ---------------------------------------
            self._step(7, 'Bron ma\'lumotini olish (get_booking)')
            try:
                booking_data = adapter.get_booking(booking_id)
                self._ok(f"status={booking_data.get('status')}")
            except (BookharaError, IntegrationError, httpx.HTTPStatusError) as exc:
                self._warn(f"Bron ma'lumoti olinmadi: {exc}")

            # 8. Bron qoidalari ------------------------------------------------
            self._step(8, 'Bron qoidalarini olish (get_booking_rules)')
            try:
                booking_rules = adapter.get_booking_rules(booking_id)
                if booking_rules is None:
                    self._warn("Qoidalar topilmadi (404/410)")
                else:
                    self._ok(f'{len(booking_rules)} ta shart qatori')
            except (BookharaError, IntegrationError, httpx.HTTPStatusError) as exc:
                self._warn(f"Xato: {exc}")

            # 9. Narx o'zgarishini tekshirish ------------------------------------
            self._step(9, "To'lovdan oldin narxni tekshirish (check_price)")
            try:
                price_check = adapter.check_price(booking_id)
                if price_check['is_price_changed']:
                    self._warn(f"Narx o'zgargan! Yangi narx: {price_check['new_price']}")
                else:
                    self._ok("Narx o'zgarmagan")
            except (BookharaError, IntegrationError, httpx.HTTPStatusError) as exc:
                self._warn(f"Xato: {exc}")

            # 10. To'lov ruxsati ------------------------------------------------
            self._step(10, "To'lov ruxsatini tekshirish (check_payment_permission)")
            try:
                allowed = adapter.check_payment_permission(booking_id)
                if allowed:
                    self._ok("To'lovga ruxsat berilgan — AlifPay tayyor bo'lgach shu yerdan davom ettiriladi")
                else:
                    self._warn("To'lovga ruxsat berilmagan (payment_allowed=False)")
            except (BookharaError, IntegrationError, httpx.HTTPStatusError) as exc:
                self._warn(f"Xato: {exc}")

            self.stdout.write(
                f"\n{BOLD}{GREEN}To'lovgacha bo'lgan butun zanjir muvaffaqiyatli sinovdan o'tdi.{RESET}"
            )
            self.stdout.write(f"{YELLOW}pay_booking() chaqirilmadi — AlifPay hali ulanmagan.{RESET}")

        except (BookharaError, IntegrationError, httpx.HTTPStatusError) as exc:
            self._fail(f'Kutilmagan xato: {exc}')
            raise CommandError(str(exc)) from exc

        finally:
            # Tozalash: yaratilgan TO'LANMAGAN bronni bekor qilish.
            # DIQQAT: bu yerda cancel_unpaid_booking() (cancel-unpaid)
            # ishlatiladi, void_booking() EMAS — void faqat to'langan
            # (paid/ticketed) bronlar uchun, aks holda 404/410 qaytaradi.
            if booking_id and not opts['no_cleanup']:
                self._step(11, f"Tozalash: to'lanmagan bronni bekor qilish (cancel_unpaid_booking: {booking_id})")
                try:
                    adapter.cancel_unpaid_booking(booking_id)
                    self._ok('Bron bekor qilindi (cancel-unpaid)')
                except (BookharaError, IntegrationError, httpx.HTTPStatusError) as exc:
                    self._warn(f"Avtomatik bekor qilinmadi, qo'lda tekshiring (booking_id={booking_id}): {exc}")
            elif booking_id:
                self._warn(f"--no-cleanup berilgan: bron bekor qilinmadi (booking_id={booking_id})")

    # ------------------------------------------------------------------

    def _load_passengers(self, opts) -> list[dict]:
        """Yo'lovchi(lar) ro'yxatini JSON fayldan o'qiydi.

        Kutilgan format (bookhara wiki / create-avia-booking.md):
        [
          {
            "first_name": "Alla",
            "last_name": "Petrova",
            "middle_name": null,          // yo'q bo'lsa maydonni o'chiring
            "age": "adt",                  // adt|chd|inf|ins (directory.md)
            "birthdate": "1983-01-06",
            "gender": "F",                 // M|F
            "citizenship": "UZ",            // ISO 3166-1 alpha-2
            "tel": "+998901234567",
            "doc_type": "A",
            "doc_number": "AS76123646",
            "doc_expire": "2030-05-14"
          }
        ]

        MUHIM: qidiruvda ko'rsatilgan (adults/children/infants) yosh
        guruhlari va soni bron so'rovidagi passengers bilan ANIQ mos
        kelishi shart, aks holda Bookhara xato qaytaradi. Shuningdek,
        soxta (o'ylab topilgan) F.I.Sh./pasport ma'lumoti bilan bron
        qilish Bookhara qoidalariga ko'ra taqiqlangan va jarimaga
        sabab bo'lishi mumkin — shu sabab bu buyruq placeholder
        yo'lovchi generatsiya QILMAYDI.
        """
        with open(opts['passenger_json'], encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else [data]
