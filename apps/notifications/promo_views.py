"""Promo discount views — CRM staff tomonidan mijozlarga chegirma yuborish."""

from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from apps.core.authentication import CRMJWTAuthentication
from apps.core.permissions import IsRestaurantCRMUser, IsTourCRMUser
from apps.users.models import User

from .models import PromoDiscount

_PROMO_TAG = 'CRM — Promo Discounts'


class PromoPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class PromoDiscountQueryMixin:
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        organization = self.request.user.organization
        if not organization:
            return PromoDiscount.objects.none()
        
        qs = PromoDiscount.objects.filter(organization=organization).select_related('created_by')
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        
        # Search by phone or name
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                customer_phone__icontains=search
            ) | qs.filter(
                customer_name__icontains=search
            )
        
        return qs.order_by('-created_at')


class PromoDiscountListView(PromoDiscountQueryMixin, generics.ListCreateAPIView):
    """GET/POST /api/crm/promo-discounts/"""
    
    @extend_schema(
        tags=[_PROMO_TAG],
        summary='Chegirma takliflari ro\'yxati',
        parameters=[
            OpenApiParameter('page', int, description='Sahifa raqami'),
            OpenApiParameter('page_size', int, description='Sahifa hajmi (default: 20, max: 100)'),
            OpenApiParameter('status', str, description='Filter by status: active|expired|cancelled'),
            OpenApiParameter('search', str, description='Qidiruv (telefon yoki ism)'),
        ],
        responses={200: OpenApiResponse(description='Chegirma takliflari')},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return PromoDiscount.objects.none()
        return super().get_queryset()
    
    @extend_schema(
        tags=[_PROMO_TAG],
        summary='Yangi chegirma taklifi yaratish',
        request=None,
        responses={201: OpenApiResponse(description='Chegirma yaratildi')},
    )
    def post(self, request, *args, **kwargs):
        organization = request.user.organization
        if not organization:
            return Response({'message': 'Tashkilot topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        
        data = request.data
        
        # Find user by phone
        phone = data.get('customer_phone', '').strip()
        user = User.objects.filter(phone=phone).first()
        
        if not user:
            return Response({'message': 'Mijoz topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        
        # Create promo discount
        promo = PromoDiscount.objects.create(
            organization=organization,
            created_by=request.user,
            customer_phone=phone,
            customer_name=data.get('customer_name', user.full_name),
            discount_type=data.get('discount_type', 'fixed'),
            discount_value=data.get('discount_value'),
            title=data.get('title', 'Chegirma taklifi'),
            description=data.get('description', ''),
            valid_until=data.get('valid_until'),
        )
        
        # Send notification
        from .tasks import send_promo_discount_notification
        send_promo_discount_notification.delay(promo.id)
        
        return Response({
            'id': str(promo.id),
            'customer_name': promo.customer_name,
            'customer_phone': promo.customer_phone,
            'discount_type': promo.discount_type,
            'discount_value': str(promo.discount_value),
            'title': promo.title,
            'status': promo.status,
        }, status=status.HTTP_201_CREATED)


class PromoDiscountDetailView(PromoDiscountQueryMixin, APIView):
    """GET/PATCH/DELETE /api/crm/promo-discounts/<id>/"""
    
    @extend_schema(
        tags=[_PROMO_TAG],
        summary='Chegirma taklifi tafsilotlari',
        responses={200: OpenApiResponse(description='Chegirma tafsilotlari')},
    )
    def get(self, request, pk):
        qs = self.get_queryset()
        try:
            promo = qs.get(pk=pk)
        except PromoDiscount.DoesNotExist:
            return Response({'message': 'Chegirma topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'id': str(promo.id),
            'customer_name': promo.customer_name,
            'customer_phone': promo.customer_phone,
            'discount_type': promo.discount_type,
            'discount_value': str(promo.discount_value),
            'title': promo.title,
            'description': promo.description,
            'valid_until': promo.valid_until.isoformat() if promo.valid_until else None,
            'status': promo.status,
            'is_sent': promo.is_sent,
            'sent_at': promo.sent_at.isoformat() if promo.sent_at else None,
            'created_at': promo.created_at.isoformat(),
        })
    
    @extend_schema(
        tags=[_PROMO_TAG],
        summary='Chegirma taklifini bekor qilish',
        responses={200: OpenApiResponse(description='Chegirma bekor qilindi')},
    )
    def delete(self, request, pk):
        qs = self.get_queryset()
        try:
            promo = qs.get(pk=pk)
        except PromoDiscount.DoesNotExist:
            return Response({'message': 'Chegirma topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        
        promo.status = PromoDiscount.Status.CANCELLED
        promo.save(update_fields=['status', 'updated_at'])
        
        return Response({'message': 'Chegirma bekor qilindi.'})
