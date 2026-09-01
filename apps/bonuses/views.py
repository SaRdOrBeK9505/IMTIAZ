"""Bonuses app views."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi_schemas import ErrorResponseSerializer

from .models import BonusCategory, UserBonus
from .serializers import (
    BonusCategorySerializer,
    BonusQRScanSerializer,
    BonusValidationResponseSerializer,
    UserBonusSerializer,
)
from .services import QRCodeService

_ADMIN_TAG = 'Admin — Bonuses'
_USER_TAG = 'User — Bonuses'


@extend_schema_view(
    list=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Bonus kategoriyalari ro\'yxati',
        description='Admin uchun barcha bonus kategoriyalari.',
    ),
    create=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Yangi bonus kategoriyasi yaratish',
        request=BonusCategorySerializer,
        responses={201: BonusCategorySerializer, 400: ErrorResponseSerializer},
    ),
    retrieve=extend_schema(tags=[_ADMIN_TAG], summary='Bonus kategoriyasi tafsilotlari'),
    update=extend_schema(tags=[_ADMIN_TAG], summary='Bonus kategoriyasini yangilash'),
    partial_update=extend_schema(tags=[_ADMIN_TAG], summary='Bonus kategoriyasini qisman yangilash'),
    destroy=extend_schema(tags=[_ADMIN_TAG], summary='Bonus kategoriyasini o\'chirish'),
)
class BonusCategoryViewSet(viewsets.ModelViewSet):
    """Admin CRUD for bonus categories."""
    
    queryset = BonusCategory.objects.all()
    serializer_class = BonusCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        qs = super().get_queryset()
        service_type = self.request.query_params.get('service_type')
        if service_type:
            qs = qs.filter(service_type=service_type)
        return qs
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """POST /api/admin/bonuses/categories/{id}/activate/ — Activate bonus."""
        bonus = self.get_object()
        bonus.is_active = True
        bonus.save(update_fields=['is_active', 'updated_at'])
        return Response({'status': 'activated'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """POST /api/admin/bonuses/categories/{id}/deactivate/ — Deactivate bonus."""
        bonus = self.get_object()
        bonus.is_active = False
        bonus.save(update_fields=['is_active', 'updated_at'])
        return Response({'status': 'deactivated'})


@extend_schema(
    tags=[_USER_TAG],
    summary='Mening bonuslarim',
    description='Foydalanuvchining barcha bonuslari.',
    responses={200: UserBonusSerializer(many=True), 401: ErrorResponseSerializer},
)
class UserBonusListView(APIView):
    """GET /api/bonuses/ — List user's bonuses."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        bonuses = UserBonus.objects.filter(user=request.user).select_related('bonus_category')
        serializer = UserBonusSerializer(bonuses, many=True)
        return Response(serializer.data)


@extend_schema(
    tags=[_USER_TAG],
    summary='Bonuslar bo\'yicha filtrlash',
    description='Xizmat turiga qarab bonuslarni filtrlash.',
    responses={200: UserBonusSerializer(many=True), 401: ErrorResponseSerializer},
)
class BonusByCategoryView(APIView):
    """GET /api/bonuses/by-category/{service_type}/ — Filter bonuses by service type."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, service_type):
        valid_types = [choice[0] for choice in BonusCategory.ServiceType.choices]
        if service_type not in valid_types:
            return Response(
                {'error': f'Noto\'g\'ri service_type. Quyidagilardan biri bo\'lishi kerak: {valid_types}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bonuses = UserBonus.objects.filter(
            user=request.user,
            bonus_category__service_type=service_type
        ).select_related('bonus_category')
        
        serializer = UserBonusSerializer(bonuses, many=True)
        return Response(serializer.data)


@extend_schema(
    tags=[_USER_TAG],
    summary='Bonus QR kodini yaratish',
    description='Bonus uchun QR kod generatsiya qilish.',
    responses={200: UserBonusSerializer, 404: ErrorResponseSerializer},
)
class GenerateQRCodeView(APIView):
    """GET /api/bonuses/{id}/qr/ — Generate QR code for bonus."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        try:
            bonus = UserBonus.objects.get(pk=pk, user=request.user)
            
            if not bonus.qr_code:
                bonus.generate_qr_code()
            
            serializer = UserBonusSerializer(bonus)
            return Response(serializer.data)
            
        except UserBonus.DoesNotExist:
            return Response(
                {'error': 'Bonus topilmadi'},
                status=status.HTTP_404_NOT_FOUND
            )


@extend_schema(
    tags=[_USER_TAG],
    summary='Bonusni oldindan tekshirish (pre-check)',
    description='Bonus muddati tugaganmi yoki ishlatilganmi - checkout oldin tekshirish.',
    responses={
        200: BonusValidationResponseSerializer,
        400: BonusValidationResponseSerializer,
        404: ErrorResponseSerializer,
    },
)
class ValidateBonusView(APIView):
    """GET /api/bonuses/{id}/validate/ — Pre-check bonus validity before checkout."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Check if bonus is valid without marking it as used."""
        try:
            user_bonus = UserBonus.objects.get(pk=pk, user=request.user)
            
            # Check if already used
            if user_bonus.is_used:
                return Response({
                    'valid': False,
                    'error': 'Bu bonus allaqachon ishlatilgan',
                    'used_at': user_bonus.used_at.isoformat() if user_bonus.used_at else None,
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if bonus category is valid
            category = user_bonus.bonus_category
            if not category.is_valid():
                reason = self._get_invalid_reason(category)
                return Response({
                    'valid': False,
                    'error': reason,
                    'category_valid': category.is_valid(),
                    'category_active': category.is_active,
                    'valid_until': category.valid_until.isoformat() if category.valid_until else None,
                    'usage_count': category.usage_count,
                    'max_usage_count': category.max_usage_count,
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Bonus is valid
            return Response({
                'valid': True,
                'message': 'Bonus amal qiladi',
                'bonus': {
                    'id': user_bonus.id,
                    'category': category.name,
                    'service_type': category.service_type,
                    'discount_percentage': category.discount_percentage,
                    'discount_amount': str(category.discount_amount) if category.discount_amount else None,
                    'min_purchase': str(category.min_purchase),
                    'valid_until': category.valid_until.isoformat() if category.valid_until else None,
                }
            })
            
        except UserBonus.DoesNotExist:
            return Response(
                {'valid': False, 'error': 'Bonus topilmadi'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def _get_invalid_reason(self, category) -> str:
        """Get detailed reason why bonus is invalid."""
        from django.utils import timezone
        now = timezone.now().date()
        
        if not category.is_active:
            return 'Bonus kategoriyasi faol emas'
        if category.valid_from and now < category.valid_from:
            return f'Bonus {category.valid_from.strftime("%d.%m.%Y")} dan boshlab amal qiladi'
        if category.valid_until and now > category.valid_until:
            return 'Bonus muddati tugagan'
        if category.max_usage_count and category.usage_count >= category.max_usage_count:
            return 'Bonus ishlatish limiti tugagan'
        return 'Bonus amal qilmaydi'


@extend_schema(
    tags=[_ADMIN_TAG],
    summary='QR kodni skanlash va qo\'llash',
    description='Admin/Staff tomonidan QR kod skanlash va bonusni qo\'llash.',
    request=BonusQRScanSerializer,
    responses={
        200: OpenApiResponse(description='Bonus qo\'llandi'),
        400: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
    },
)
class ScanBonusQRView(APIView):
    """POST /api/admin/bonus/scan/ — Scan and apply bonus QR code."""
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request):
        serializer = BonusQRScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        qr_code = serializer.validated_data['qr_code']
        
        # Check cache first
        cached_result = QRCodeService.get_cached_verification(qr_code)
        if cached_result:
            if not cached_result['valid']:
                return Response(
                    {'error': cached_result.get('error', 'QR code invalid')},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response({'message': 'QR code already verified', 'data': cached_result['data']})
        
        # Verify QR code
        verification = QRCodeService.verify_signed_payload(qr_code)
        
        # Cache result
        QRCodeService.cache_qr_verification(qr_code, verification)
        
        if not verification['valid']:
            return Response(
                {'error': verification.get('error', 'QR code invalid')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = verification['data']
        
        # Only process bonus type QR codes
        if data['entity_type'] != 'bonus':
            return Response(
                {'error': 'QR code is not a bonus type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get user bonus
            user_bonus = UserBonus.objects.get(
                id=data['entity_id'],
                user_id=data['user_id']
            )
            
            # Check if already used
            if user_bonus.is_used:
                return Response(
                    {'error': 'Bu bonus allaqachon ishlatilgan'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if bonus category is valid
            if not user_bonus.bonus_category.is_valid():
                return Response(
                    {'error': 'Bonus muddati tugagan yoki cheklangan'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mark as used
            user_bonus.mark_as_used()
            
            return Response({
                'message': 'Bonus muvaffaqiyatli qo\'llandi',
                'bonus': BonusCategorySerializer(user_bonus.bonus_category).data
            })
            
        except UserBonus.DoesNotExist:
            return Response(
                {'error': 'Bonus topilmadi'},
                status=status.HTTP_404_NOT_FOUND
            )
