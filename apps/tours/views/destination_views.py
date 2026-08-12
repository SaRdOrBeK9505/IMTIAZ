"""Mijozlar uchun yo'nalishlar API — qidiruv, filter, pagination."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi_schemas import ErrorResponseSerializer

from ..pagination import TourDestinationPagination
from ..serializers import TourDestinationDetailSerializer, TourDestinationListSerializer
from ..services import TourDestinationSearchService

_DEST_TAG = 'Tours — Destinations'

_LIST_PARAMS = [
    OpenApiParameter('q', str, description='Qidiruv: nom, mamlakat, shahar, tavsif'),
    OpenApiParameter('country', str, description='Mamlakat nomi'),
    OpenApiParameter('country_code', str, description='ISO mamlakat kodi (AE, TR, ...)'),
    OpenApiParameter('city', str, description='Shahar'),
    OpenApiParameter('is_popular', bool, description='Faqat mashhur yo\'nalishlar'),
    OpenApiParameter('min_price', float, description='Minimal tur narxi (UZS)'),
    OpenApiParameter('max_price', float, description='Maksimal tur narxi (UZS)'),
    OpenApiParameter('min_packages', int, description='Kamida N ta tur'),
    OpenApiParameter('category_id', str, description='Kategoriya bo\'yicha filter'),
    OpenApiParameter('organization_id', str, description='Tur kompaniyasi ID'),
    OpenApiParameter('min_days', int, description='Minimal tur davomiyligi (kun)'),
    OpenApiParameter('max_days', int, description='Maksimal tur davomiyligi (kun)'),
    OpenApiParameter('difficulty', str, description='easy | moderate | hard | extreme'),
    OpenApiParameter('has_upcoming', bool, description='Kelgusi jo\'nash sanasi bor yo\'nalishlar'),
    OpenApiParameter('departure_from', str, description='Jo\'nash sanasidan (YYYY-MM-DD)'),
    OpenApiParameter('departure_to', str, description='Jo\'nash sanasigacha (YYYY-MM-DD)'),
    OpenApiParameter(
        'ordering',
        str,
        description='popular | price_asc | price_desc | name | name_desc | packages | rating | newest',
    ),
    OpenApiParameter('page', int, description='Sahifa raqami'),
    OpenApiParameter('page_size', int, description='Sahifadagi elementlar (max 48, default 12)'),
]


def _parse_bool(value: str | None) -> bool | None:
    if value is None or value == '':
        return None
    return value.lower() in ('true', '1', 'yes')


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None or value == '':
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _parse_int(value: str | None) -> int | None:
    if value is None or value == '':
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _search_params_from_request(request) -> dict:
    p = request.query_params
    return {
        'query': p.get('q') or None,
        'country': p.get('country') or None,
        'country_code': p.get('country_code') or None,
        'city': p.get('city') or None,
        'is_popular': _parse_bool(p.get('is_popular')),
        'min_price': _parse_decimal(p.get('min_price')),
        'max_price': _parse_decimal(p.get('max_price')),
        'min_packages': _parse_int(p.get('min_packages')),
        'category_id': p.get('category_id') or None,
        'organization_id': p.get('organization_id') or None,
        'min_days': _parse_int(p.get('min_days')),
        'max_days': _parse_int(p.get('max_days')),
        'difficulty': p.get('difficulty') or None,
        'has_upcoming': _parse_bool(p.get('has_upcoming')),
        'departure_from': p.get('departure_from') or None,
        'departure_to': p.get('departure_to') or None,
        'ordering': p.get('ordering') or None,
    }


class TourDestinationListView(generics.ListAPIView):
    """
    GET /api/tours/destinations/
    Mijozlar uchun yo'nalishlar grid — filter, qidiruv, pagination.
    """
    permission_classes = [AllowAny]
    serializer_class = TourDestinationListSerializer
    pagination_class = TourDestinationPagination

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            from ..models import TourDestination
            return TourDestination.objects.none()
        return TourDestinationSearchService.search(**_search_params_from_request(self.request))

    @extend_schema(
        summary='Sayohat yo\'nalishlari (filter + qidiruv + pagination)',
        tags=[_DEST_TAG],
        parameters=_LIST_PARAMS,
        responses={200: TourDestinationListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class TourDestinationDetailView(generics.RetrieveAPIView):
    """GET /api/tours/destinations/<id>/ — to'liq yo'nalish + tavsiya etilgan turlar."""
    permission_classes = [AllowAny]
    serializer_class = TourDestinationDetailSerializer
    lookup_field = 'pk'

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            from ..models import TourDestination
            return TourDestination.objects.none()
        return TourDestinationSearchService.base_queryset()

    @extend_schema(
        summary='Yo\'nalish tafsiloti',
        tags=[_DEST_TAG],
        responses={200: TourDestinationDetailSerializer, 404: ErrorResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class TourDestinationFiltersView(APIView):
    """
    GET /api/tours/destinations/filters/
    Mobil filter UI uchun mavjud mamlakatlar, kategoriyalar, narx diapazoni.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Yo\'nalish filter metadata',
        tags=[_DEST_TAG],
        responses={200: OpenApiResponse(description='Mavjud filterlar')},
    )
    def get(self, request):
        return Response(TourDestinationSearchService.get_filter_metadata())


class TourDestinationPackagesView(generics.ListAPIView):
    """
    GET /api/tours/destinations/<id>/packages/
    Tanlangan yo'nalishdagi barcha turlar (pagination bilan).
    """
    permission_classes = [AllowAny]
    pagination_class = TourDestinationPagination

    def get_serializer_class(self):
        from ..serializers import TourPackageListSerializer
        return TourPackageListSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            from ..models import TourPackage
            return TourPackage.objects.none()

        from ..models import TourPackage

        destination = TourDestinationSearchService.get_detail(str(self.kwargs['pk']))
        if not destination:
            return TourPackage.objects.none()

        qs = TourPackage.objects.filter(
            destination=destination,
            is_active=True,
            organization__is_active=True,
        ).select_related('destination', 'category', 'organization')

        p = self.request.query_params
        if category_id := p.get('category_id'):
            qs = qs.filter(category_id=category_id)
        if min_price := _parse_decimal(p.get('min_price')):
            qs = qs.filter(base_price__gte=min_price)
        if max_price := _parse_decimal(p.get('max_price')):
            qs = qs.filter(base_price__lte=max_price)
        if difficulty := p.get('difficulty'):
            qs = qs.filter(difficulty_level=difficulty)
        if p.get('is_featured', '').lower() == 'true':
            qs = qs.filter(is_featured=True)

        ordering = p.get('ordering', 'featured')
        order_map = {
            'featured': ['-is_featured', '-avg_rating', '-total_bookings'],
            'price_asc': ['base_price', 'title'],
            'price_desc': ['-base_price', 'title'],
            'rating': ['-avg_rating', '-review_count'],
            'newest': ['-created_at'],
        }
        return qs.order_by(*order_map.get(ordering, order_map['featured']))

    @extend_schema(
        summary='Yo\'nalishdagi turlar ro\'yxati',
        tags=[_DEST_TAG],
        parameters=[
            OpenApiParameter('category_id', str, required=False),
            OpenApiParameter('min_price', float, required=False),
            OpenApiParameter('max_price', float, required=False),
            OpenApiParameter('difficulty', str, required=False),
            OpenApiParameter('is_featured', bool, required=False),
            OpenApiParameter('ordering', str, required=False),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
    )
    def get(self, request, *args, **kwargs):
        if not TourDestinationSearchService.get_detail(str(self.kwargs['pk'])):
            return Response({'message': 'Yo\'nalish topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        return super().get(request, *args, **kwargs)
