"""
Payments app — To'lov tizimi modellari.

Arxitektura:
    - PaymentProvider: qaysi provayder ishlatilishi hali tanlanmagan.
      Enum qiymatlari future-proof tarzda saqlanadi.
      Hozir barcha provayderlar StubPaymentProvider bilan ishlaydi.
    - PAYMENT_STATUS_TRANSITIONS: state machine — noto'g'ri o'tishlar
      Payment.transition_to() da exception bilan bloklangan.
    - commission_amount / commission_percent: platforma komissiyasi uchun
      tayyor maydonlar (to'lov oqimi aniqlanganida doldiriladi).

TZ 3.5 bo'limiga mos.
"""

from __future__ import annotations

from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class PaymentProvider(models.TextChoices):
    """
    Qo'llab-quvvatlanadigan to'lov provayderlari.
    Hozir tanlanmagan — barcha variantlar saqlanadi.
    """
    PAYME      = 'payme',      'Payme'
    CLICK      = 'click',      'Click'
    MULTICARD  = 'multicard',  'Multicard'
    WALLET     = 'wallet',     'IMTIAZ Hamyon'
    ALIFPAY    = 'alifpay',   'AlifPay'
    # Kelajak uchun joy qoldirilgan:
    # STRIPE   = 'stripe',   'Stripe'
    # UZCARD   = 'uzcard',   'Uzcard'


class PaymentStatus(models.TextChoices):
    PENDING             = 'pending',             'Kutilmoqda'
    PROCESSING          = 'processing',          'Jarayonda'
    SUCCESS             = 'success',             'Muvaffaqiyatli'
    FAILED              = 'failed',              'Amalga oshmadi'
    REFUNDED            = 'refunded',            'Qaytarilgan'
    PARTIALLY_REFUNDED  = 'partially_refunded',  'Qisman qaytarilgan'
    CANCELLED           = 'cancelled',           'Bekor qilingan'


# ─── State machine ────────────────────────────────────────────────────────────
# Faqat shu transition'lar ruxsat etilgan.
# Boshqa o'tish Payment.transition_to() da ValueError chiqaradi.

PAYMENT_STATUS_TRANSITIONS: dict[str, list[str]] = {
    PaymentStatus.PENDING:            [PaymentStatus.PROCESSING, PaymentStatus.CANCELLED],
    PaymentStatus.PROCESSING:         [PaymentStatus.SUCCESS, PaymentStatus.FAILED],
    PaymentStatus.SUCCESS:            [PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED],
    PaymentStatus.FAILED:             [PaymentStatus.PENDING, PaymentStatus.SUCCESS],
    PaymentStatus.REFUNDED:           [],
    PaymentStatus.PARTIALLY_REFUNDED: [PaymentStatus.REFUNDED],
    PaymentStatus.CANCELLED:          [],
}


class Payment(BaseModel):
    """
    Yagona to'lov yozuvi.
    Har bir booking yoki subscription to'lovi shu model orqali o'tadi.
    """
    # Nima uchun to'lov (booking yoki obuna)
    booking = models.ForeignKey(
        'booking.Booking',
        on_delete=models.CASCADE,
        related_name='payments',
        null=True, blank=True,
    )
    subscription = models.ForeignKey(
        'membership.Subscription',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='payments',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments',
    )

    # To'lov ma'lumotlari
    provider = models.CharField(
        max_length=20,
        choices=PaymentProvider.choices,
        help_text='To\'lov provayderi — hali tanlanmagan, stub bilan ishlaydi',
    )
    status = models.CharField(
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    amount   = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='UZS')

    # Komissiya (to'lov oqimi aniqlanganida to'ldiriladi)
    commission_amount  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    commission_percent = models.DecimalField(max_digits=5,  decimal_places=2, default=0)

    # Tashqi provayder ma'lumotlari
    external_transaction_id = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    external_order_id       = models.CharField(max_length=128, blank=True, null=True)
    provider_response       = models.JSONField(null=True, blank=True)

    # Qaytarish
    refunded_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    refund_reason   = models.TextField(blank=True)

    error_message = models.TextField(blank=True)

    class Meta:
        verbose_name        = "To'lov"
        verbose_name_plural = "To'lovlar"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['provider', 'status']),
        ]

    def __str__(self) -> str:
        return (
            f'{self.user} | {self.provider} | '
            f'{self.amount} {self.currency} [{self.status}]'
        )

    def transition_to(self, new_status: str) -> None:
        """
        State machine: faqat ruxsat etilgan o'tishga yo'l qo'yadi.
        Raises:
            ValueError — agar o'tish ruxsat etilmagan bo'lsa
        """
        allowed = PAYMENT_STATUS_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"To'lov holati '{self.status}' dan '{new_status}' ga o'tish "
                f"ruxsat etilmagan. Ruxsat etilganlar: {allowed}"
            )
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])


class PaymentLog(BaseModel):
    """
    To'lov holati o'zgarishlari audit log'i.
    Har bir transition yozib boriladi.
    """
    payment     = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='logs')
    from_status = models.CharField(max_length=30, blank=True)
    to_status   = models.CharField(max_length=30)
    note        = models.TextField(blank=True)
    metadata    = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name        = "To'lov logi"
        verbose_name_plural = "To'lov loglari"
        ordering = ['created_at']

    def __str__(self) -> str:
        return f'{self.payment_id} | {self.from_status} → {self.to_status}'
