from django.urls import path

from .views import (
    RequestOTPView,
    VerifyOTPView,
    CompleteRegistrationView,
    LoginView,
    CRMLoginView,
    AdminLoginView,
    LogoutView,
    TokenRefreshView,
    UserMeView,
    AISettingsView,
)
from .crm_onboarding_views import CRMOwnerRegisterDisabledView

urlpatterns = [
    # ── Ro'yxatdan o'tish (customer) ──────────────────────────────────────────
    path('auth/register/request-otp/', RequestOTPView.as_view(),          name='register-request-otp'),
    path('auth/register/verify-otp/',  VerifyOTPView.as_view(),           name='register-verify-otp'),
    path('auth/register/complete/',    CompleteRegistrationView.as_view(), name='register-complete'),

    # CRM owner self-register o'chirilgan — faqat Django admin
    path('crm/auth/register/request-otp/', CRMOwnerRegisterDisabledView.as_view(), name='crm-owner-register-request-otp'),
    path('crm/auth/register/verify-otp/',  CRMOwnerRegisterDisabledView.as_view(), name='crm-owner-register-verify-otp'),
    path('crm/auth/register/complete/',    CRMOwnerRegisterDisabledView.as_view(), name='crm-owner-register-complete'),

    # ── Login (phone + password) ──────────────────────────────────────────────
    path('auth/login/',       LoginView.as_view(),      name='auth-login'),
    path('crm/auth/login/',   CRMLoginView.as_view(),   name='auth-crm-login'),
    path('admin/auth/login/', AdminLoginView.as_view(), name='auth-admin-login'),

    # ── Token ────────────────────────────────────────────────────────────────
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/logout/',        LogoutView.as_view(),        name='auth-logout'),

    # ── Profile ───────────────────────────────────────────────────────────────
    path('users/me/',             UserMeView.as_view(),     name='user-me'),
    path('users/me/ai-settings/', AISettingsView.as_view(), name='user-ai-settings'),
]
