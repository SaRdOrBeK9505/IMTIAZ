"""
Parvoz bronlari uchun Bookhara settlement saga — holat mashinasi.

Oqim (AlifPay capture-only):
    PENDING → PRICE_LOCKED → PAYMENT_CAPTURED → BOOKHARA_SETTLING
        → BOOKHARA_CONFIRMED → COMPLETED

Xato:
    BOOKHARA_FAILED → REFUND_PENDING → REFUNDED
                                   ↘ FAILED (refund ham muvaffaqiyatsiz)
"""

from __future__ import annotations


class SettlementStatus:
    PENDING = 'pending'
    PRICE_LOCKED = 'price_locked'
    PAYMENT_CAPTURED = 'payment_captured'
    BOOKHARA_SETTLING = 'bookhara_settling'
    BOOKHARA_CONFIRMED = 'bookhara_confirmed'
    COMPLETED = 'completed'
    BOOKHARA_FAILED = 'bookhara_failed'
    REFUND_PENDING = 'refund_pending'
    REFUNDED = 'refunded'
    FAILED = 'failed'

    CHOICES = [
        (PENDING, 'Kutilmoqda'),
        (PRICE_LOCKED, 'Narx qulflangan (pre-flight OK)'),
        (PAYMENT_CAPTURED, 'Mijoz to\'lovi qabul qilindi'),
        (BOOKHARA_SETTLING, 'Bookhara settlement jarayonda'),
        (BOOKHARA_CONFIRMED, 'Bookhara tasdiqladi'),
        (COMPLETED, 'Yakunlandi'),
        (BOOKHARA_FAILED, 'Bookhara settlement xato'),
        (REFUND_PENDING, 'Qaytarish kutilmoqda'),
        (REFUNDED, 'Mijozga qaytarildi'),
        (FAILED, 'Amalga oshmadi'),
    ]


SETTLEMENT_TRANSITIONS: dict[str, list[str]] = {
    SettlementStatus.PENDING: [
        SettlementStatus.PRICE_LOCKED,
        SettlementStatus.PAYMENT_CAPTURED,
        SettlementStatus.FAILED,
    ],
    SettlementStatus.PRICE_LOCKED: [
        SettlementStatus.PAYMENT_CAPTURED,
        SettlementStatus.FAILED,
    ],
    SettlementStatus.PAYMENT_CAPTURED: [
        SettlementStatus.BOOKHARA_SETTLING,
        SettlementStatus.BOOKHARA_FAILED,
    ],
    SettlementStatus.BOOKHARA_SETTLING: [
        SettlementStatus.BOOKHARA_CONFIRMED,
        SettlementStatus.BOOKHARA_FAILED,
    ],
    SettlementStatus.BOOKHARA_CONFIRMED: [
        SettlementStatus.COMPLETED,
    ],
    SettlementStatus.BOOKHARA_FAILED: [
        SettlementStatus.REFUND_PENDING,
        SettlementStatus.BOOKHARA_SETTLING,
        SettlementStatus.FAILED,
    ],
    SettlementStatus.REFUND_PENDING: [
        SettlementStatus.REFUNDED,
        SettlementStatus.FAILED,
    ],
    SettlementStatus.COMPLETED: [],
    SettlementStatus.REFUNDED: [],
    SettlementStatus.FAILED: [],
}


class TransactionStep:
    """BookingTransactionLog bosqich nomlari."""

    PRE_FLIGHT_START = 'pre_flight_start'
    PRE_FLIGHT_OK = 'pre_flight_ok'
    PRE_FLIGHT_FAILED = 'pre_flight_failed'
    PAYMENT_INITIATED = 'payment_initiated'
    PAYMENT_CAPTURED = 'payment_captured'
    BOOKHARA_SETTLE_START = 'bookhara_settle_start'
    BOOKHARA_SETTLE_OK = 'bookhara_settle_ok'
    BOOKHARA_SETTLE_FAILED = 'bookhara_settle_failed'
    BOOKHARA_CANCEL_HOLD = 'bookhara_cancel_hold'
    REFUND_START = 'refund_start'
    REFUND_OK = 'refund_ok'
    REFUND_FAILED = 'refund_failed'
    DEPOSIT_CHECK = 'deposit_check'

    CHOICES = [
        (PRE_FLIGHT_START, 'Pre-flight boshlandi'),
        (PRE_FLIGHT_OK, 'Pre-flight muvaffaqiyatli'),
        (PRE_FLIGHT_FAILED, 'Pre-flight rad etildi'),
        (PAYMENT_INITIATED, 'To\'lov boshlandi'),
        (PAYMENT_CAPTURED, 'To\'lov qabul qilindi'),
        (BOOKHARA_SETTLE_START, 'Bookhara settlement boshlandi'),
        (BOOKHARA_SETTLE_OK, 'Bookhara settlement OK'),
        (BOOKHARA_SETTLE_FAILED, 'Bookhara settlement xato'),
        (BOOKHARA_CANCEL_HOLD, 'Bookhara hold bekor qilindi'),
        (REFUND_START, 'Qaytarish boshlandi'),
        (REFUND_OK, 'Qaytarish muvaffaqiyatli'),
        (REFUND_FAILED, 'Qaytarish xato'),
        (DEPOSIT_CHECK, 'Depozit balans tekshiruvi'),
    ]


def can_transition(current: str, new: str) -> bool:
    return new in SETTLEMENT_TRANSITIONS.get(current, [])
