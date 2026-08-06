from django.urls import path
from .views import (
    TelegramAuthView,
    SMSSendView,
    SMSVerifyView,
    UserMeView,
    AISettingsView,
    WalletView,
)

urlpatterns = [
    # Auth
    path('auth/telegram/',   TelegramAuthView.as_view(), name='auth-telegram'),
    path('auth/sms/send/',   SMSSendView.as_view(),      name='auth-sms-send'),
    path('auth/sms/verify/', SMSVerifyView.as_view(),    name='auth-sms-verify'),

    # Profile
    path('users/me/',              UserMeView.as_view(),    name='user-me'),
    path('users/me/ai-settings/',  AISettingsView.as_view(), name='user-ai-settings'),

    # Wallet
    path('wallet/', WalletView.as_view(), name='wallet'),
]
