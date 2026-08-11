"""QR Codes — User-facing URL routes."""

from django.urls import path
from apps.qr_codes.views import QRCodeInfoView, QRRedeemView

urlpatterns = [
    path('<str:code>/',         QRCodeInfoView.as_view(), name='qr-info'),
    path('<str:code>/redeem/',  QRRedeemView.as_view(),   name='qr-redeem'),
]
