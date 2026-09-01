"""Background Music views."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi_schemas import ErrorResponseSerializer

from .models import BackgroundMusic
from .serializers import (
    BackgroundMusicSerializer,
    BackgroundMusicUpdateSerializer,
)

_ADMIN_TAG = 'Admin — Background Music'


@extend_schema_view(
    list=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Fon musiqalari ro\'yxati',
        description='Admin uchun barcha fon musiqalari.',
    ),
    create=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Yangi fon musiqasi yuklash',
        request=BackgroundMusicSerializer,
        responses={201: BackgroundMusicSerializer, 400: ErrorResponseSerializer},
    ),
    retrieve=extend_schema(tags=[_ADMIN_TAG], summary='Fon musiqasi tafsilotlari'),
    update=extend_schema(tags=[_ADMIN_TAG], summary='Fon musiqasini yangilash'),
    partial_update=extend_schema(tags=[_ADMIN_TAG], summary='Fon musiqasini qisman yangilash'),
    destroy=extend_schema(tags=[_ADMIN_TAG], summary='Fon musiqasini o\'chirish'),
)
class BackgroundMusicViewSet(viewsets.ModelViewSet):
    """Admin CRUD for background music."""
    
    queryset = BackgroundMusic.objects.all()
    serializer_class = BackgroundMusicSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        qs = super().get_queryset()
        mood = self.request.query_params.get('mood')
        if mood:
            qs = qs.filter(mood=mood)
        return qs
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """POST /api/admin/music/{id}/activate/ — Activate track."""
        music = self.get_object()
        music.activate()
        serializer = self.get_serializer(music)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """POST /api/admin/music/{id}/deactivate/ — Deactivate track."""
        music = self.get_object()
        music.deactivate()
        serializer = self.get_serializer(music)
        return Response(serializer.data)


@extend_schema(
    tags=[_ADMIN_TAG],
    summary='Hozirgi faol fon musiqasi',
    description='Hozir ijro etilayotgan fon musiqasini olish.',
    responses={
        200: BackgroundMusicSerializer,
        404: OpenApiResponse(description='Faol musiqasi yo\'q'),
    },
)
class ActiveMusicView(APIView):
    """GET /api/admin/music/active/ — Get currently active music."""
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        active_music = BackgroundMusic.get_active_track()
        if active_music:
            serializer = BackgroundMusicSerializer(active_music)
            return Response(serializer.data)
        return Response(
            {'message': 'No active music track'},
            status=status.HTTP_404_NOT_FOUND
        )


@extend_schema(
    tags=[_ADMIN_TAG],
    summary='Fon musiqasini boshqarish',
    description='Ovoz darajasini va faol holatini yangilash.',
    request=BackgroundMusicUpdateSerializer,
    responses={
        200: BackgroundMusicSerializer,
        404: ErrorResponseSerializer,
    },
)
class ControlMusicView(APIView):
    """PATCH /api/admin/music/{id}/control/ — Control music playback."""
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def patch(self, request, pk):
        try:
            music = BackgroundMusic.objects.get(pk=pk)
            serializer = BackgroundMusicUpdateSerializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            if 'volume' in serializer.validated_data:
                music.volume = serializer.validated_data['volume']
            
            if 'is_active' in serializer.validated_data:
                if serializer.validated_data['is_active']:
                    music.activate()
                else:
                    music.deactivate()
            
            music.save(update_fields=['volume', 'updated_at'])
            
            response_serializer = BackgroundMusicSerializer(music)
            return Response(response_serializer.data)
            
        except BackgroundMusic.DoesNotExist:
            return Response(
                {'error': 'Music track not found'},
                status=status.HTTP_404_NOT_FOUND
            )
