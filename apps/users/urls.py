from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RequestOTPView,
    VerifyOTPView,
    CompleteRegistrationView,
    LoginView,
    CRMLoginView,
    AdminLoginView,
    LogoutView,
    UserMeView,
    AISettingsView,
)

urlpatterns = [
    # ── Ro'yxatdan o'tish ─────────────────────────────────────────────────────
    path('auth/register/request-otp/', RequestOTPView.as_view(),          name='register-request-otp'),
    path('auth/register/verify-otp/',  VerifyOTPView.as_view(),           name='register-verify-otp'),
    path('auth/register/complete/',    CompleteRegistrationView.as_view(), name='register-complete'),

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
