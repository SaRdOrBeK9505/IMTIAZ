"""
Payment providers registry.

Faol provayder: apps/payments/providers/alifpay.py → AlifPayProvider

StubPaymentProvider faqat unit testlar uchun — get_provider() ga kiritilmagan.
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
