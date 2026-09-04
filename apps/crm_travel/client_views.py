"""Tour mijozlari tarixi — tur kompaniyasi CRM paneli."""

from __future__ import annotations

from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from apps.core.authentication import CRMJWTAuthentication
from apps.core.permissions import IsTourCRMUser
from apps.booking.models import Booking, BookingStatus, ServiceType
from apps.users.models import User

_TAG = 'CRM — Travel Clients'


class ClientPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class TourClientQueryMixin:
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTourCRMUser]

    def get_client_queryset(self):
        organization = self.request.user.organization
        if not organization:
            return User.objects.none()

        # Get users who have tour bookings with this organization
        user_ids = Booking.objects.filter(
            service_type=ServiceType.TOUR,
            tour_detail__package__organization=organization,
        ).values_list('user_id', flat=True).distinct()

        qs = User.objects.filter(id__in=user_ids).order_by('-created_at')

        if q := self.request.query_params.get('search'):
            qs = qs.filter(
                models.Q(full_name__icontains=q)
                | models.Q(phone__icontains=q)
            )
        return qs


class TourClientListView(TourClientQueryMixin, generics.ListAPIView):
    """GET /api/crm/tour/clients/ — Mijozlar ro'yxati"""
    
    @extend_schema(
        tags=[_TAG],
        summary='Tur mijozlari ro\'yxati',
        parameters=[
            OpenApiParameter('page', int, description='Sahifa raqami'),
            OpenApiParameter('page_size', int, description='Sahifa hajmi (default: 10, max: 100)'),
            OpenApiParameter('search', str, required=False),
        ],
        responses={200: OpenApiResponse(description='Mijozlar ro\'yxati')},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return User.objects.none()
        return self.get_client_queryset()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        
        # Calculate total purchases for each client
        organization = request.user.organization
        client_data = []
        
        for user in (page if page is not None else queryset):
            purchase_count = Booking.objects.filter(
                user=user,
                service_type=ServiceType.TOUR,
                tour_detail__package__organization=organization,
            ).count()
            
            client_data.append({
                'id': str(user.id),
                'full_name': user.full_name,
                'phone': user.phone,
                'email': user.email,
                'total_purchases': purchase_count,
            })
        
        if page is not None:
            return self.get_paginated_response(client_data)
        return Response(client_data)


class TourClientDetailView(TourClientQueryMixin, APIView):
    """GET /api/crm/tour/clients/<id>/ — Bitta mijoz ma'lumotlari"""
    
    @extend_schema(
        tags=[_TAG],
        summary='Mijoz tafsilotlari',
        responses={200: OpenApiResponse(description='Mijoz ma\'lumotlari')},
    )
    def get(self, request, pk):
        organization = self.request.user.organization
        if not organization:
            return Response({'message': 'Tashkilot topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            user = self.get_client_queryset().get(pk=pk)
        except User.DoesNotExist:
            return Response({'message': 'Mijoz topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        
        purchase_count = Booking.objects.filter(
            user=user,
            service_type=ServiceType.TOUR,
            tour_detail__package__organization=organization,
        ).count()
        
        return Response({
            'id': str(user.id),
            'full_name': user.full_name,
            'phone': user.phone,
            'email': user.email,
            'total_purchases': purchase_count,
        })


class TourClientPurchasesView(TourClientQueryMixin, APIView):
    """GET /api/crm/tour/clients/<id>/purchases/ — Mijozning xaridlar tarixi"""
    
    @extend_schema(
        tags=[_TAG],
        summary='Mijozning xaridlar tarixi',
        parameters=[
            OpenApiParameter('page', int, description='Sahifa raqami'),
            OpenApiParameter('page_size', int, description='Sahifa hajmi (default: 10, max: 100)'),
        ],
        responses={200: OpenApiResponse(description='Xaridlar tarixi')},
    )
    def get(self, request, pk):
        organization = self.request.user.organization
        if not organization:
            return Response({'message': 'Tashkilot topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            user = self.get_client_queryset().get(pk=pk)
        except User.DoesNotExist:
            return Response({'message': 'Mijoz topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get tour bookings for this client
        bookings = Booking.objects.filter(
            user=user,
            service_type=ServiceType.TOUR,
            tour_detail__package__organization=organization,
        ).select_related('tour_detail__package').order_by('-created_at')
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 10)), 100)
        
        from django.core.paginator import Paginator
        paginator = Paginator(bookings, page_size)
        page_obj = paginator.get_page(page)
        
        purchases = []
        for booking in page_obj:
            tour_detail = booking.tour_detail
            package = tour_detail.package if tour_detail else None
            
            purchases.append({
                'id': str(booking.id),
                'tour_name': package.title if package else 'Noma\'lum',
                'destination': package.destination if package else 'Noma\'lum',
                'start_date': str(tour_detail.start_date) if tour_detail and tour_detail.start_date else None,
                'end_date': str(tour_detail.end_date) if tour_detail and tour_detail.end_date else None,
                'people_count': tour_detail.passengers if tour_detail else 0,
                'price': str(booking.final_price),
                'operator': booking.created_by.get_full_name() if booking.created_by else 'Admin',
                'created_at': booking.created_at.strftime('%Y-%m-%d') if booking.created_at else None,
                'voucher_url': f'/api/crm/tour/clients/{pk}/voucher/{booking.id}' if booking.status == BookingStatus.CONFIRMED else None,
            })
        
        return Response({
            'results': purchases,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        })
