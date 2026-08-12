"""Events app views."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.core.openapi_schemas import ErrorResponseSerializer

from .models import Event
from .serializers import EventSerializer

_TAG = 'Events'


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

        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__slug=category)

        return qs.order_by('starts_at')

    @extend_schema(
        tags=[_TAG],
        summary='Tadbirlar ro\'yxati',
        description=(
            'Published tadbirlar. Eksklyuziv tadbirlar faqat premium tier foydalanuvchilariga ko\'rinadi.'
        ),
        parameters=[
            OpenApiParameter('category', str, description='Kategoriya slug'),
        ],
        responses={200: EventSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


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

    @extend_schema(
        tags=[_TAG],
        summary='Tadbir tafsilotlari',
        responses={200: EventSerializer, 404: ErrorResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
