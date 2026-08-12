from django.urls import path
from .views import (
    PaymentListView,
    PaymentInitiateView,
    PaymentConfirmView,
    PaymentWebhookView,
)

urlpatterns = [
    path('',                           PaymentListView.as_view(),    name='payment-list'),
    path('initiate/',                  PaymentInitiateView.as_view(), name='payment-initiate'),
    path('<uuid:payment_id>/confirm/', PaymentConfirmView.as_view(), name='payment-confirm'),
    path('webhook/<str:provider>/',    PaymentWebhookView.as_view(), name='payment-webhook'),
]
