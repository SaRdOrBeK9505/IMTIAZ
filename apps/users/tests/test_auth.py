"""
Auth oqimi testlari.

Coverage:
    - RequestOTPView      (qadam 1)
    - VerifyOTPView       (qadam 2)
    - CompleteRegistrationView (qadam 3+4)
    - LoginView
    - CRMLoginView
    - AdminLoginView
    - LogoutView
"""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.core.signing import TimestampSigner
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import OTPCode, User, UserRole

_signer = TimestampSigner()


def _make_user(phone='+998901234567', role=UserRole.CUSTOMER, password='Test1234!'):
    user = User.objects.create(
        phone=phone,
        first_name='Test',
        last_name='User',
        role=role,
        is_phone_verified=True,
    )
    user.set_password(password)
    user.save(update_fields=['password'])
    return user


def _make_otp(phone, purpose=OTPCode.Purpose.REGISTER):
    return OTPCode.create_for_phone(phone, purpose=purpose)


# ─── Qadam 1: RequestOTP ──────────────────────────────────────────────────────

class RequestOTPViewTests(TestCase):
    url = '/api/auth/register/request-otp/'

    def setUp(self):
        self.client = APIClient()
        cache.clear()

    @patch('apps.users.views.send_otp_sms', return_value=True)
    def test_success(self, mock_sms):
        resp = self.client.post(self.url, {
            'full_name':    'Asilbek Karimov',
            'phone_number': '+998901234567',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('expires_in', resp.data)
        mock_sms.assert_called_once()

        # Cache'da saqlangan
        reg = cache.get('register_data:+998901234567')
        self.assertEqual(reg['full_name'], 'Asilbek Karimov')

    @patch('apps.users.views.send_otp_sms', return_value=True)
    def test_already_registered(self, mock_sms):
        _make_user(phone='+998901234567')
        resp = self.client.post(self.url, {
            'full_name':    'Asilbek Karimov',
            'phone_number': '+998901234567',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.users.views.send_otp_sms', return_value=True)
    def test_rate_limit(self, mock_sms):
        cache.set('sms_rate:+998901234568', True, timeout=60)
        resp = self.client.post(self.url, {
            'full_name':    'Test User',
            'phone_number': '+998901234568',
        })
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_invalid_phone(self):
        resp = self.client.post(self.url, {
            'full_name':    'Test User',
            'phone_number': '12345',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_single_word_full_name(self):
        resp = self.client.post(self.url, {
            'full_name':    'Asilbek',
            'phone_number': '+998901234567',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.users.views.send_otp_sms', return_value=False)
    def test_sms_failure(self, mock_sms):
        resp = self.client.post(self.url, {
            'full_name':    'Asilbek Karimov',
            'phone_number': '+998901234567',
        })
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


# ─── Qadam 2: VerifyOTP ───────────────────────────────────────────────────────

class VerifyOTPViewTests(TestCase):
    url   = '/api/auth/register/verify-otp/'
    phone = '+998901234567'

    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def test_success(self):
        otp = _make_otp(self.phone)
        resp = self.client.post(self.url, {
            'phone_number': self.phone,
            'otp_code':     otp.code,
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('verification_token', resp.data)
        # OTP is_used bo'lishi kerak
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_wrong_code(self):
        _make_otp(self.phone)
        resp = self.client.post(self.url, {
            'phone_number': self.phone,
            'otp_code':     '000000',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_otp_found(self):
        resp = self.client.post(self.url, {
            'phone_number': self.phone,
            'otp_code':     '123456',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_brute_force_block(self):
        otp = _make_otp(self.phone)
        otp.attempts = 5
        otp.save(update_fields=['attempts'])
        resp = self.client.post(self.url, {
            'phone_number': self.phone,
            'otp_code':     otp.code,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ─── Qadam 3+4: CompleteRegistration ─────────────────────────────────────────

class CompleteRegistrationViewTests(TestCase):
    url   = '/api/auth/register/complete/'
    phone = '+998901234567'

    def setUp(self):
        self.client = APIClient()
        cache.clear()
        cache.set(
            f'register_data:{self.phone}',
            {'full_name': 'Asilbek Karimov'},
            timeout=900,
        )

    def _get_token(self):
        return _signer.sign(self.phone)

    def test_success_without_telegram(self):
        resp = self.client.post(self.url, {
            'verification_token': self._get_token(),
            'password':           'Qwerty123!',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)
        self.assertTrue(resp.data['is_new_user'])

        user = User.objects.get(phone=self.phone)
        self.assertEqual(user.first_name, 'Asilbek')
        self.assertEqual(user.last_name, 'Karimov')
        self.assertTrue(user.is_phone_verified)
        self.assertIsNone(user.telegram_id)
        self.assertEqual(user.role, UserRole.CUSTOMER)

    def test_jwt_audience_is_mobile(self):
        resp = self.client.post(self.url, {
            'verification_token': self._get_token(),
            'password':           'Qwerty123!',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        token = RefreshToken(resp.data['refresh'])
        self.assertEqual(token['aud'], 'mobile')
        self.assertEqual(token['role'], UserRole.CUSTOMER)

    def test_no_register_data_in_cache(self):
        cache.clear()
        resp = self.client.post(self.url, {
            'verification_token': self._get_token(),
            'password':           'Qwerty123!',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_token(self):
        resp = self.client.post(self.url, {
            'verification_token': 'invalid:token:xyz',
            'password':           'Qwerty123!',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_password(self):
        resp = self.client.post(self.url, {
            'verification_token': self._get_token(),
            'password':           '123',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cache_cleared_after_registration(self):
        self.client.post(self.url, {
            'verification_token': self._get_token(),
            'password':           'Qwerty123!',
        })
        self.assertIsNone(cache.get(f'register_data:{self.phone}'))

    def test_duplicate_registration(self):
        token = self._get_token()
        self.client.post(self.url, {'verification_token': token, 'password': 'Qwerty123!'})
        # cache tozalandi — ikkinchi urinish xato qaytaradi
        resp = self.client.post(self.url, {'verification_token': token, 'password': 'Qwerty123!'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ─── Login ────────────────────────────────────────────────────────────────────

class LoginViewTests(TestCase):
    url = '/api/auth/login/'

    def setUp(self):
        self.client = APIClient()
        self.user   = _make_user()

    def test_success(self):
        resp = self.client.post(self.url, {
            'phone':    '+998901234567',
            'password': 'Test1234!',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)
        self.assertEqual(resp.data['user']['role'], UserRole.CUSTOMER)

    def test_jwt_claims(self):
        resp = self.client.post(self.url, {'phone': '+998901234567', 'password': 'Test1234!'})
        token = RefreshToken(resp.data['refresh'])
        self.assertEqual(token['aud'], 'mobile')
        self.assertEqual(token['role'], UserRole.CUSTOMER)

    def test_wrong_password(self):
        resp = self.client.post(self.url, {'phone': '+998901234567', 'password': 'wrong'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wrong_role_blocked(self):
        """Customer endpoint orqali CRM useri kira olmasin."""
        _make_user(phone='+998901234568', role=UserRole.OWNER)
        resp = self.client.post(self.url, {'phone': '+998901234568', 'password': 'Test1234!'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_phone_normalization(self):
        """+ belgisiz ham kirish ishlashi kerak."""
        resp = self.client.post(self.url, {'phone': '998901234567', 'password': 'Test1234!'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        resp = self.client.post(self.url, {'phone': '+998901234567', 'password': 'Test1234!'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class CRMLoginViewTests(TestCase):
    url = '/api/crm/auth/login/'

    def setUp(self):
        self.client = APIClient()

    def test_owner_can_login(self):
        _make_user(phone='+998901234567', role=UserRole.OWNER)
        resp = self.client.post(self.url, {'phone': '+998901234567', 'password': 'Test1234!'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        token = RefreshToken(resp.data['refresh'])
        self.assertEqual(token['aud'], 'crm')

    def test_branch_staff_can_login(self):
        _make_user(phone='+998901234568', role=UserRole.BRANCH_STAFF)
        resp = self.client.post(self.url, {'phone': '+998901234568', 'password': 'Test1234!'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_customer_blocked(self):
        _make_user(phone='+998901234569', role=UserRole.CUSTOMER)
        resp = self.client.post(self.url, {'phone': '+998901234569', 'password': 'Test1234!'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class AdminLoginViewTests(TestCase):
    url = '/api/admin/auth/login/'

    def setUp(self):
        self.client = APIClient()

    def test_admin_can_login(self):
        _make_user(phone='+998901234567', role=UserRole.ADMIN)
        resp = self.client.post(self.url, {'phone': '+998901234567', 'password': 'Test1234!'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        token = RefreshToken(resp.data['refresh'])
        self.assertEqual(token['aud'], 'admin')

    def test_customer_blocked(self):
        _make_user(phone='+998901234568', role=UserRole.CUSTOMER)
        resp = self.client.post(self.url, {'phone': '+998901234568', 'password': 'Test1234!'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ─── Audience tekshiruvi ──────────────────────────────────────────────────────

class AudienceAuthTests(TestCase):
    """CRM tokeni mobile endpointga kira olmasligi va aksincha."""

    def setUp(self):
        self.client  = APIClient()
        self.customer = _make_user(phone='+998901234567', role=UserRole.CUSTOMER)
        self.owner    = _make_user(phone='+998901234568', role=UserRole.OWNER)

    def _get_token(self, user: User) -> str:
        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        refresh['aud']  = user.jwt_audience
        return str(refresh.access_token)

    def test_mobile_token_accepted_on_me(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self._get_token(self.customer)}')
        resp = self.client.get('/api/users/me/')
        # IsAuthenticated (no aud check on /users/me/) — should pass
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_crm_token_rejected_on_mobile_endpoint_via_crm_auth(self):
        """CRM auth class ishlatadigan endpoint crm token qabul qilishi kerak."""
        from apps.core.authentication import CRMJWTAuthentication
        token = self._get_token(self.owner)
        # CRMJWTAuthentication: aud='crm' → qabul qiladi
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        req     = factory.get('/', HTTP_AUTHORIZATION=f'Bearer {token}')
        auth    = CRMJWTAuthentication()
        result  = auth.authenticate(req)
        self.assertIsNotNone(result)
        self.assertEqual(result[0].pk, self.owner.pk)

    def test_mobile_token_rejected_by_crm_auth(self):
        """Mobile token CRM auth classidan o'tmasligi kerak."""
        from apps.core.authentication import CRMJWTAuthentication
        from rest_framework.exceptions import AuthenticationFailed
        from rest_framework.test import APIRequestFactory
        token   = self._get_token(self.customer)
        factory = APIRequestFactory()
        req     = factory.get('/', HTTP_AUTHORIZATION=f'Bearer {token}')
        auth    = CRMJWTAuthentication()
        with self.assertRaises(AuthenticationFailed):
            auth.authenticate(req)


# ─── Logout ───────────────────────────────────────────────────────────────────

class LogoutViewTests(TestCase):
    url = '/api/auth/logout/'

    def setUp(self):
        self.client = APIClient()
        self.user   = _make_user()

    def _auth(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}'
        )
        return str(refresh)

    def test_logout_success(self):
        refresh = self._auth()
        resp = self.client.post(self.url, {'refresh': refresh})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_logout_invalid_token(self):
        self._auth()
        resp = self.client.post(self.url, {'refresh': 'invalid.token.here'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_requires_auth(self):
        self.client.credentials()
        resp = self.client.post(self.url, {'refresh': 'something'})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
