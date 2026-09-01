"""App Settings views."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi_schemas import ErrorResponseSerializer

from .models import AppSetting
from .serializers import AppSettingSerializer, PublicAppSettingSerializer

_ADMIN_TAG = 'Admin — Settings'
_PUBLIC_TAG = 'Public — Settings'


@extend_schema_view(
    list=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Barcha sozlamalar (admin)',
        description='Admin uchun barcha ilova sozlamalari.',
    ),
    create=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Yangi sozlamani yaratish',
        request=AppSettingSerializer,
        responses={201: AppSettingSerializer, 400: ErrorResponseSerializer},
    ),
    retrieve=extend_schema(tags=[_ADMIN_TAG], summary='Sozlamani ko\'rish'),
    update=extend_schema(tags=[_ADMIN_TAG], summary='Sozlamani yangilash'),
    partial_update=extend_schema(tags=[_ADMIN_TAG], summary='Sozlamani qisman yangilash'),
    destroy=extend_schema(tags=[_ADMIN_TAG], summary='Sozlamani o\'chirish'),
)
class AppSettingViewSet(viewsets.ModelViewSet):
    """Admin CRUD for app settings."""
    
    queryset = AppSetting.objects.all()
    serializer_class = AppSettingSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def ai_assistant_name(self, request):
        """GET /api/admin/settings/ai_assistant_name/ — Get AI assistant name."""
        name = AppSetting.get_ai_assistant_name()
        return Response({'ai_assistant_name': name})
    
    @action(detail=False, methods=['post'])
    def set_ai_assistant_name(self, request):
        """POST /api/admin/settings/set_ai_assistant_name/ — Set AI assistant name."""
        name = request.data.get('name')
        if not name:
            return Response(
                {'error': 'Name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        AppSetting.set_ai_assistant_name(name)
        return Response({'ai_assistant_name': name})


@extend_schema(
    tags=[_PUBLIC_TAG],
    summary='Ommaviy sozlamalar',
    description='Ommaviy ilova sozlamalari (AI assistant name, etc.).',
    responses={200: PublicAppSettingSerializer(many=True)},
)
class PublicSettingsView(APIView):
    """GET /api/settings/public/ — Get public app settings."""
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        settings = AppSetting.objects.filter(is_public=True)
        serializer = PublicAppSettingSerializer(settings, many=True)
        
        # Convert to dict for easier access
        settings_dict = {s['key']: s for s in serializer.data}
        
        # Always include AI assistant name
        ai_name = AppSetting.get_ai_assistant_name()
        settings_dict['ai_assistant_name'] = {
            'key': 'ai_assistant_name',
            'value': ai_name,
            'description': 'AI assistant display name'
        }
        
        return Response(settings_dict)
