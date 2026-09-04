from django.urls import path

from .crm_views import (
    CRMNotificationListView,
    CRMNotificationReadAllView,
    CRMNotificationReadView,
)
from .promo_views import PromoDiscountListView, PromoDiscountDetailView

urlpatterns = [
    path('', CRMNotificationListView.as_view(), name='crm-notification-list'),
    path('read-all/', CRMNotificationReadAllView.as_view(), name='crm-notification-read-all'),
    path('<uuid:pk>/read/', CRMNotificationReadView.as_view(), name='crm-notification-read'),
    path('promo-discounts/', PromoDiscountListView.as_view(), name='crm-promo-discounts-list'),
    path('promo-discounts/<uuid:pk>/', PromoDiscountDetailView.as_view(), name='crm-promo-discounts-detail'),
]
