from django.urls import path
from .views import MembershipTierListView, MyMembershipView, WaitlistApplyView, SubscriptionView

urlpatterns = [
    path('tiers/',        MembershipTierListView.as_view(), name='membership-tiers'),
    path('my/',           MyMembershipView.as_view(),       name='membership-my'),
    path('waitlist/',     WaitlistApplyView.as_view(),      name='membership-waitlist'),
    path('subscription/', SubscriptionView.as_view(),       name='membership-subscription'),
]
