"""
AI Assistant app — chat sessiyalari va to'liq audit log.
Provider Abstraction pattern: biznes logika provayderdan mustaqil.
TZ 3.2 bo'limiga mos.
"""

from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class ConversationSession(BaseModel):
    """
    Foydalanuvchi bilan AI o'rtasidagi suhbat sessiyasi.
    Har bir sessiya mustaqil kontekstga ega.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversation_sessions'
    )
    title = models.CharField(max_length=255, blank=True, help_text='Avto-yaratilgan sarlavha')
    is_active = models.BooleanField(default=True)
    context_summary = models.TextField(
        blank=True,
        help_text='Uzoq sessiyalar uchun kontekst qisqartmasi'
    )

    class Meta:
        verbose_name = 'Suhbat sessiyasi'
        verbose_name_plural = 'Suhbat sessiyalari'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.user} — {self.title or self.id}'


class ConversationMessage(BaseModel):
    """Sessiya ichidagi har bir xabar."""

    class Role(models.TextChoices):
        USER = 'user', 'Foydalanuvchi'
        ASSISTANT = 'assistant', 'AI'
        SYSTEM = 'system', 'Tizim'

    session = models.ForeignKey(
        ConversationSession,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    # Tool-calling metadata
    tool_calls = models.JSONField(null=True, blank=True, help_text='Claude tool_use bloklari')
    tool_results = models.JSONField(null=True, blank=True, help_text='Tool natijalar')
    tokens_used = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Xabar'
        verbose_name_plural = 'Xabarlar'
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.role}] {self.content[:60]}'


class UserAIProfile(BaseModel):
    """Foydalanuvchiga xos doimiy AI xotira profili."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_profile',
    )
    preferred_seat_class = models.CharField(max_length=20, blank=True)
    preferred_cuisine = models.CharField(max_length=100, blank=True)
    frequent_destinations = models.JSONField(default=list, blank=True)
    summary_text = models.TextField(
        blank=True,
        help_text="AI tomonidan yozilgan qisqa xulosa (session'larni chetlab, doimiy profil)",
    )

    class Meta:
        verbose_name = 'AI foydalanuvchi profili'
        verbose_name_plural = 'AI foydalanuvchi profillari'

    def __str__(self):
        return f'{self.user} — AI profile'


class AIActionLog(BaseModel):
    """
    AI tomonidan bajarilgan har bir harakat qayd etiladi.
    Moliyaviy nizolar va xavfsizlik tekshiruvi uchun asosiy manba.
    TZ 3.2 — Audit bo'limi.
    """

    class ActionType(models.TextChoices):
        SEARCH = 'search', 'Qidiruv'
        RECOMMEND = 'recommend', 'Tavsiya'
        BOOK = 'book', 'Bron qilish'
        CANCEL = 'cancel', 'Bekor qilish'
        PAYMENT_CONFIRM = 'payment_confirm', 'To\'lovni tasdiqlash'
        PAYMENT_INITIATE = 'payment_initiate', 'To\'lovni boshlash'
        INFO_REQUEST = 'info_request', 'Ma\'lumot so\'rash'

    class ActionStatus(models.TextChoices):
        SUCCESS = 'success', 'Muvaffaqiyatli'
        FAILED = 'failed', 'Amalga oshmadi'
        NEEDS_CONFIRMATION = 'needs_confirmation', 'Tasdiqlash kerak'
        CANCELLED_BY_USER = 'cancelled_by_user', 'Foydalanuvchi bekor qildi'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_action_logs'
    )
    session = models.ForeignKey(
        ConversationSession,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='action_logs'
    )
    action_type = models.CharField(max_length=30, choices=ActionType.choices)
    service_type = models.CharField(max_length=20, blank=True, null=True)
    # So'rov parametrlari (qidiruv so'rovi, bron ma'lumotlari va h.k.)
    payload = models.JSONField(default=dict)
    # Natija (tashqi API javobi, yaratilgan booking ID va h.k.)
    result = models.JSONField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=ActionStatus.choices,
        default=ActionStatus.SUCCESS
    )
    error_message = models.TextField(blank=True)
    # Narx tasdiqlash kerak bo'lgan holatda
    amount_requiring_confirmation = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    # needs_confirmation holati uchun muddati — 5 daqiqa
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text='needs_confirmation holati uchun muddat (5 daqiqa)'
    )

    class Meta:
        verbose_name = 'AI harakat logi'
        verbose_name_plural = 'AI harakat loglari'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'action_type', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'{self.user} | {self.action_type} | {self.status} | {self.created_at}'