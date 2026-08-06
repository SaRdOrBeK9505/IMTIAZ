"""
To'lov provayderlari uchun abstract interfeys.

Arxitektura qaror:
    To'lov provayder (Payme / Click / Multicard / boshqa) hali tanlanmagan.
    Shuning uchun bu qatlam to'liq abstraktsiya sifatida saqlanadi.
    Yangi provider qo'shish uchun:
        1. apps/payments/providers/<provider_name>.py yarating
        2. BasePaymentProvider'ni implement qiling
        3. PaymentProvider enum'ga nom qo'shing
        4. apps/payments/services.py → get_provider() ga ro'yxatga oling
    Boshqa hech narsa o'zgarmaydi.

TZ 3.5 bo'limiga mos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class PaymentIntent:
    """
    To'lov yaratish natijasi.
    payment_url — foydalanuvchi yo'naltiriladigan to'lov sahifasi (Payme checkout, Click va h.k.)
    """
    success: bool
    external_transaction_id: str | None = None
    payment_url: str | None = None
    error_message: str = ''
    raw: dict = field(default_factory=dict)


@dataclass
class PaymentCheckResult:
    """To'lov holatini tekshirish natijasi."""
    is_paid: bool
    is_failed: bool = False
    amount_paid: Decimal | None = None
    error_message: str = ''
    raw: dict = field(default_factory=dict)


@dataclass
class RefundResult:
    """Qaytarish natijasi."""
    success: bool
    refunded_amount: Decimal | None = None
    error_message: str = ''
    raw: dict = field(default_factory=dict)


class BasePaymentProvider(ABC):
    """
    Barcha to'lov provayderlari shu interfeysni implement qiladi.

    Majburiy metodlar:
        create_payment()  — to'lov sessiyasi ochish, redirect URL olish
        check_status()    — to'lov holatini provayder orqali tekshirish
        refund()          — to'lovni qaytarish (to'liq yoki qisman)
        get_provider_name() — enum qiymatiga mos nom (masalan 'payme')
    """

    @abstractmethod
    def create_payment(
        self,
        order_id: str,
        amount: Decimal,
        description: str,
        return_url: str | None = None,
        extra: dict | None = None,
    ) -> PaymentIntent:
        """
        To'lov sessiyasini yaratadi.

        Args:
            order_id:    Ichki Payment UUID (str)
            amount:      To'lov miqdori (UZS, Decimal)
            description: To'lov tavsifi
            return_url:  To'lovdan keyin qaytish URL (ixtiyoriy)
            extra:       Provaydarga xos qo'shimcha parametrlar (ixtiyoriy)

        Returns:
            PaymentIntent — payment_url yoki error_message bilan
        """
        ...

    @abstractmethod
    def check_status(self, external_transaction_id: str) -> PaymentCheckResult:
        """
        Tashqi provayder orqali to'lov holatini tekshiradi.
        Webhook ishlamagan yoki polling kerak bo'lganda chaqiriladi.
        """
        ...

    @abstractmethod
    def refund(
        self,
        external_transaction_id: str,
        amount: Decimal | None = None,
    ) -> RefundResult:
        """
        To'lovni qaytaradi.
        amount=None bo'lsa — to'liq qaytariladi.
        """
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """PaymentProvider enum qiymatini qaytaradi ('payme', 'click' va h.k.)"""
        ...
