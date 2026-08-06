"""
StubPaymentProvider — haqiqiy provayder tanlanmaguncha ishlatiladigan placeholder.

Development va test muhitida to'lov oqimini sinash imkonini beradi:
    - create_payment()  → har doim success=True, mock URL qaytaradi
    - check_status()    → har doim is_paid=True qaytaradi
    - refund()          → har doim success=True qaytaradi

DIQQAT: Bu provider faqat DEBUG=True muhitida ro'yxatga olingan.
        Production'da haqiqiy provider bilan almashtirilishi shart.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from .base import BasePaymentProvider, PaymentIntent, PaymentCheckResult, RefundResult

logger = logging.getLogger(__name__)


class StubPaymentProvider(BasePaymentProvider):
    """
    Mock payment provider — real provider tanlanmaguncha.
    Haqiqiy API chaqiruvi yo'q.
    """

    def get_provider_name(self) -> str:
        return 'stub'

    def create_payment(
        self,
        order_id: str,
        amount: Decimal,
        description: str,
        return_url: str | None = None,
        extra: dict | None = None,
    ) -> PaymentIntent:
        logger.warning(
            '[StubProvider] create_payment chaqirildi — haqiqiy provayder sozlanmagan. '
            'order_id=%s, amount=%s', order_id, amount
        )
        return PaymentIntent(
            success=True,
            external_transaction_id=f'stub-{order_id}',
            payment_url=f'https://stub-pay.local/pay?order={order_id}&amount={amount}',
        )

    def check_status(self, external_transaction_id: str) -> PaymentCheckResult:
        logger.warning(
            '[StubProvider] check_status chaqirildi. txn_id=%s', external_transaction_id
        )
        return PaymentCheckResult(is_paid=True)

    def refund(
        self,
        external_transaction_id: str,
        amount: Decimal | None = None,
    ) -> RefundResult:
        logger.warning(
            '[StubProvider] refund chaqirildi. txn_id=%s, amount=%s',
            external_transaction_id, amount
        )
        return RefundResult(success=True, refunded_amount=amount)
