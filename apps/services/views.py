"""
Services — Views.

Admin endpoints (IsAdminUser):
  ServiceIcon  → CRUD   /api/services/admin/icons/
  ServiceColor → CRUD   /api/services/admin/colors/
  Service      → CRUD   /api/services/admin/

Client endpoints (IsAuthenticated):
  ServiceIcon  → list, retrieve   /api/services/icons/
  ServiceColor → list, retrieve   /api/services/colors/
  Service      → list, retrieve   /api/services/
"""

from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi_schemas import ErrorResponseSerializer

from .models import Service, ServiceColor, ServiceIcon
from .serializers import (
    ServiceAdminSerializer,
    ServiceClientSerializer,
    ServiceColorAdminSerializer,
    ServiceColorClientSerializer,
    ServiceIconAdminSerializer,
    ServiceIconClientSerializer,
)

_ADMIN_TAG  = 'Admin — Services'
_CLIENT_TAG = 'App — Services'


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN — ServiceIcon
# ══════════════════════════════════════════════════════════════════════════════

@extend_schema_view(
    list=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Iconlar ro\'yxati (admin)',
        parameters=[OpenApiParameter('search', str, description='name yoki slug bo\'yicha qidiruv')],
    ),
    create=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Yangi icon qo\'shish',
        responses={201: ServiceIconAdminSerializer, 400: ErrorResponseSerializer},
    ),
    retrieve=extend_schema(tags=[_ADMIN_TAG], summary='Icon tafsilotlari'),
    update=extend_schema(tags=[_ADMIN_TAG], summary='Iconni to\'liq yangilash'),
    partial_update=extend_schema(tags=[_ADMIN_TAG], summary='Iconni qisman yangilash'),
    destroy=extend_schema(tags=[_ADMIN_TAG], summary='Iconni o\'chirish'),
)
class ServiceIconAdminViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD — ServiceIcon.

      GET    /api/services/admin/icons/
      POST   /api/services/admin/icons/
      GET    /api/services/admin/icons/{id}/
      PUT    /api/services/admin/icons/{id}/
      PATCH  /api/services/admin/icons/{id}/
      DELETE /api/services/admin/icons/{id}/
    """

    queryset = ServiceIcon.objects.all().order_by('name')
    serializer_class = ServiceIconAdminSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    search_fields = ['name', 'slug']


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN — ServiceColor
# ══════════════════════════════════════════════════════════════════════════════

@extend_schema_view(
    list=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Ranglar ro\'yxati (admin)',
        parameters=[OpenApiParameter('search', str, description='name yoki hex_code bo\'yicha qidiruv')],
    ),
    create=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Yangi rang qo\'shish',
        responses={201: ServiceColorAdminSerializer, 400: ErrorResponseSerializer},
    ),
    retrieve=extend_schema(tags=[_ADMIN_TAG], summary='Rang tafsilotlari'),
    update=extend_schema(tags=[_ADMIN_TAG], summary='Rangni to\'liq yangilash'),
    partial_update=extend_schema(tags=[_ADMIN_TAG], summary='Rangni qisman yangilash'),
    destroy=extend_schema(tags=[_ADMIN_TAG], summary='Rangni o\'chirish'),
)
class ServiceColorAdminViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD — ServiceColor.

      GET    /api/services/admin/colors/
      POST   /api/services/admin/colors/
      GET    /api/services/admin/colors/{id}/
      PUT    /api/services/admin/colors/{id}/
      PATCH  /api/services/admin/colors/{id}/
      DELETE /api/services/admin/colors/{id}/
    """

    queryset = ServiceColor.objects.all().order_by('name', 'hex_code')
    serializer_class = ServiceColorAdminSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    search_fields = ['name', 'hex_code']


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN — Service
# ══════════════════════════════════════════════════════════════════════════════

@extend_schema_view(
    list=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Xizmatlar ro\'yxati (admin)',
        parameters=[
            OpenApiParameter('is_active', bool, description='Aktiv/noaktiv filtr'),
            OpenApiParameter('search', str, description='name bo\'yicha qidiruv'),
        ],
    ),
    create=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Yangi xizmat qo\'shish',
        responses={201: ServiceAdminSerializer, 400: ErrorResponseSerializer},
    ),
    retrieve=extend_schema(tags=[_ADMIN_TAG], summary='Xizmat tafsilotlari'),
    update=extend_schema(tags=[_ADMIN_TAG], summary='Xizmatni to\'liq yangilash'),
    partial_update=extend_schema(tags=[_ADMIN_TAG], summary='Xizmatni qisman yangilash'),
    destroy=extend_schema(tags=[_ADMIN_TAG], summary='Xizmatni o\'chirish'),
)
class ServiceAdminViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD — Service.

      GET    /api/services/admin/
      POST   /api/services/admin/
      GET    /api/services/admin/{id}/
      PUT    /api/services/admin/{id}/
      PATCH  /api/services/admin/{id}/
      DELETE /api/services/admin/{id}/
    """

    queryset = (
        Service.objects
        .select_related('icon', 'color')
        .order_by('order', 'id')
    )
    serializer_class = ServiceAdminSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    search_fields = ['name', 'slug']

    def get_queryset(self):
        qs = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        return qs


# ══════════════════════════════════════════════════════════════════════════════
#  CLIENT — ServiceIcon (ro'yxat va bitta element)
# ══════════════════════════════════════════════════════════════════════════════

@extend_schema(
    tags=[_CLIENT_TAG],
    summary='Iconlar ro\'yxati',
    description='CRM panelda service yaratishda icon tanlash uchun.',
    responses={200: ServiceIconClientSerializer(many=True)},
)
class ServiceIconListView(APIView):
    """GET /api/services/icons/ — barcha iconlar."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        icons = ServiceIcon.objects.all().order_by('name')
        serializer = ServiceIconClientSerializer(
            icons, many=True, context={'request': request}
        )
        return Response(serializer.data)


@extend_schema(
    tags=[_CLIENT_TAG],
    summary='Icon tafsilotlari',
    responses={200: ServiceIconClientSerializer, 404: ErrorResponseSerializer},
)
class ServiceIconDetailView(APIView):
    """GET /api/services/icons/{id}/ — bitta icon."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            icon = ServiceIcon.objects.get(pk=pk)
        except ServiceIcon.DoesNotExist:
            return Response(
                {'error': 'Icon topilmadi'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ServiceIconClientSerializer(icon, context={'request': request})
        return Response(serializer.data)


# ══════════════════════════════════════════════════════════════════════════════
#  CLIENT — ServiceColor (ro'yxat va bitta element)
# ══════════════════════════════════════════════════════════════════════════════

@extend_schema(
    tags=[_CLIENT_TAG],
    summary='Ranglar ro\'yxati',
    description='CRM panelda service yaratishda rang tanlash uchun.',
    responses={200: ServiceColorClientSerializer(many=True)},
)
class ServiceColorListView(APIView):
    """GET /api/services/colors/ — barcha ranglar."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        colors = ServiceColor.objects.all().order_by('name', 'hex_code')
        serializer = ServiceColorClientSerializer(
            colors, many=True, context={'request': request}
        )
        return Response(serializer.data)


@extend_schema(
    tags=[_CLIENT_TAG],
    summary='Rang tafsilotlari',
    responses={200: ServiceColorClientSerializer, 404: ErrorResponseSerializer},
)
class ServiceColorDetailView(APIView):
    """GET /api/services/colors/{id}/ — bitta rang."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            color = ServiceColor.objects.get(pk=pk)
        except ServiceColor.DoesNotExist:
            return Response(
                {'error': 'Rang topilmadi'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ServiceColorClientSerializer(color, context={'request': request})
        return Response(serializer.data)


# ══════════════════════════════════════════════════════════════════════════════
#  CLIENT — Service (ro'yxat va bitta element)
# ══════════════════════════════════════════════════════════════════════════════

@extend_schema(
    tags=[_CLIENT_TAG],
    summary='Xizmatlar ro\'yxati',
    description='Foydalanuvchiga ko\'rsatiladigan aktiv xizmatlar.',
    responses={200: ServiceClientSerializer(many=True)},
)
class ServiceListView(APIView):
    """GET /api/services/ — barcha aktiv xizmatlar."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        services = (
            Service.objects
            .select_related('icon', 'color')
            .filter(is_active=True)
            .order_by('order', 'id')
        )
        serializer = ServiceClientSerializer(
            services, many=True, context={'request': request}
        )
        return Response(serializer.data)


@extend_schema(
    tags=[_CLIENT_TAG],
    summary='Xizmat tafsilotlari',
    responses={200: ServiceClientSerializer, 404: ErrorResponseSerializer},
)
class ServiceDetailView(APIView):
    """GET /api/services/{id}/ — bitta xizmat."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            service = (
                Service.objects
                .select_related('icon', 'color')
                .filter(is_active=True)
                .get(pk=pk)
            )
        except Service.DoesNotExist:
            return Response(
                {'error': 'Xizmat topilmadi'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ServiceClientSerializer(service, context={'request': request})
        return Response(serializer.data)
