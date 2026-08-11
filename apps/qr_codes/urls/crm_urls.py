"""QR Codes — CRM URL routes."""

from django.urls import path
from apps.qr_codes.views import (
    QRCodeCRMListCreateView,
    QRCodeCRMDetailView,
    QRCodeRegenerateView,
    QRCodeRedemptionListView,
    QRAllRedemptionsListView,
    QRStaffScanView,
    QRStaffRedeemView,
    QRScannerDashboardView,
    QRBonusesListView,
    QRCodeAnalyticsView,
    QRAllAnalyticsView,
)

urlpatterns = [
    # UI sahifalari (screenshot mos — specific pathlar birinchi)
    path('scanner/',                     QRScannerDashboardView.as_view(),     name='crm-qr-scanner'),
    path('bonuses/',                     QRBonusesListView.as_view(),          name='crm-qr-bonuses'),
    path('analytics/',                   QRAllAnalyticsView.as_view(),         name='crm-qr-all-analytics'),
    path('redemptions/',                 QRAllRedemptionsListView.as_view(),   name='crm-qr-all-redemptions'),
    path('scan/',                        QRStaffScanView.as_view(),            name='crm-qr-scan'),
    path('redeem/',                      QRStaffRedeemView.as_view(),          name='crm-qr-redeem'),

    # QR kodlar CRUD
    path('',                             QRCodeCRMListCreateView.as_view(),    name='crm-qr-list'),
    path('<uuid:pk>/',                   QRCodeCRMDetailView.as_view(),        name='crm-qr-detail'),
    path('<uuid:pk>/regenerate/',        QRCodeRegenerateView.as_view(),       name='crm-qr-regenerate'),
    path('<uuid:pk>/redemptions/',       QRCodeRedemptionListView.as_view(),   name='crm-qr-redemptions'),
    path('<uuid:pk>/analytics/',         QRCodeAnalyticsView.as_view(),        name='crm-qr-analytics'),
]
