"""Booking settlement saga testlari."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.booking.models import Booking, BookingSettlement, BookingStatus, ServiceType
from apps.booking.settlement import SettlementStatus, TransactionStep
from apps.payments.models import Payment, PaymentStatus, PaymentProvider
from apps.payments.settlement_service import FlightSettlementService, PreflightResult
from apps.users.models import User


def _make_user(phone='+998901234500'):
    user = User.objects.create(phone=phone, role='customer', is_phone_verified=True)
    user.set_password('Test1234!')
    user.save()
    return user


def _make_flight_booking(user, external_id='bh-123'):
    booking = Booking.objects.create(
        user=user,
        service_type=ServiceType.FLIGHT,
        status=BookingStatus.PENDING,
        title='TAS→DXB',
        final_price=Decimal('1500000'),
        external_booking_id=external_id,
        external_provider='bookhara',
    )
    return booking


class SettlementStateMachineTests(TestCase):
    def test_settlement_transitions(self):
        user = _make_user()
        booking = _make_flight_booking(user)
        settlement = BookingSettlement.objects.create(
            booking=booking,
            idempotency_key='test-key-1',
        )
        self.assertEqual(settlement.status, SettlementStatus.PENDING)

        settlement.transition_to(SettlementStatus.PRICE_LOCKED)
        settlement.transition_to(SettlementStatus.PAYMENT_CAPTURED)
        settlement.transition_to(SettlementStatus.BOOKHARA_SETTLING)
        settlement.transition_to(SettlementStatus.BOOKHARA_CONFIRMED)
        settlement.transition_to(SettlementStatus.COMPLETED)

        self.assertEqual(settlement.status, SettlementStatus.COMPLETED)

    def test_invalid_transition_raises(self):
        user = _make_user('+998901234501')
        booking = _make_flight_booking(user, 'bh-124')
        settlement = BookingSettlement.objects.create(
            booking=booking,
            idempotency_key='test-key-2',
        )
        with self.assertRaises(ValueError):
            settlement.transition_to(SettlementStatus.COMPLETED)


class PreflightTests(TestCase):
    @patch('apps.payments.settlement_service.is_bookhara_configured', return_value=False)
    def test_preflight_not_configured(self, _mock):
        user = _make_user('+998901234502')
        booking = _make_flight_booking(user, 'bh-125')
        result = FlightSettlementService.run_preflight(booking)
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, 'not_configured')

    @patch('apps.payments.settlement_service.is_bookhara_configured', return_value=True)
    def test_preflight_no_hold(self, _mock):
        user = _make_user('+998901234503')
        booking = _make_flight_booking(user, external_id='')
        booking.external_booking_id = ''
        booking.save()
        result = FlightSettlementService.run_preflight(booking)
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, 'no_hold')

    @patch('apps.payments.settlement_service.BookharaAdapter')
    @patch('apps.payments.settlement_service.is_bookhara_configured', return_value=True)
    def test_preflight_success(self, _mock_cfg, mock_adapter_cls):
        adapter = MagicMock()
        mock_adapter_cls.return_value = adapter
        adapter.check_payment_permission.return_value = True
        adapter.check_price.return_value = {
            'is_price_changed': False,
            'new_price': Decimal('1500000'),
        }
        adapter.check_balance.return_value = {'deposit': 10_000_000, 'credit': 0}

        user = _make_user('+998901234504')
        booking = _make_flight_booking(user, 'bh-126')
        result = FlightSettlementService.run_preflight(booking)

        self.assertTrue(result.ok)
        settlement = BookingSettlement.objects.get(booking=booking)
        self.assertEqual(settlement.status, SettlementStatus.PRICE_LOCKED)
        self.assertTrue(
            settlement.transaction_logs.filter(step=TransactionStep.PRE_FLIGHT_OK).exists()
        )

    @patch('apps.payments.settlement_service.BookharaAdapter')
    @patch('apps.payments.settlement_service.is_bookhara_configured', return_value=True)
    def test_preflight_insufficient_deposit(self, _mock_cfg, mock_adapter_cls):
        adapter = MagicMock()
        mock_adapter_cls.return_value = adapter
        adapter.check_payment_permission.return_value = True
        adapter.check_price.return_value = {
            'is_price_changed': False,
            'new_price': Decimal('1500000'),
        }
        adapter.check_balance.return_value = {'deposit': 100_000, 'credit': 0}

        user = _make_user('+998901234505')
        booking = _make_flight_booking(user, 'bh-127')
        result = FlightSettlementService.run_preflight(booking)

        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, 'insufficient_deposit')


class SettlementSagaTests(TestCase):
    @patch('apps.payments.settlement_service.FlightSettlementService._call_bookhara_pay')
    def test_settlement_success_confirms_booking(self, mock_pay):
        mock_pay.return_value = {
            'status': 'ticketed',
            'fiscalization_v2': {'amount': 1500000, 'total_amount': 1500000},
        }

        user = _make_user('+998901234506')
        booking = _make_flight_booking(user, 'bh-128')
        settlement = BookingSettlement.objects.create(
            booking=booking,
            idempotency_key='test-key-3',
            status=SettlementStatus.PAYMENT_CAPTURED,
        )
        payment = Payment.objects.create(
            booking=booking,
            user=user,
            provider=PaymentProvider.ALIFPAY,
            status=PaymentStatus.SUCCESS,
            amount=Decimal('1500000'),
        )
        settlement.payment = payment
        settlement.save()

        ok = FlightSettlementService.settle_with_bookhara(booking, payment)
        self.assertTrue(ok)

        booking.refresh_from_db()
        settlement.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.CONFIRMED)
        self.assertEqual(settlement.status, SettlementStatus.COMPLETED)

    @patch('apps.payments.settlement_service.FlightSettlementService._attempt_refund')
    @patch('apps.payments.settlement_service.FlightSettlementService._cancel_bookhara_hold')
    @patch('apps.payments.settlement_service.FlightSettlementService._call_bookhara_pay')
    def test_settlement_failure_triggers_compensation(
        self, mock_pay, mock_cancel, mock_refund,
    ):
        mock_pay.side_effect = Exception('Depozit yetarli emas')

        user = _make_user('+998901234507')
        booking = _make_flight_booking(user, 'bh-129')
        settlement = BookingSettlement.objects.create(
            booking=booking,
            idempotency_key='test-key-4',
            status=SettlementStatus.PAYMENT_CAPTURED,
        )
        payment = Payment.objects.create(
            booking=booking,
            user=user,
            provider=PaymentProvider.ALIFPAY,
            status=PaymentStatus.SUCCESS,
            amount=Decimal('1500000'),
        )
        settlement.payment = payment
        settlement.save()

        ok = FlightSettlementService.settle_with_bookhara(booking, payment)
        self.assertFalse(ok)

        settlement.refresh_from_db()
        self.assertIn(
            settlement.status,
            (SettlementStatus.BOOKHARA_FAILED, SettlementStatus.REFUND_PENDING),
        )
        mock_cancel.assert_called_once()
        mock_refund.assert_called_once()
