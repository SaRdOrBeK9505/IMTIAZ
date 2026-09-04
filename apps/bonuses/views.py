"""Bonuses app views — BonusCategory shablon boshqaruvi + QRCode orqali nashr/tayinlash."""

from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi_schemas import ErrorResponseSerializer
from apps.qr_codes.models import QRCode
from apps.qr_codes.serializers import QRCodePublicSerializer  # user-facing serializer
from apps.qr_codes.services import QRGeneratorService

from .models import BonusCategory
from .serializers import BonusCategorySerializer, BonusPublishSerializer, BonusAssignSerializer

User = get_user_model()

_ADMIN_TAG = 'Admin — Bonus shablonlari'
_USER_TAG = 'Client — Mening bonuslarim'


@extend_schema_view(
    list=extend_schema(tags=[_ADMIN_TAG]), retrieve=extend_schema(tags=[_ADMIN_TAG]),
    create=extend_schema(tags=[_ADMIN_TAG]), update=extend_schema(tags=[_ADMIN_TAG]),
    partial_update=extend_schema(tags=[_ADMIN_TAG]), destroy=extend_schema(tags=[_ADMIN_TAG]),
)
class BonusCategoryViewSet(viewsets.ModelViewSet):
    """Admin — bonus shablonlarini CRUD qilish. Bu hali hech kimga QR bermaydi,
    faqat 'e'lon matni' sifatida turadi. Haqiqiy QR yaratish uchun /publish/ yoki /assign/ chaqiriladi."""

    queryset = BonusCategory.objects.all()
    serializer_class = BonusCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        service_type = self.request.query_params.get('service_type')
        if service_type:
            qs = qs.filter(service_type=service_type)
        return qs

    @extend_schema(
        tags=[_ADMIN_TAG],
        summary="Shablonni OMMAVIY QR kampaniya sifatida e'lon qilish",
        description="Bu shablondan bitta QRCode yaratadi (assigned_user=None) — istalgan "
                    "mijoz ilova/botda ko'rib, skanerlab foydalana oladi.",
        request=BonusPublishSerializer,
        responses={201: QRCodePublicSerializer, 400: ErrorResponseSerializer},
    )
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        category = self.get_object()
        serializer = BonusPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization_id = serializer.validated_data.get('organization_id')  # None → IMTIAZ platforma darajasi

        qr = QRCode.objects.create(
            organization_id=organization_id,
            source_template=category,
            assigned_user=None,
            title=category.name,
            description=category.description,
            qr_type='discount_percent' if category.discount_percentage else 'discount_fixed',
            discount_value=category.discount_percentage or category.discount_amount or 0,
            minimum_order_amount=category.min_purchase,
            applicable_services=[category.service_type],
            service_type=category.service_type,
            max_total_uses=category.max_usage_count,
            max_uses_per_user=1,
            valid_from=category.valid_from,
            valid_until=category.valid_until,
            is_active=category.is_active,
            created_by=request.user,
        )
        QRGeneratorService.generate_qr_image(qr)
        return Response(QRCodePublicSerializer(qr).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=[_ADMIN_TAG],
        summary="Shablonni tanlangan foydalanuvchilarga SHAXSIY vaucher sifatida tayinlash",
        description="Har bir user_id uchun ALOHIDA, noyob kodli QRCode yaratadi (assigned_user=<shu foydalanuvchi>).",
        request=BonusAssignSerializer,
        responses={201: QRCodePublicSerializer(many=True), 400: ErrorResponseSerializer},
    )
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        category = self.get_object()
        serializer = BonusAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_ids = serializer.validated_data['user_ids']

        users = User.objects.filter(id__in=user_ids)
        if users.count() != len(set(user_ids)):
            return Response(
                {'error': "Ba'zi user_id'lar topilmadi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        for user in users:
            qr = QRCode.objects.create(
                organization=None,
                source_template=category,
                assigned_user=user,
                title=category.name,
                description=category.description,
                qr_type='discount_percent' if category.discount_percentage else 'discount_fixed',
                discount_value=category.discount_percentage or category.discount_amount or 0,
                minimum_order_amount=category.min_purchase,
                applicable_services=[category.service_type],
                service_type=category.service_type,
                max_total_uses=1,
                max_uses_per_user=1,
                valid_from=category.valid_from,
                valid_until=category.valid_until,
                is_active=category.is_active,
                created_by=request.user,
            )
            QRGeneratorService.generate_qr_image(qr)
            created.append(qr)

        return Response(QRCodePublicSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=[_USER_TAG],
    summary='Mening bonuslarim — shaxsiy vaucherlar + ochiq kampaniyalar',
    description='Foydalanuvchiga tayinlangan barcha shaxsiy vaucherlar VA hozir amal '
                'qilayotgan ommaviy (assigned_user=None) kampaniyalar — bitta ro\'yxatda.',
    responses={200: QRCodePublicSerializer(many=True), 401: ErrorResponseSerializer},
)
class MyBonusesView(APIView):
    """GET /api/bonuses/ — birlashtirilgan ro'yxat."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q

        service_type = request.query_params.get('service_type')
        qs = QRCode.objects.filter(
            Q(assigned_user=request.user) | Q(assigned_user__isnull=True),
            is_active=True,
        ).select_related('organization', 'source_template')
        if service_type:
            qs = qs.filter(Q(service_type=service_type) | Q(service_type='all'))

        serializer = QRCodePublicSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)
