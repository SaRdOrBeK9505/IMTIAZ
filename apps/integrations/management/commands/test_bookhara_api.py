"""
Bookhara API v1.2.0 — to'liq endpoint test suite.

Manba: bookhara.docx (Bookhara avia API hujjati)
Smoke test (qisqa zanjir): test_bookhara_flow

Bu buyruq Bookhara REST API ning BARCHA hujjatlashtirilgan endpointlarini
bosqichma-bosqich sinaydi, natijalarni jadval shaklida chiqaradi va
ixtiyoriy JSON hisobot yozadi.

Qamrov (bookhara.docx):
  01. POST   /api/v1/accounts/tokens
  02. GET    /api/v1/accounts/check-balance
  03. GET    /api/v1/offers
  04. GET    /api/v1/offers/{id}/fare-family
  05. GET    /api/v1/offers/{id}
  06. GET    /api/v1/offers/{id}/rules
  07. POST   /api/v1/offers/{id}/booking
  08. GET    /api/v1/booking/{id}
  09. GET    /api/v1/booking/{id}/rules
  10. GET    /api/v1/booking/{id}/check-price
  11. GET    /api/v1/booking/{id}/payment-permission
  12. POST   /api/v1/booking/{id}/payment          (--with-payment)
  13. GET    /api/v1/booking/{id}/fiscalization      (--with-payment)
  14. GET    /api/v1/booking/{id}/pdf-receipt        (--with-payment)
  15. DELETE /api/v1/booking/{id}/cancel-unpaid
  16. DELETE /api/v1/booking/{id}/void               (--with-payment, ixtiyoriy)
  17. GET    /api/v1/booking/{id}/get-refund-amounts (--with-payment, ixtiyoriy)
  18. DELETE /api/v1/booking/{id}/auto-cancel         (--with-payment, ixtiyoriy)
  19. DELETE /api/v1/booking/{id}/manual-refund      (--with-payment, ixtiyoriy)
  20. GET    /api/v1/services/schedule
  21. GET    /api/v1/visa-types/v2
  22. GET    /api/v1/visa-types

Ishlatish — faqat qidiruv va xizmat endpointlari (bron yaratmasdan):
    python manage.py test_bookhara_api \\
        --origin TAS --destination IST --date 2026-09-15 --search-only

Ishlatish — to'liq zanjir (to'lovsiz, bron + cancel-unpaid):
    python manage.py test_bookhara_api \\
        --origin TAS --destination IST --date 2026-09-15 \\
        --passenger-json /path/to/passengers.json \\
        --payer-name "Ism Familiya" \\
        --payer-email "user@example.com" \\
        --payer-tel "+998901234567"

Ishlatish — to'lov bilan (production account + depozit talab qilinadi):
    python manage.py test_bookhara_api ... --with-payment

JSON hisobot:
    python manage.py test_bookhara_api ... --report-json /tmp/bookhara_report.json
"""

from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

import httpx
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError

from apps.integrations.adapters.bookhara import (
    BookharaAdapter,
    BookharaError,
)
from apps.integrations.adapters.bookhara_client import (
    TOKEN_CACHE_KEY,
    BookharaClient,
)
from apps.integrations.errors import IntegrationError, is_bookhara_configured

# ---------------------------------------------------------------------------
# Terminal ranglari
# ---------------------------------------------------------------------------

RESET = '\033[0m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
DIM = '\033[2m'


class TestStatus(str, Enum):
    PASS = 'PASS'
    FAIL = 'FAIL'
    SKIP = 'SKIP'
    WARN = 'WARN'


@dataclass
class EndpointSpec:
    """Bitta Bookhara endpoint spetsifikatsiyasi."""
    code: str
    method: str
    path: str
    title: str
    phase: str
    required: bool = True
    needs_offer: bool = False
    needs_booking: bool = False
    needs_payment: bool = False


@dataclass
class TestResult:
    spec: EndpointSpec
    status: TestStatus
    duration_ms: int = 0
    message: str = ''
    details: dict[str, Any] = field(default_factory=dict)
    error: str = ''


# bookhara.docx bo'yicha barcha endpointlar ro'yxati
ENDPOINTS: list[EndpointSpec] = [
    EndpointSpec('01', 'POST', '/api/v1/accounts/tokens', 'Token olish', 'auth'),
    EndpointSpec('02', 'GET', '/api/v1/accounts/check-balance', 'Balans', 'account'),
    EndpointSpec('03', 'GET', '/api/v1/offers', 'Parvoz qidiruv', 'search'),
    EndpointSpec('20', 'GET', '/api/v1/services/schedule', 'Parvoz jadvali', 'services'),
    EndpointSpec('21', 'GET', '/api/v1/visa-types/v2', 'Viza turlari v2', 'services', required=False),
    EndpointSpec('22', 'GET', '/api/v1/visa-types', 'Viza turlari v1', 'services', required=False),
    EndpointSpec('04', 'GET', '/api/v1/offers/{id}/fare-family', 'Tarif oilasi', 'offer', needs_offer=True),
    EndpointSpec('05', 'GET', '/api/v1/offers/{id}', 'Offer narx', 'offer', needs_offer=True),
    EndpointSpec('06', 'GET', '/api/v1/offers/{id}/rules', 'Offer qoidalari', 'offer', needs_offer=True),
    EndpointSpec('07', 'POST', '/api/v1/offers/{id}/booking', 'Bron yaratish', 'booking', needs_offer=True),
    EndpointSpec('08', 'GET', '/api/v1/booking/{id}', 'Bron ma\'lumoti', 'booking', needs_booking=True),
    EndpointSpec('09', 'GET', '/api/v1/booking/{id}/rules', 'Bron qoidalari', 'booking', needs_booking=True),
    EndpointSpec('10', 'GET', '/api/v1/booking/{id}/check-price', 'Narx tekshiruvi', 'booking', needs_booking=True),
    EndpointSpec('11', 'GET', '/api/v1/booking/{id}/payment-permission', 'To\'lov ruxsati', 'booking', needs_booking=True),
    EndpointSpec('12', 'POST', '/api/v1/booking/{id}/payment', 'To\'lov (pay)', 'payment', needs_booking=True, needs_payment=True),
    EndpointSpec('13', 'GET', '/api/v1/booking/{id}/fiscalization', 'Fiskalizatsiya', 'payment', needs_booking=True, needs_payment=True),
    EndpointSpec('14', 'GET', '/api/v1/booking/{id}/pdf-receipt', 'PDF kvitansiya', 'payment', needs_booking=True, needs_payment=True, required=False),
    EndpointSpec('17', 'GET', '/api/v1/booking/{id}/get-refund-amounts', 'Refund summasi', 'refund', needs_booking=True, needs_payment=True, required=False),
    EndpointSpec('15', 'DELETE', '/api/v1/booking/{id}/cancel-unpaid', 'To\'lanmagan cancel', 'cancel', needs_booking=True),
    EndpointSpec('16', 'DELETE', '/api/v1/booking/{id}/void', 'Void (to\'langan)', 'cancel', needs_booking=True, needs_payment=True, required=False),
    EndpointSpec('18', 'DELETE', '/api/v1/booking/{id}/auto-cancel', 'Auto-cancel', 'cancel', needs_booking=True, needs_payment=True, required=False),
    EndpointSpec('19', 'DELETE', '/api/v1/booking/{id}/manual-refund', 'Manual refund', 'cancel', needs_booking=True, needs_payment=True, required=False),
]


class BookharaApiTestSuite:
    """Bookhara API endpointlarini ketma-ket sinovdan o'tkazuvchi suite."""

    def __init__(self, stdout, opts: dict):
        self.stdout = stdout
        self.opts = opts
        self.client = BookharaClient()
        self.adapter = BookharaAdapter(client=self.client)
        self.results: list[TestResult] = []
        self.offer_id: str | None = None
        self.booking_id: str | None = None
        self.paid: bool = False
        self.passengers: list[dict] = []

    # ------------------------------------------------------------------
    # Yordamchi metodlar
    # ------------------------------------------------------------------

    def _line(self, text: str = ''):
        self.stdout.write(text)

    def _header(self, text: str):
        self._line(f"\n{BOLD}{CYAN}{'=' * 72}{RESET}")
        self._line(f"{BOLD}{CYAN}  {text}{RESET}")
        self._line(f"{BOLD}{CYAN}{'=' * 72}{RESET}")

    def _record(self, spec: EndpointSpec, status: TestStatus, message: str = '',
                details: dict | None = None, error: str = '', duration_ms: int = 0):
        result = TestResult(
            spec=spec,
            status=status,
            duration_ms=duration_ms,
            message=message,
            details=details or {},
            error=error,
        )
        self.results.append(result)
        icon = {
            TestStatus.PASS: f'{GREEN}PASS{RESET}',
            TestStatus.FAIL: f'{RED}FAIL{RESET}',
            TestStatus.SKIP: f'{DIM}SKIP{RESET}',
            TestStatus.WARN: f'{YELLOW}WARN{RESET}',
        }[status]
        self._line(
            f"  [{icon}] {spec.code} {spec.method:6} {spec.path}"
            f"  {DIM}({duration_ms}ms){RESET}"
        )
        if message:
            self._line(f"         {message}")
        if error:
            self._line(f"         {RED}{error}{RESET}")

    def _run(self, spec: EndpointSpec, func: Callable[[], str], details: dict | None = None) -> TestResult:
        start = time.monotonic()
        try:
            message = func()
            duration = int((time.monotonic() - start) * 1000)
            self._record(spec, TestStatus.PASS, message, details, duration_ms=duration)
        except SkipTest as exc:
            duration = int((time.monotonic() - start) * 1000)
            self._record(spec, TestStatus.SKIP, str(exc), duration_ms=duration)
        except WarnTest as exc:
            duration = int((time.monotonic() - start) * 1000)
            self._record(spec, TestStatus.WARN, str(exc), duration_ms=duration)
        except Exception as exc:
            duration = int((time.monotonic() - start) * 1000)
            err = f'{type(exc).__name__}: {exc}'
            self._record(spec, TestStatus.FAIL, '', error=err, duration_ms=duration)
        return self.results[-1]

    def _should_skip_spec(self, spec: EndpointSpec) -> str | None:
        if self.opts['search_only'] and spec.phase in ('booking', 'payment', 'cancel', 'refund'):
            return '--search-only: bron/to\'lov bosqichlari o\'tkazildi'
        if self.opts['search_only'] and spec.needs_offer:
            return '--search-only: offer endpoint o\'tkazildi'
        if spec.needs_offer and not self.offer_id:
            return 'offer_id yo\'q (qidiruv muvaffaqiyatsiz yoki o\'tkazilgan)'
        if spec.needs_booking and not self.booking_id:
            return 'booking_id yo\'q (bron yaratilmagan yoki muvaffaqiyatsiz)'
        if spec.needs_payment and not self.opts['with_payment']:
            return '--with-payment berilmagan (to\'lov endpointlari o\'tkazildi)'
        if spec.needs_payment and self.opts['with_payment'] and not self.paid and spec.code in ('16', '18', '19'):
            return 'bron to\'lanmagan — void/auto-cancel/manual-refund o\'tkazildi'
        if spec.needs_payment and self.opts['with_payment'] and self.paid and spec.code == '15':
            return 'bron to\'langan — cancel-unpaid o\'tkazildi'
        return None

    @staticmethod
    def _assert_bookhara_envelope(body: dict, *, expect_data: bool = True):
        if not isinstance(body, dict):
            raise AssertionError(f'Javob dict emas: {type(body).__name__}')
        if 'request_id' not in body:
            raise AssertionError('Javobda request_id yo\'q (API v1.2.0 envelope)')
        if expect_data and body.get('data') is None and 'error_code' not in body:
            raise AssertionError('Javobda data bloki yo\'q')

    @staticmethod
    def _unwrap(body: dict | list) -> dict | list:
        if isinstance(body, dict) and body.get('data') is not None:
            return body['data']
        return body

    def _load_passengers(self):
        path = self.opts['passenger_json']
        try:
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f'{path} topilmadi. Masalan: '
                f'--passenger-json /home/imtiaz/app/passengers.sample.json'
            ) from exc
        self.passengers = data if isinstance(data, list) else [data]

    # ------------------------------------------------------------------
    # Endpoint testlari
    # ------------------------------------------------------------------

    def test_tokens(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            cache.delete(TOKEN_CACHE_KEY)
            token1 = self.client._fetch_token()
            if not token1:
                raise AssertionError('Token bo\'sh qaytdi')
            token2 = self.client._get_token()
            if token2 != token1:
                raise AssertionError('Keshlangan token mos kelmadi')
            return f'token uzunligi={len(token1)}, kesh ishlayapti'

        self._run(spec, _exec)

    def test_check_balance(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            raw = self.client.get('/api/v1/accounts/check-balance')
            self._assert_bookhara_envelope(raw)
            adapter_balance = self.adapter.check_balance()
            inner = self._unwrap(raw)
            deposit = inner.get('deposit') if isinstance(inner, dict) else None
            msg = (
                f"deposit={adapter_balance.get('deposit')} "
                f"credit={adapter_balance.get('credit')} "
                f"{adapter_balance.get('currency')}"
            )
            if deposit is None and adapter_balance.get('deposit') is None:
                if not self.opts['with_payment']:
                    raise WarnTest(f'{msg} — test account (depozit yo\'q, normal)')
            return msg

        self._run(spec, _exec)

    def test_search(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            offers = self.adapter.search(
                origin=self.opts['origin'],
                destination=self.opts['destination'],
                departure_date=self.opts['date'],
                passengers=self.opts['adults'],
                seat_class=self.opts['seat_class'],
                return_date=self.opts['return_date'],
                children=self.opts['children'],
                infants=self.opts['infants'],
                infants_with_seat=self.opts['infants_with_seat'],
            )
            if not offers:
                raise AssertionError('Hech qanday offer topilmadi')
            self.offer_id = offers[0].offer_id
            return (
                f'{len(offers)} ta offer; birinchi: {offers[0].airline} '
                f'{offers[0].flight_number}, {offers[0].price} {offers[0].currency}'
            )

        self._run(spec, _exec)

    def test_schedule(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            rows = self.adapter.get_schedule(
                departure_from=self.opts['date'],
                departure_to=self.opts['date'],
                airport_from=self.opts['origin'],
                airport_to=self.opts['destination'],
            )
            return f'{len(rows)} ta jadval qatori'

        self._run(spec, _exec)

    def test_visa_types_v2(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            raw = self.client.get(
                '/api/v1/visa-types/v2',
                params={'countries[0]': 'UZ', 'countries[1]': 'TR'},
            )
            self._assert_bookhara_envelope(raw)
            data = self._unwrap(raw)
            count = len(data) if isinstance(data, list) else 1
            return f'{count} ta viza yozuvi (v2)'

        self._run(spec, _exec)

    def test_visa_types(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            raw = self.client.get(
                '/api/v1/visa-types',
                params={'countries[0]': 'UZ', 'countries[1]': 'TR'},
            )
            self._assert_bookhara_envelope(raw)
            data = self._unwrap(raw)
            count = len(data) if isinstance(data, list) else 1
            return f'{count} ta viza yozuvi (v1)'

        self._run(spec, _exec)

    def test_fare_family(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            items = self.adapter.get_fare_family(self.offer_id)
            return f'{len(items)} ta tarif varianti'

        self._run(spec, _exec)

    def test_get_offer(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            price = self.adapter.get_price(self.offer_id)
            return f'narx={price} UZS'

        self._run(spec, _exec)

    def test_offer_rules(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            rules = self.adapter.get_offer_rules(self.offer_id)
            if rules is None:
                raise WarnTest('Offer muddati tugagan (410) — qoidalar yo\'q')
            return f'{len(rules)} ta qoida qatori'

        self._run(spec, _exec)

    def test_create_booking(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)
        if not self.opts['passenger_json']:
            raise SkipTest('--passenger-json berilmagan')
        if not (self.opts['payer_name'] and self.opts['payer_email'] and self.opts['payer_tel']):
            raise SkipTest('payer ma\'lumotlari to\'liq emas')

        self._load_passengers()

        def _exec() -> str:
            result = self.adapter.create_booking(
                self.offer_id,
                self.passengers,
                payer_name=self.opts['payer_name'],
                payer_email=self.opts['payer_email'],
                payer_tel=self.opts['payer_tel'],
            )
            if not result.success:
                raise AssertionError(
                    f'[{result.error_code}] {result.error_message}'
                )
            self.booking_id = result.external_booking_id
            return f'booking_id={self.booking_id}, pnr={result.confirmation_code}'

        self._run(spec, _exec)

    def test_get_booking(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            data = self.adapter.get_booking(self.booking_id)
            status = data.get('status', '?')
            return f'status={status}'

        self._run(spec, _exec)

    def test_booking_rules(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            rules = self.adapter.get_booking_rules(self.booking_id)
            if rules is None:
                raise WarnTest('Bron qoidalari topilmadi (404/410)')
            return f'{len(rules)} ta qoida qatori'

        self._run(spec, _exec)

    def test_check_price(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            check = self.adapter.check_price(self.booking_id)
            changed = check.get('is_price_changed')
            return f"is_price_changed={changed}"

        self._run(spec, _exec)

    def test_payment_permission(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            allowed = self.adapter.check_payment_permission(self.booking_id)
            if not allowed and self.opts['with_payment']:
                raise AssertionError('payment_allowed=False — to\'lov mumkin emas')
            return f'payment_allowed={allowed}'

        self._run(spec, _exec)

    def test_payment(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)

        def _exec() -> str:
            balance = self.adapter.check_balance()
            deposit = balance.get('deposit')
            if deposit is None or Decimal(str(deposit or 0)) <= 0:
                raise SkipTest(
                    'Depozit yo\'q yoki nol — pay_booking sinab bo\'lmaydi '
                    '(production account kerak)'
                )
            pay_result = self.adapter.pay_booking(self.booking_id)
            self.paid = True
            status = pay_result.get('status', '?')
            fiscal = pay_result.get('fiscalization_v2') or {}
            return f'status={status}, fiscalization={"ha" if fiscal else "yo\'q"}'

        self._run(spec, _exec)

    def test_fiscalization(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)
        if not self.paid:
            raise SkipTest('pay_booking bajarilmagan')

        def _exec() -> str:
            data = self.adapter.get_fiscalization(self.booking_id)
            inner = self._unwrap(data) if isinstance(data, dict) else data
            fiscal = (inner.get('fiscalization_v2') if isinstance(inner, dict) else None) or {}
            return f'fiscalization_v2={"ha" if fiscal else "bo\'sh"}'

        self._run(spec, _exec)

    def test_pdf_receipt(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)
        if not self.paid:
            raise SkipTest('pay_booking bajarilmagan')

        def _exec() -> str:
            raw = self.client.get(f'/api/v1/booking/{self.booking_id}/pdf-receipt')
            self._assert_bookhara_envelope(raw)
            data = self._unwrap(raw)
            if not isinstance(data, list) or not data:
                raise WarnTest('PDF kvitansiya hali tayyor emas (ticketed kutish kerak bo\'lishi mumkin)')
            url = data[0].get('itinerary_receipt', '')
            return f'{len(data)} ta yo\'lovchi kvitansiyasi; url={"ha" if url else "yo\'q"}'

        self._run(spec, _exec)

    def test_refund_amounts(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)
        if not self.paid:
            raise SkipTest('pay_booking bajarilmagan')

        def _exec() -> str:
            info = self.adapter.get_refund_amounts(self.booking_id)
            if not info.get('refund_available'):
                raise WarnTest('Refund mavjud emas (5233 yoki tarif cheklovi)')
            return (
                f"refund={info.get('refund_amount')} "
                f"penalty={info.get('penalty')} {info.get('currency')}"
            )

        self._run(spec, _exec)

    def test_cancel_unpaid(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)
        if self.opts['no_cleanup']:
            raise SkipTest('--no-cleanup: cancel-unpaid o\'tkazildi')
        if self.paid:
            raise SkipTest('bron to\'langan — cancel-unpaid emas')

        def _exec() -> str:
            self.adapter.cancel_unpaid_booking(self.booking_id)
            self.booking_id = None
            return 'to\'lanmagan bron bekor qilindi'

        self._run(spec, _exec)

    def test_void(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)
        if not self.paid:
            raise SkipTest('bron to\'lanmagan')

        def _exec() -> str:
            self.adapter.void_booking(self.booking_id)
            return 'void muvaffaqiyatli'

        self._run(spec, _exec)

    def test_auto_cancel(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)
        if not self.paid:
            raise SkipTest('bron to\'lanmagan')
        if self.opts.get('skip_destructive'):
            raise SkipTest('--skip-destructive: auto-cancel o\'tkazildi')

        def _exec() -> str:
            self.adapter.auto_cancel_booking(self.booking_id)
            return 'auto-cancel muvaffaqiyatli'

        self._run(spec, _exec)

    def test_manual_refund(self, spec: EndpointSpec):
        skip = self._should_skip_spec(spec)
        if skip:
            raise SkipTest(skip)
        if not self.paid:
            raise SkipTest('bron to\'lanmagan')
        if self.opts.get('skip_destructive'):
            raise SkipTest('--skip-destructive: manual-refund o\'tkazildi')

        def _exec() -> str:
            self.adapter.request_manual_refund(self.booking_id)
            return 'manual-refund so\'rovi yuborildi'

        self._run(spec, _exec)

    # ------------------------------------------------------------------
    # Suite ishga tushirish
    # ------------------------------------------------------------------

    HANDLERS: dict[str, Callable] = {}

    def run_all(self):
        handlers = {
            '01': self.test_tokens,
            '02': self.test_check_balance,
            '03': self.test_search,
            '04': self.test_fare_family,
            '05': self.test_get_offer,
            '06': self.test_offer_rules,
            '07': self.test_create_booking,
            '08': self.test_get_booking,
            '09': self.test_booking_rules,
            '10': self.test_check_price,
            '11': self.test_payment_permission,
            '12': self.test_payment,
            '13': self.test_fiscalization,
            '14': self.test_pdf_receipt,
            '15': self.test_cancel_unpaid,
            '16': self.test_void,
            '17': self.test_refund_amounts,
            '18': self.test_auto_cancel,
            '19': self.test_manual_refund,
            '20': self.test_schedule,
            '21': self.test_visa_types_v2,
            '22': self.test_visa_types,
        }

        self._header('Bookhara API v1.2.0 — To\'liq Endpoint Test Suite')
        self._line(f"  Muhit: {self.client.base_url}")
        self._line(f"  Vaqt:  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        self._line(
            f"  Rejim: {'search-only' if self.opts['search_only'] else 'to\'liq'}"
            f"{' + to\'lov' if self.opts['with_payment'] else ''}"
        )

        current_phase = None
        for spec in ENDPOINTS:
            if spec.phase != current_phase:
                current_phase = spec.phase
                self._line(f"\n{BOLD}--- Faza: {current_phase.upper()} ---{RESET}")

            handler = handlers.get(spec.code)
            if not handler:
                self._record(spec, TestStatus.SKIP, 'Handler topilmadi')
                continue

            try:
                handler(spec)
            except SkipTest as exc:
                self._record(spec, TestStatus.SKIP, str(exc))
            except WarnTest as exc:
                self._record(spec, TestStatus.WARN, str(exc))
            except Exception:
                self._record(
                    spec, TestStatus.FAIL, error=traceback.format_exc().splitlines()[-1],
                )

            # Kritik xato — keyingi bosqichlar ma'nosi yo'qolishi mumkin
            last = self.results[-1]
            if last.status == TestStatus.FAIL and last.spec.required:
                if spec.code == '03':
                    self._line(f"\n{RED}Qidiruv muvaffaqiyatsiz — offer/booking testlari o\'tkaziladi.{RESET}")
                elif spec.code == '07':
                    self._line(f"\n{RED}Bron yaratilmadi — booking testlari o\'tkaziladi.{RESET}")

        self._print_summary()
        return self._exit_code()

    def _print_summary(self):
        passed = sum(1 for r in self.results if r.status == TestStatus.PASS)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAIL)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIP)
        warned = sum(1 for r in self.results if r.status == TestStatus.WARN)
        required_failed = [
            r for r in self.results
            if r.status == TestStatus.FAIL and r.spec.required
        ]

        self._header('YAKUNIY HISOBOT')
        self._line(f"  {GREEN}PASS{RESET}: {passed}  "
                   f"{RED}FAIL{RESET}: {failed}  "
                   f"{YELLOW}WARN{RESET}: {warned}  "
                   f"{DIM}SKIP{RESET}: {skipped}  "
                   f"JAMI: {len(self.results)}")

        if required_failed:
            self._line(f"\n  {RED}Majburiy endpoint xatolari:{RESET}")
            for r in required_failed:
                self._line(f"    - {r.spec.code} {r.spec.title}: {r.error or r.message}")

        if not self.opts['with_payment'] and not self.opts['search_only']:
            self._line(
                f"\n  {YELLOW}Eslatma:{RESET} to'lov endpointlari (--with-payment) "
                f"sinab ko'rilmadi. Production uchun alohida ishga tushiring."
            )

        overall = f"{GREEN}MUVAFFAQIYATLI{RESET}" if not required_failed else f"{RED}XATOLIK BOR{RESET}"
        self._line(f"\n  Natija: {overall}")

    def _exit_code(self) -> int:
        for r in self.results:
            if r.status == TestStatus.FAIL and r.spec.required:
                return 1
        return 0

    def export_json(self, path: str):
        payload = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'environment': self.client.base_url,
            'options': {
                k: v for k, v in self.opts.items()
                if k not in ('passenger_json',)
            },
            'offer_id': self.offer_id,
            'booking_id': self.booking_id,
            'paid': self.paid,
            'summary': {
                'pass': sum(1 for r in self.results if r.status == TestStatus.PASS),
                'fail': sum(1 for r in self.results if r.status == TestStatus.FAIL),
                'warn': sum(1 for r in self.results if r.status == TestStatus.WARN),
                'skip': sum(1 for r in self.results if r.status == TestStatus.SKIP),
            },
            'results': [
                {
                    'code': r.spec.code,
                    'method': r.spec.method,
                    'path': r.spec.path,
                    'title': r.spec.title,
                    'phase': r.spec.phase,
                    'required': r.spec.required,
                    'status': r.status.value,
                    'duration_ms': r.duration_ms,
                    'message': r.message,
                    'error': r.error,
                    'details': r.details,
                }
                for r in self.results
            ],
        }
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)


class SkipTest(Exception):
    """Test ataylab o'tkazib yuboriladi."""


class WarnTest(Exception):
    """Test ogohlantirish bilan o'tdi."""


class Command(BaseCommand):
    help = "Bookhara API v1.2.0 — barcha endpointlarni to'liq sinovdan o'tkazadi"

    def add_arguments(self, parser):
        parser.add_argument('--origin', default='TAS', help="Jo'nash aeroporti (IATA)")
        parser.add_argument('--destination', default='IST', help='Manzil aeroporti (IATA)')
        parser.add_argument('--date', required=True, help='Jo\'nash sanasi YYYY-MM-DD')
        parser.add_argument('--return-date', default=None, help='Qaytish sanasi (ixtiyoriy)')
        parser.add_argument('--adults', type=int, default=1)
        parser.add_argument('--children', type=int, default=0)
        parser.add_argument('--infants', type=int, default=0)
        parser.add_argument('--infants-with-seat', type=int, default=0)
        parser.add_argument('--seat-class', default='E', help='E=economy, B=business, A=any')
        parser.add_argument(
            '--passenger-json', default=None,
            help='Bron uchun yo\'lovchilar JSON (create-avia-booking formati)',
        )
        parser.add_argument('--payer-name', default=None)
        parser.add_argument('--payer-email', default=None)
        parser.add_argument('--payer-tel', default=None)
        parser.add_argument(
            '--search-only', action='store_true',
            help='Faqat auth, balans, qidiruv, schedule, visa endpointlari',
        )
        parser.add_argument(
            '--with-payment', action='store_true',
            help='pay_booking, fiscalization, pdf-receipt va refund endpointlarini ham sinash',
        )
        parser.add_argument(
            '--no-cleanup', action='store_true',
            help='Oxirida cancel-unpaid chaqirilmasin',
        )
        parser.add_argument(
            '--skip-destructive', action='store_true',
            help='void/auto-cancel/manual-refund kabi xavfli endpointlarni o\'tkazib yuborish',
        )
        parser.add_argument(
            '--report-json', default=None,
            help='Natijalarni JSON faylga yozish',
        )

    def handle(self, *args, **opts):
        if not is_bookhara_configured():
            raise CommandError(
                'BOOKHARA_EMAIL / BOOKHARA_PASSWORD .env da sozlanmagan.'
            )

        if not opts['passenger_json'] and not opts['search_only']:
            from django.conf import settings
            default = settings.BASE_DIR / 'passengers.sample.json'
            if default.is_file():
                opts['passenger_json'] = str(default)
                self.stdout.write(
                    f'  {DIM}passenger-json avtomatik: {default}{RESET}\n'
                )

        suite = BookharaApiTestSuite(self.stdout, opts)
        exit_code = suite.run_all()

        if opts['report_json']:
            suite.export_json(opts['report_json'])
            self.stdout.write(f"\n  JSON hisobot: {opts['report_json']}")

        if exit_code != 0:
            raise CommandError('Bookhara API test suite xato bilan tugadi.')
