from django.urls import path
from .views import BookingListView, BookingDetailView, CreateRestaurantBookingFromAIView

urlpatterns = [
    path('', BookingListView.as_view(), name='booking-list'),
    path('<uuid:pk>/', BookingDetailView.as_view(), name='booking-detail'),
    path('restaurant/create-from-ai/', CreateRestaurantBookingFromAIView.as_view(), name='restaurant-booking-create-from-ai'),
]
