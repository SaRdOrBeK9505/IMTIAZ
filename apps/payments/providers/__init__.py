"""
Payment providers registry.

Qo'shilgan provayderlar:
    stub     — development placeholder (haqiqiy API yo'q)

Kelajakda qo'shiladigan provayderlar (provider tanlanganida):
    payme    — apps/payments/providers/payme.py
    click    — apps/payments/providers/click.py
    multicard — apps/payments/providers/multicard.py
"""

from .base import BasePaymentProvider, PaymentIntent, PaymentCheckResult, RefundResult
from .stub import StubPaymentProvider

__all__ = [
    'BasePaymentProvider',
    'PaymentIntent',
    'PaymentCheckResult',
    'RefundResult',
    'StubPaymentProvider',
]
