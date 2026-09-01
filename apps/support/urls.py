"""User Inquiry/Support URLs."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AdminInquiryViewSet,
    CreateInquiryView,
    InquiryDetailView,
    UserInquiryListView,
)

router = DefaultRouter()
router.register('admin', AdminInquiryViewSet, basename='admin-inquiries')

urlpatterns = [
    # User endpoints
    path('inquiries/', UserInquiryListView.as_view(), name='user-inquiries'),
    path('inquiries/create/', CreateInquiryView.as_view(), name='create-inquiry'),
    path('inquiries/<uuid:pk>/', InquiryDetailView.as_view(), name='inquiry-detail'),
    
    # Admin endpoints
    path('', include(router.urls)),
]
