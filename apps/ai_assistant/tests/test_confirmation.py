"""
Confirmation Gate testlari.
Ishga tushirish: python manage.py test apps.ai_assistant.tests.test_confirmation
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from apps.ai_assistant.confirmation import (
    create_pending_action,
    confirm_pending_action,
    reject_pending_action,
    requires_confirmation,
    ConfirmationError,
    CONFIRMATION_TTL_MINUTES,
)
from apps.ai_assistant.models import AIActionLog


def make_user(**kwargs):
    """Test user yaratadi."""
    from apps.users.models import User
    defaults = {
        'telegram_id': 999_000_000 + User.objects.count(),
        'ai_autonomy_level': 'manual',
        'ai_auto_price_limit': Decimal('500000'),
    }
    defaults.update(kwargs)
    return User.objects.create(**defaults)


def make_session(user):
    from apps.ai_assistant.models import ConversationSession
    return ConversationSession.objects.create(user=user)


# ─── requires_confirmation ────────────────────────────────────────────────────

class RequiresConfirmationTests(TestCase):

    def test_manual_always_true(self):
        user = make_user(ai_autonomy_level='manual')
        self.assertTrue(requires_confirmation(user, 'book', Decimal('1000')))
        self.assertTrue(requires_confirmation(user, 'book', None))
        self.assertTrue(requires_confirmation(user, 'cancel', None))

    def test_semi_auto_small_amount_false(self):
        user = make_user(ai_autonomy_level='semi_auto')
        self.assertFalse(requires_confirmation(user, 'book', Decimal('100000')))

    def test_semi_auto_large_amount_true(self):
        user = make_user(ai_autonomy_level='semi_auto')
        self.assertTrue(requires_confirmation(user, 'book', Decimal('500000')))

    def test_semi_auto_cancel_always_true(self):
        user = make_user(ai_autonomy_level='semi_auto')
        self.assertTrue(requires_confirmation(user, 'cancel', None))

    def test_full_auto_within_limit_false(self):
        user = make_user(
            ai_autonomy_level='full_auto',
            ai_auto_price_limit=Decimal('1000000'),
        )
        self.assertFalse(requires_confirmation(user, 'book', Decimal('500000')))

    def test_full_auto_exceeds_limit_true(self):
        user = make_user(
            ai_autonomy_level='full_auto',
            ai_auto_price_limit=Decimal('500000'),
        )
        self.assertTrue(requires_confirmation(user, 'book', Decimal('600000')))


# ─── create_pending_action ────────────────────────────────────────────────────

class CreatePendingActionTests(TestCase):

    def setUp(self):
        self.user    = make_user()
        self.session = make_session(self.user)
        self.payload = {
            'offer_id': 'test-offer-001',
            'origin': 'TAS', 'destination': 'DXB',
            'departure_at': '2026-09-01T08:00:00',
            'passengers': 1,
        }

    def test_creates_aiactionlog_with_needs_confirmation(self):
        log = create_pending_action(
            user=self.user, session=self.session,
            action_type='book', service_type='flight',
            payload=self.payload, amount=Decimal('1500000'),
        )
        self.assertEqual(log.status, AIActionLog.ActionStatus.NEEDS_CONFIRMATION)
        self.assertEqual(log.action_type, 'book')
        self.assertEqual(log.service_type, 'flight')
        self.assertEqual(log.amount_requiring_confirmation, Decimal('1500000'))
        self.assertIsNotNone(log.expires_at)

    def test_no_booking_created(self):
        """Pending action yaratilganda Booking yaratilmaydi."""
        from apps.booking.models import Booking
        count_before = Booking.objects.count()

        create_pending_action(
            user=self.user, session=self.session,
            action_type='book', service_type='flight',
            payload=self.payload,
        )
        self.assertEqual(Booking.objects.count(), count_before)

    def test_expires_at_set_correctly(self):
        before = timezone.now()
        log    = create_pending_action(
            user=self.user, session=self.session,
            action_type='book', service_type='restaurant',
            payload={'branch_id': '1', 'date': '2026-09-01', 'time': '19:00', 'guests': 2},
        )
        after  = timezone.now()
        expected_min = before + timedelta(minutes=CONFIRMATION_TTL_MINUTES - 1)
        expected_max = after  + timedelta(minutes=CONFIRMATION_TTL_MINUTES + 1)
        self.assertGreater(log.expires_at, expected_min)
        self.assertLess(log.expires_at, expected_max)


# ─── confirm_pending_action ───────────────────────────────────────────────────

class ConfirmPendingActionTests(TestCase):

    def setUp(self):
        self.user    = make_user()
        self.session = make_session(self.user)
        self.payload = {
            'branch_id': 'branch-uuid',
            'date': '2026-09-01', 'time': '19:00', 'guests': 2,
        }

    def _make_log(self, **kwargs):
        defaults = dict(
            user=self.user, session=self.session,
            action_type='book', service_type='restaurant',
            payload=self.payload,
            status=AIActionLog.ActionStatus.NEEDS_CONFIRMATION,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        defaults.update(kwargs)
        return AIActionLog.objects.create(**defaults)

    def test_wrong_source_raises(self):
        log = self._make_log()
        with self.assertRaises(ConfirmationError) as ctx:
            confirm_pending_action(str(log.id), self.user, 'chat_message')
        self.assertIn('frontend tugmasi', str(ctx.exception))

    def test_wrong_user_raises(self):
        other_user = make_user(telegram_id=888000001)
        log = self._make_log()
        with self.assertRaises(ConfirmationError) as ctx:
            confirm_pending_action(str(log.id), other_user, 'frontend_button')
        self.assertIn('tegishli emas', str(ctx.exception))

    def test_already_confirmed_raises(self):
        log = self._make_log(status=AIActionLog.ActionStatus.SUCCESS)
        with self.assertRaises(ConfirmationError) as ctx:
            confirm_pending_action(str(log.id), self.user, 'frontend_button')
        self.assertIn('allaqachon', str(ctx.exception))

    def test_expired_raises_and_marks_failed(self):
        log = self._make_log(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        with self.assertRaises(ConfirmationError) as ctx:
            confirm_pending_action(str(log.id), self.user, 'frontend_button')
        self.assertIn('muddati', str(ctx.exception))
        log.refresh_from_db()
        self.assertEqual(log.status, AIActionLog.ActionStatus.FAILED)

    def test_double_confirm_raises(self):
        """Ikki marta tasdiqlashga urinish — ikkinchisi rad etiladi."""
        log = self._make_log()
        # Birinchi tasdiqlash muvaffaqiyatli bo'lishi uchun mock
        with patch(
            'apps.ai_assistant.confirmation._execute_confirmed_action',
            return_value={'status': 'ok', 'booking_id': 'test-id'},
        ):
            confirm_pending_action(str(log.id), self.user, 'frontend_button')

        # Ikkinchi urinish
        with self.assertRaises(ConfirmationError) as ctx:
            confirm_pending_action(str(log.id), self.user, 'frontend_button')
        self.assertIn('allaqachon', str(ctx.exception))

    def test_successful_confirm_sets_success_status(self):
        log = self._make_log()
        with patch(
            'apps.ai_assistant.confirmation._execute_confirmed_action',
            return_value={'status': 'ok', 'booking_id': 'new-booking-id'},
        ):
            result_log = confirm_pending_action(str(log.id), self.user, 'frontend_button')

        self.assertEqual(result_log.status, AIActionLog.ActionStatus.SUCCESS)
        self.assertIsNotNone(result_log.result)


# ─── reject_pending_action ────────────────────────────────────────────────────

class RejectPendingActionTests(TestCase):

    def setUp(self):
        self.user    = make_user()
        self.session = make_session(self.user)

    def test_reject_sets_cancelled_by_user(self):
        log = AIActionLog.objects.create(
            user=self.user, session=self.session,
            action_type='book', service_type='flight',
            payload={},
            status=AIActionLog.ActionStatus.NEEDS_CONFIRMATION,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        reject_pending_action(str(log.id), self.user)
        log.refresh_from_db()
        self.assertEqual(log.status, AIActionLog.ActionStatus.CANCELLED_BY_USER)

    def test_reject_wrong_user_raises(self):
        other = make_user(telegram_id=777000001)
        log   = AIActionLog.objects.create(
            user=self.user, session=self.session,
            action_type='book', service_type='flight',
            payload={},
            status=AIActionLog.ActionStatus.NEEDS_CONFIRMATION,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        with self.assertRaises(ConfirmationError):
            reject_pending_action(str(log.id), other)


# ─── To'liq oqim integratsion test ───────────────────────────────────────────

class FullFlowIntegrationTest(TestCase):
    """
    AI → qidiruv → book_flight → needs_confirmation →
    frontend confirm → Booking yaratiladi.
    """

    def setUp(self):
        self.user    = make_user(ai_autonomy_level='manual')
        self.session = make_session(self.user)

    @patch('apps.ai_assistant.services.AIAssistantService._load_history', return_value=[])
    @patch('apps.ai_assistant.services.get_ai_provider')
    def test_full_flow(self, mock_provider_factory, mock_history):
        from apps.ai_assistant.services import AIAssistantService
        from apps.booking.models import Booking

        # AI book_flight tool chaqiradi
        mock_provider = MagicMock()
        mock_provider.chat.return_value = MagicMock(
            content='Parvoz topildi, tasdiqlaymizmi?',
            tool_calls=[{
                'id':    'tool-call-001',
                'name':  'book_flight',
                'input': {
                    'offer_id':    'bookhara-offer-001',
                    'origin':      'TAS',
                    'destination': 'DXB',
                    'departure_at':'2026-09-01T08:00:00',
                    'passengers':  1,
                },
            }],
            tokens_used=100,
            raw=MagicMock(content=[]),
        )
        mock_provider_factory.return_value = mock_provider

        svc = AIAssistantService()

        # 1. Chat — book_flight so'rovi
        result = svc.chat(
            user=self.user,
            message='TASdan DXBga 1 kishi bron qil',
            session_id=str(self.session.id),
        )

        # 2. requires_confirmation=True, Booking yaratilmagan
        self.assertTrue(result['requires_confirmation'])
        self.assertIsNotNone(result['pending_action_id'])
        self.assertEqual(Booking.objects.count(), 0)

        # 3. AIActionLog status = needs_confirmation
        log = AIActionLog.objects.get(id=result['pending_action_id'])
        self.assertEqual(log.status, AIActionLog.ActionStatus.NEEDS_CONFIRMATION)
        self.assertEqual(log.payload['offer_id'], 'bookhara-offer-001')

        # 4. Frontend confirm → Booking yaratiladi
        with patch(
            'apps.ai_assistant.confirmation._create_flight_booking',
            return_value={'status': 'ok', 'booking_id': 'new-uuid'},
        ) as mock_create:
            confirmed_log = confirm_pending_action(
                action_log_id=result['pending_action_id'],
                user=self.user,
                confirmation_source='frontend_button',
            )

        # 5. Log status = success
        self.assertEqual(confirmed_log.status, AIActionLog.ActionStatus.SUCCESS)
        mock_create.assert_called_once()
