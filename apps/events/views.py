"""Events app views."""

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Event
from .serializers import EventSerializer


class EventListView(generics.ListAPIView):
    """
    GET /api/events/
    Eksklyuziv tadbirlar faqat tier.exclusive_events_access=True bo'lgan foydalanuvchilarga ko'rinadi.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = EventSerializer

    def get_queryset(self):
        user = self.request.user
        try:
            has_exclusive = user.membership_tier.exclusive_events_access
        except Exception:
            has_exclusive = False

        qs = Event.objects.filter(status='published').select_related('category', 'branch')
        if not has_exclusive:
            qs = qs.filter(is_exclusive=False)

        # Filtrlash
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__slug=category)

        return qs.order_by('starts_at')


class EventDetailView(generics.RetrieveAPIView):
    """GET /api/events/{id}/"""
    permission_classes = [IsAuthenticated]
    serializer_class = EventSerializer

    def get_queryset(self):
        user = self.request.user
        try:
            has_exclusive = user.membership_tier.exclusive_events_access
        except Exception:
            has_exclusive = False

        qs = Event.objects.filter(status='published').select_related('category', 'branch')
        if not has_exclusive:
            qs = qs.filter(is_exclusive=False)
        return qs
