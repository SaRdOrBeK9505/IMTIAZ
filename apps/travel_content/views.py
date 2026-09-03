"""Travel Content views — Admin CRUD and Client read-only."""

from django.db.models import F
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, generics, permissions

from .models import TravelReel, CuratedTrip, CuratedTripImage
from .pagination import TravelContentPagination
from .serializers import (
    TravelReelAdminSerializer, TravelReelListSerializer, TravelReelDetailSerializer,
    CuratedTripAdminSerializer, CuratedTripImageSerializer,
    CuratedTripListSerializer, CuratedTripDetailSerializer,
)

_ADMIN_TAG = 'Admin — Travel Content'
_CLIENT_TAG = 'Client — Travel Content'


# ══════════════════════════ ADMIN — CRUD ════════════════════════════════════

@extend_schema_view(
    list=extend_schema(tags=[_ADMIN_TAG]), retrieve=extend_schema(tags=[_ADMIN_TAG]),
    create=extend_schema(tags=[_ADMIN_TAG]), update=extend_schema(tags=[_ADMIN_TAG]),
    partial_update=extend_schema(tags=[_ADMIN_TAG]), destroy=extend_schema(tags=[_ADMIN_TAG]),
)
class TravelReelViewSet(viewsets.ModelViewSet):
    queryset = TravelReel.objects.select_related('destination').all()
    serializer_class = TravelReelAdminSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = TravelContentPagination
    filterset_fields = ['media_type', 'is_active', 'destination']
    search_fields = ['title', 'subtitle']


@extend_schema_view(
    list=extend_schema(tags=[_ADMIN_TAG]), retrieve=extend_schema(tags=[_ADMIN_TAG]),
    create=extend_schema(tags=[_ADMIN_TAG]), update=extend_schema(tags=[_ADMIN_TAG]),
    partial_update=extend_schema(tags=[_ADMIN_TAG]), destroy=extend_schema(tags=[_ADMIN_TAG]),
)
class CuratedTripViewSet(viewsets.ModelViewSet):
    queryset = CuratedTrip.objects.select_related('destination').prefetch_related('gallery_images').all()
    serializer_class = CuratedTripAdminSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = TravelContentPagination
    filterset_fields = ['is_active', 'is_featured', 'is_verified_by_imtiaz', 'destination']
    search_fields = ['title', 'subtitle']


@extend_schema_view(
    list=extend_schema(tags=[_ADMIN_TAG]), retrieve=extend_schema(tags=[_ADMIN_TAG]),
    create=extend_schema(tags=[_ADMIN_TAG]), update=extend_schema(tags=[_ADMIN_TAG]),
    partial_update=extend_schema(tags=[_ADMIN_TAG]), destroy=extend_schema(tags=[_ADMIN_TAG]),
)
class CuratedTripImageViewSet(viewsets.ModelViewSet):
    queryset = CuratedTripImage.objects.select_related('trip').all()
    serializer_class = CuratedTripImageSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ['trip']


# ══════════════════════════ CLIENT — READ ONLY ═══════════════════════════════

class TravelReelListView(generics.ListAPIView):
    """GET /api/travel-content/reels/ — Screenshot 1 uchun kartochkalar ro'yxati."""
    queryset = TravelReel.objects.filter(is_active=True).select_related('destination')
    serializer_class = TravelReelListSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = TravelContentPagination
    filterset_fields = ['destination', 'media_type']

    @extend_schema(tags=[_CLIENT_TAG])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class TravelReelDetailView(generics.RetrieveAPIView):
    """GET /api/travel-content/reels/{id}/ — Screenshot 2, fullscreen reels."""
    queryset = TravelReel.objects.filter(is_active=True).select_related('destination')
    serializer_class = TravelReelDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'pk'

    @extend_schema(tags=[_CLIENT_TAG])
    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        TravelReel.objects.filter(pk=instance.pk).update(view_count=F('view_count') + 1)
        return super().get(request, *args, **kwargs)


class CuratedTripListView(generics.ListAPIView):
    """GET /api/travel-content/curated-trips/ — Screenshot 3, 4 kartochkalar ro'yxati."""
    queryset = CuratedTrip.objects.filter(is_active=True).select_related('destination')
    serializer_class = CuratedTripListSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = TravelContentPagination
    filterset_fields = ['destination', 'is_featured']

    @extend_schema(tags=[_CLIENT_TAG])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CuratedTripDetailView(generics.RetrieveAPIView):
    """GET /api/travel-content/curated-trips/{id}/ — to'liq ma'lumot + video."""
    queryset = CuratedTrip.objects.filter(is_active=True).select_related('destination').prefetch_related('gallery_images')
    serializer_class = CuratedTripDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'pk'

    @extend_schema(tags=[_CLIENT_TAG])
    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        CuratedTrip.objects.filter(pk=instance.pk).update(view_count=F('view_count') + 1)
        return super().get(request, *args, **kwargs)

