"""Destination views."""

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets, status

from apps.core.openapi_schemas import ErrorResponseSerializer

from .models import Destination
from .serializers import DestinationAdminSerializer, DestinationClientSerializer

_ADMIN_TAG  = 'Admin — Destinations'
_CLIENT_TAG = 'Telegram Mini App — Destinations'


# ── Admin CRUD ────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=[_ADMIN_TAG], summary='Destinatsiyalar ro\'yxati (admin)',
        parameters=[
            OpenApiParameter('group', str, description='popular | signature'),
            OpenApiParameter('is_active', bool),
        ],
    ),
    create=extend_schema(
        tags=[_ADMIN_TAG], summary='Yangi destinatsiya qo\'shish',
        responses={201: DestinationAdminSerializer, 400: ErrorResponseSerializer},
    ),
    retrieve=extend_schema(tags=[_ADMIN_TAG], summary='Destinatsiya tafsilotlari'),
    update=extend_schema(tags=[_ADMIN_TAG], summary='To\'liq yangilash'),
    partial_update=extend_schema(tags=[_ADMIN_TAG], summary='Qisman yangilash'),
    destroy=extend_schema(tags=[_ADMIN_TAG], summary='O\'chirish'),
)
class DestinationViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD:
      GET    /api/destinations/admin/
      POST   /api/destinations/admin/
      GET    /api/destinations/admin/{id}/
      PUT    /api/destinations/admin/{id}/
      PATCH  /api/destinations/admin/{id}/
      DELETE /api/destinations/admin/{id}/
    """

    queryset = Destination.objects.all()
    serializer_class = DestinationAdminSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        group     = self.request.query_params.get('group')
        is_active = self.request.query_params.get('is_active')
        if group:
            qs = qs.filter(group=group)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        return qs


# ── Client (foydalanuvchi) ────────────────────────────────────────────────────

@extend_schema(
    tags=[_CLIENT_TAG],
    summary='Destinatsiyalar ro\'yxati',
    parameters=[
        OpenApiParameter('group', str, description='popular | signature — guruh bo\'yicha filtr'),
    ],
    responses={200: DestinationClientSerializer(many=True)},
)
class DestinationListView(APIView):
    """GET /api/destinations/ — barcha aktiv destinatsiyalar."""

    permission_classes = [AllowAny]

    def get(self, request):
        qs = Destination.objects.filter(is_active=True)
        group = request.query_params.get('group')
        if group:
            qs = qs.filter(group=group)
        serializer = DestinationClientSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


@extend_schema(
    tags=[_CLIENT_TAG],
    summary='Destinatsiya tafsilotlari',
    responses={200: DestinationClientSerializer, 404: ErrorResponseSerializer},
)
class DestinationDetailView(APIView):
    """GET /api/destinations/{id}/ — bitta destinatsiya."""

    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            dest = Destination.objects.filter(is_active=True).get(pk=pk)
        except Destination.DoesNotExist:
            return Response({'error': 'Topilmadi'}, status=status.HTTP_404_NOT_FOUND)
        serializer = DestinationClientSerializer(dest, context={'request': request})
        return Response(serializer.data)
