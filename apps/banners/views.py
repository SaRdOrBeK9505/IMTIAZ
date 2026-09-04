"""Banners app views — admin va client endpointlari."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from apps.core.openapi_schemas import ErrorResponseSerializer
from apps.users.models import UserRole

from .models import Banner
from .serializers import BannerSerializer, BannerCreateSerializer, BannerUpdateSerializer

_ADMIN_TAG = 'Admin — Banners'
_CLIENT_TAG = 'Telegram Mini App — Banners'


class IsAdminUser(BasePermission):
    """Admin role tekshiruvi."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == UserRole.ADMIN


class BannerPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ─── Admin Views (himoyalangan) ───────────────────────────────────────────────

class AdminBannerListView(generics.ListCreateAPIView):
    """GET/POST /api/admin/banners/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = BannerPagination
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BannerCreateSerializer
        return BannerSerializer
    
    def get_queryset(self):
        """Admin uchun barcha bannerlar (isActive=false bo'lganlari ham)."""
        return Banner.objects.all().order_by('order', '-created_at')
    
    @extend_schema(
        tags=[_ADMIN_TAG],
        summary='Barcha bannerlar ro\'yxati (admin)',
        parameters=[
            OpenApiParameter('page', int, description='Sahifa raqami'),
            OpenApiParameter('page_size', int, description='Sahifa hajmi (default: 20, max: 100)'),
        ],
        responses={200: BannerSerializer(many=True), 403: ErrorResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        tags=[_ADMIN_TAG],
        summary='Yangi banner yaratish',
        request=BannerCreateSerializer,
        responses={201: BannerSerializer, 403: ErrorResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        banner = serializer.save()
        return Response(
            {'success': True, 'data': BannerSerializer(banner).data},
            status=status.HTTP_201_CREATED
        )


class AdminBannerDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/PATCH/DELETE /api/admin/banners/<id>/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Banner.objects.all()
    serializer_class = BannerSerializer
    
    @extend_schema(
        tags=[_ADMIN_TAG],
        summary='Bannerni id bo\'yicha olish (admin)',
        responses={200: BannerSerializer, 404: ErrorResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        tags=[_ADMIN_TAG],
        summary='Bannerni tahrirlash (to\'liq)',
        request=BannerUpdateSerializer,
        responses={200: BannerSerializer, 404: ErrorResponseSerializer},
    )
    def put(self, request, *args, **kwargs):
        serializer = BannerUpdateSerializer(self.get_object(), data=request.data)
        serializer.is_valid(raise_exception=True)
        banner = serializer.save()
        return Response({'success': True, 'data': BannerSerializer(banner).data})
    
    @extend_schema(
        tags=[_ADMIN_TAG],
        summary='Bannerni qisman tahrirlash',
        request=BannerUpdateSerializer,
        responses={200: BannerSerializer, 404: ErrorResponseSerializer},
    )
    def patch(self, request, *args, **kwargs):
        serializer = BannerUpdateSerializer(
            self.get_object(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        banner = serializer.save()
        return Response({'success': True, 'data': BannerSerializer(banner).data})
    
    @extend_schema(
        tags=[_ADMIN_TAG],
        summary='Bannerni o\'chirish',
        responses={200: OpenApiResponse(description='Banner o\'chirildi'), 404: ErrorResponseSerializer},
    )
    def delete(self, request, *args, **kwargs):
        try:
            banner = self.get_object()
            banner.delete()
            return Response({'success': True, 'message': 'Banner o\'chirildi.'})
        except Banner.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Banner topilmadi.'},
                status=status.HTTP_404_NOT_FOUND
            )


class AdminBannerUploadView(APIView):
    """POST /api/admin/banners/upload/ — rasm yuklash"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @extend_schema(
        tags=[_ADMIN_TAG],
        summary='Rasm yuklash',
        request=None,
        responses={200: OpenApiResponse(description='Rasm URL qaytarildi')},
    )
    def post(self, request):
        from django.core.files.uploadedfile import InMemoryUploadedFile
        
        if 'file' not in request.FILES:
            return Response(
                {'success': False, 'error': 'Fayl yuklanmadi.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        
        # Fayl formati tekshirish
        allowed_extensions = ['jpg', 'jpeg', 'png', 'webp']
        file_ext = file.name.split('.')[-1].lower()
        if file_ext not in allowed_extensions:
            return Response(
                {'success': False, 'error': f'Ruxsat etilgan formatlar: {", ".join(allowed_extensions)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Fayl hajmi tekshirish (5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if file.size > max_size:
            return Response(
                {'success': False, 'error': 'Fayl hajmi 5MB dan oshmasligi kerak.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Faylni saqlash (local storage)
        from django.core.files.storage import default_storage
        from django.utils import timezone
        import os
        
        filename = f"banners/{timezone.now().strftime('%Y%m%d_%H%M%S')}_{file.name}"
        filepath = default_storage.save(filename, file)
        file_url = default_storage.url(filepath)
        
        return Response({
            'success': True,
            'data': {
                'imageUrl': file_url,
                'filename': filename
            }
        })


# ─── Client Views (public) ───────────────────────────────────────────────────

class ClientBannerListView(generics.ListAPIView):
    """GET /api/banners/ — faol bannerlar ro'yxati"""
    permission_classes = [AllowAny]
    serializer_class = BannerSerializer
    pagination_class = None  # Barchasini ko'rsatish
    
    def get_queryset(self):
        """Faqat isActive=true bannerlar, order bo'yicha saralangan."""
        return Banner.objects.filter(is_active=True).order_by('order', '-created_at')
    
    @extend_schema(
        tags=[_CLIENT_TAG],
        summary='Faol bannerlar ro\'yxati (public)',
        responses={200: BannerSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return Response({
            'success': True,
            'data': BannerSerializer(self.get_queryset(), many=True).data
        })


class ClientBannerDetailView(generics.RetrieveAPIView):
    """GET /api/banners/<id>/ — bitta bannerni id bo'yicha olish"""
    permission_classes = [AllowAny]
    queryset = Banner.objects.filter(is_active=True)
    serializer_class = BannerSerializer
    
    @extend_schema(
        tags=[_CLIENT_TAG],
        summary='Bannerni id bo\'yicha olish (public)',
        responses={200: BannerSerializer, 404: ErrorResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        try:
            banner = self.get_object()
            return Response({'success': True, 'data': BannerSerializer(banner).data})
        except Banner.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Banner topilmadi.'},
                status=status.HTTP_404_NOT_FOUND
            )
