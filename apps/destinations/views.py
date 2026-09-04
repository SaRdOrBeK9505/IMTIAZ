"""Destination views."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi_schemas import ErrorResponseSerializer

from .models import Country, Destination, DestinationImage
from .serializers import (
    CountrySerializer,
    CountryWithDestinationsSerializer,
    DestinationImageSerializer,
    DestinationListSerializer,
    DestinationSerializer,
)

_ADMIN_TAG = 'Admin — Destinations'
_CLIENT_TAG = 'Telegram Mini App — Destinations'


@extend_schema_view(
    list=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Mamlakatlar ro\'yxati',
        description='Admin uchun barcha mamlakatlar.',
    ),
    create=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Yangi mamlakat qo\'shish',
        request=CountrySerializer,
        responses={201: CountrySerializer, 400: ErrorResponseSerializer},
    ),
    retrieve=extend_schema(tags=[_ADMIN_TAG], summary='Mamlakat tafsilotlari'),
    update=extend_schema(tags=[_ADMIN_TAG], summary='Mamlakatni yangilash'),
    partial_update=extend_schema(tags=[_ADMIN_TAG], summary='Mamlakatni qisman yangilash'),
    destroy=extend_schema(tags=[_ADMIN_TAG], summary='Mamlakatni o\'chirish'),
)
class CountryViewSet(viewsets.ModelViewSet):
    """Admin CRUD for countries."""
    
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @action(detail=True, methods=['get'])
    def destinations(self, request, pk=None):
        """GET /api/admin/destinations/countries/{id}/destinations/ — Get country destinations."""
        country = self.get_object()
        destinations = country.destinations.all()
        serializer = DestinationSerializer(destinations, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Manzillar ro\'yxati',
        description='Admin uchun barcha manzillar.',
    ),
    create=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Yangi manzil qo\'shish',
        request=DestinationSerializer,
        responses={201: DestinationSerializer, 400: ErrorResponseSerializer},
    ),
    retrieve=extend_schema(tags=[_ADMIN_TAG], summary='Manzil tafsilotlari'),
    update=extend_schema(tags=[_ADMIN_TAG], summary='Manzilni yangilash'),
    partial_update=extend_schema(tags=[_ADMIN_TAG], summary='Manzilni qisman yangilash'),
    destroy=extend_schema(tags=[_ADMIN_TAG], summary='Manzilni o\'chirish'),
)
class DestinationViewSet(viewsets.ModelViewSet):
    """Admin CRUD for destinations."""
    
    queryset = Destination.objects.select_related('country').prefetch_related('images')
    serializer_class = DestinationSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        qs = super().get_queryset()
        country_id = self.request.query_params.get('country')
        category = self.request.query_params.get('category')
        is_popular = self.request.query_params.get('is_popular')
        
        if country_id:
            qs = qs.filter(country_id=country_id)
        if category:
            qs = qs.filter(category=category)
        if is_popular:
            qs = qs.filter(is_popular=is_popular.lower() == 'true')
        
        return qs
    
    @action(detail=True, methods=['post'])
    def set_primary_image(self, request, pk=None):
        """POST /api/admin/destinations/{id}/set-primary-image/ — Set primary image."""
        destination = self.get_object()
        image_id = request.data.get('image_id')
        
        try:
            image = DestinationImage.objects.get(id=image_id, destination=destination)
            image.is_primary = True
            image.save()
            serializer = DestinationImageSerializer(image)
            return Response(serializer.data)
        except DestinationImage.DoesNotExist:
            return Response(
                {'error': 'Image not found'},
                status=status.HTTP_404_NOT_FOUND
            )


@extend_schema_view(
    list=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Manzil rasmlari ro\'yxati',
        description='Admin uchun barcha manzil rasmlari.',
    ),
    create=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Yangi rasm qo\'shish',
        request=DestinationImageSerializer,
        responses={201: DestinationImageSerializer, 400: ErrorResponseSerializer},
    ),
    retrieve=extend_schema(tags=[_ADMIN_TAG], summary='Rasm tafsilotlari'),
    update=extend_schema(tags=[_ADMIN_TAG], summary='Rasmni yangilash'),
    partial_update=extend_schema(tags=[_ADMIN_TAG], summary='Rasmni qisman yangilash'),
    destroy=extend_schema(tags=[_ADMIN_TAG], summary='Rasmni o\'chirish'),
)
class DestinationImageViewSet(viewsets.ModelViewSet):
    """Admin CRUD for destination images."""
    
    queryset = DestinationImage.objects.select_related('destination')
    serializer_class = DestinationImageSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        qs = super().get_queryset()
        destination_id = self.request.query_params.get('destination')
        if destination_id:
            qs = qs.filter(destination_id=destination_id)
        return qs


@extend_schema(
    tags=[_CLIENT_TAG],
    summary='Mamlakatlar ro\'yxati (klient)',
    description='Foydalanuvchilar uchun mamlakatlar ro\'yxati.',
    responses={200: CountryWithDestinationsSerializer(many=True)},
)
class CountryListView(APIView):
    """GET /api/destinations/countries/ — List countries with popular destinations."""
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        countries = Country.objects.filter(is_active=True).prefetch_related('destinations')
        serializer = CountryWithDestinationsSerializer(countries, many=True)
        return Response(serializer.data)


@extend_schema(
    tags=[_CLIENT_TAG],
    summary='Manzillar ro\'yxati (klient)',
    description='Foydalanuvchilar uchun manzillar ro\'yxati.',
    responses={200: DestinationListSerializer(many=True)},
)
class DestinationListView(APIView):
    """GET /api/destinations/ — List destinations for clients."""
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        destinations = Destination.objects.filter(is_active=True).select_related('country')
        
        # Filter by country
        country_code = request.query_params.get('country_code')
        if country_code:
            destinations = destinations.filter(country__code=country_code.upper())
        
        # Filter by category
        category = request.query_params.get('category')
        if category:
            destinations = destinations.filter(category=category)
        
        # Filter popular
        popular = request.query_params.get('popular')
        if popular:
            destinations = destinations.filter(is_popular=popular.lower() == 'true')
        
        serializer = DestinationListSerializer(destinations, many=True)
        return Response(serializer.data)


@extend_schema(
    tags=[_CLIENT_TAG],
    summary='Manzil tafsilotlari (klient)',
    description='Foydalanuvchilar uchun manzil tafsilotlari.',
    responses={
        200: DestinationSerializer,
        404: ErrorResponseSerializer,
    },
)
class DestinationDetailView(APIView):
    """GET /api/destinations/{id}/ — Destination details for clients."""
    
    permission_classes = [AllowAny]
    
    def get(self, request, pk):
        try:
            destination = Destination.objects.filter(is_active=True).select_related('country').prefetch_related('images').get(pk=pk)
            serializer = DestinationSerializer(destination)
            return Response(serializer.data)
        except Destination.DoesNotExist:
            return Response(
                {'error': 'Destination not found'},
                status=status.HTTP_404_NOT_FOUND
            )
