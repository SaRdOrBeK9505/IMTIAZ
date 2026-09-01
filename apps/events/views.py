"""Events app views."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi_schemas import ErrorResponseSerializer

from .models import Event, EventRegistration
from .serializers import (
    EventSerializer,
    EventRegistrationCreateSerializer,
    EventRegistrationSerializer,
)

_TAG = 'Events'
_ADMIN_TAG = 'Admin — Events'


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


class EventRegistrationListView(generics.ListAPIView):
    """GET /api/events/registrations/ — List user's event registrations."""
    
    permission_classes = [IsAuthenticated]
    serializer_class = EventRegistrationSerializer
    
    def get_queryset(self):
        return EventRegistration.objects.filter(user=self.request.user).select_related('event')
    
    @extend_schema(
        tags=[_TAG],
        summary='Mening tadbir ro\'yxatlarim',
        responses={200: EventRegistrationSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class EventRegistrationDetailView(generics.RetrieveAPIView):
    """GET /api/events/registrations/{id}/ — Get registration details."""
    
    permission_classes = [IsAuthenticated]
    serializer_class = EventRegistrationSerializer
    
    def get_queryset(self):
        return EventRegistration.objects.filter(user=self.request.user).select_related('event')
    
    @extend_schema(
        tags=[_TAG],
        summary='Ro\'yxat tafsilotlari',
        responses={200: EventRegistrationSerializer, 404: ErrorResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CreateEventRegistrationView(APIView):
    """POST /api/events/{event_id}/register/ — Register for an event."""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=[_TAG],
        summary='Tadbirga ro\'yxatga olish',
        request=EventRegistrationCreateSerializer,
        responses={
            201: EventRegistrationSerializer,
            400: ErrorResponseSerializer,
        },
    )
    def post(self, request, event_id):
        try:
            event = Event.objects.get(pk=event_id, status='published')
        except Event.DoesNotExist:
            return Response(
                {'error': 'Event not found or not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = EventRegistrationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if already registered
        if EventRegistration.objects.filter(event=event, user=request.user).exists():
            return Response(
                {'error': 'Siz allaqachon bu tadbirga ro\'yxatga olingansiz'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create registration
        registration = EventRegistration.objects.create(
            event=event,
            user=request.user,
            ticket_count=serializer.validated_data['ticket_count'],
            special_requests=serializer.validated_data.get('special_requests', '')
        )
        
        # Confirm registration
        registration.confirm()
        
        response_serializer = EventRegistrationSerializer(registration)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class CancelEventRegistrationView(APIView):
    """POST /api/events/registrations/{id}/cancel/ — Cancel registration."""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=[_TAG],
        summary='Ro\'yxatni bekor qilish',
        responses={
            200: EventRegistrationSerializer,
            400: ErrorResponseSerializer,
        },
    )
    def post(self, request, pk):
        try:
            registration = EventRegistration.objects.get(pk=pk, user=request.user)
            registration.cancel()
            serializer = EventRegistrationSerializer(registration)
            return Response(serializer.data)
        except EventRegistration.DoesNotExist:
            return Response(
                {'error': 'Registration not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema_view(
    list=extend_schema(tags=[_ADMIN_TAG], summary='Barcha ro\'yxatlar (admin)'),
    retrieve=extend_schema(tags=[_ADMIN_TAG], summary='Ro\'yxat tafsilotlari (admin)'),
)
class EventRegistrationAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin viewset for event registrations."""
    
    queryset = EventRegistration.objects.select_related('event', 'user')
    serializer_class = EventRegistrationSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @action(detail=True, methods=['post'])
    def check_in(self, request, pk=None):
        """POST /api/admin/events/registrations/{id}/check_in/ — Check in user."""
        registration = self.get_object()
        try:
            registration.check_in()
            serializer = self.get_serializer(registration)
            return Response(serializer.data)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
