"""Restaurant Lead CRM views — acceptance/rejection workflow."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.core.authentication import CRMJWTAuthentication
from apps.core.openapi_schemas import ErrorResponseSerializer
from apps.core.permissions import IsRestaurantCRMUser
from apps.crm_core.mixins import RestaurantCRMViewSet

from .models import RestaurantBookingLead, RestaurantStaff
from .serializers import (
    RestaurantBookingLeadAcceptSerializer,
    RestaurantBookingLeadRejectSerializer,
    RestaurantBookingLeadSerializer,
    RestaurantBookingLeadUpdateTimeSerializer,
)

_LEAD_TAG = 'CRM Restaurant — Leads'


class IsRestaurantStaffPermission:
    """Custom permission — faqat RestaurantStaff bo'lganlar kirishi mumkin."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            RestaurantStaff.objects.get(user=request.user, is_active=True)
            return True
        except RestaurantStaff.DoesNotExist:
            return False


@extend_schema_view(
    list=extend_schema(
        tags=[_LEAD_TAG],
        summary='Restoran leadlari ro\'yxati',
        description='Faqat o\'z restoraniga tegishli leadlarni ko\'radi.',
    ),
    create=extend_schema(
        tags=[_LEAD_TAG],
        summary='Yangi lead yaratish',
        request=RestaurantBookingLeadSerializer,
        responses={201: RestaurantBookingLeadSerializer, 403: ErrorResponseSerializer},
    ),
    retrieve=extend_schema(tags=[_LEAD_TAG], summary='Lead tafsilotlari'),
    update=extend_schema(tags=[_LEAD_TAG], summary='Leadni yangilash'),
    partial_update=extend_schema(tags=[_LEAD_TAG], summary='Leadni qisman yangilash'),
    destroy=extend_schema(tags=[_LEAD_TAG], summary='Leadni o\'chirish'),
)
class RestaurantBookingLeadViewSet(RestaurantCRMViewSet):
    """RestaurantBookingLead ViewSet — faqat RestaurantStaff uchun."""
    
    queryset = RestaurantBookingLead.objects.select_related('restaurant', 'accepted_by')
    serializer_class = RestaurantBookingLeadSerializer
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser, IsRestaurantStaffPermission]
    authentication_classes = [CRMJWTAuthentication]
    
    def get_queryset(self):
        """Faqat o'z restoraniga tegishli leadlarni qaytarish."""
        if getattr(self, 'swagger_fake_view', False):
            return RestaurantBookingLead.objects.none()
        
        try:
            staff = RestaurantStaff.objects.get(user=self.request.user, is_active=True)
            return RestaurantBookingLead.objects.filter(restaurant=staff.restaurant).select_related(
                'restaurant', 'accepted_by'
            )
        except RestaurantStaff.DoesNotExist:
            return RestaurantBookingLead.objects.none()
    
    def perform_create(self, serializer):
        """Lead yaratganda restoranni avtomatik biriktirish."""
        try:
            staff = RestaurantStaff.objects.get(user=self.request.user, is_active=True)
            serializer.save(restaurant=staff.restaurant)
        except RestaurantStaff.DoesNotExist:
            raise PermissionDenied('Siz restoran xodimi emassiz.')


@extend_schema(
    tags=[_LEAD_TAG],
    summary='Leadni qabul qilish',
    request=RestaurantBookingLeadAcceptSerializer,
    responses={
        200: OpenApiResponse(description='Lead qabul qilindi'),
        400: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
    },
)
class RestaurantBookingLeadAcceptView(APIView):
    """PATCH /api/crm/restaurant/leads/{id}/accept/ — Leadni qabul qilish."""
    
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser, IsRestaurantStaffPermission]
    
    def patch(self, request, pk):
        try:
            lead = RestaurantBookingLead.objects.get(pk=pk)
            staff = RestaurantStaff.objects.get(user=request.user, is_active=True)
            
            # Xodim faqat o'z restoranining leadini qabul qilishi mumkin
            if lead.restaurant != staff.restaurant:
                raise PermissionDenied('Siz bu restoran leadini qabul qila olmaysiz.')
            
            serializer = RestaurantBookingLeadAcceptSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            lead.accept(staff)
            
            # Telegram notification yuborish (integrations orqali)
            from apps.notifications.tasks import send_telegram_notification
            send_telegram_notification.delay(
                chat_id=lead.customer_phone,
                message=f"✅ Sizning restoran so'rovingiz qabul qilindi! "
                       f"Restoran: {lead.restaurant.name}, Vaqt: {lead.preferred_time}"
            )
            
            return Response({
                'status': 'accepted',
                'lead_id': str(lead.id),
                'accepted_by': staff.user.get_full_name(),
                'accepted_at': lead.accepted_at.isoformat()
            })
            
        except RestaurantBookingLead.DoesNotExist:
            return Response(
                {'error': 'Lead topilmadi'},
                status=status.HTTP_404_NOT_FOUND
            )
        except RestaurantStaff.DoesNotExist:
            return Response(
                {'error': 'Restoran xodimi topilmadi'},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema(
    tags=[_LEAD_TAG],
    summary='Leadni rad etish',
    request=RestaurantBookingLeadRejectSerializer,
    responses={
        200: OpenApiResponse(description='Lead rad etildi'),
        400: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
    },
)
class RestaurantBookingLeadRejectView(APIView):
    """PATCH /api/crm/restaurant/leads/{id}/reject/ — Leadni rad etish."""
    
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser, IsRestaurantStaffPermission]
    
    def patch(self, request, pk):
        try:
            lead = RestaurantBookingLead.objects.get(pk=pk)
            staff = RestaurantStaff.objects.get(user=request.user, is_active=True)
            
            # Xodim faqat o'z restoranining leadini rad etishi mumkin
            if lead.restaurant != staff.restaurant:
                raise PermissionDenied('Siz bu restoran leadini rad eta olmaysiz.')
            
            serializer = RestaurantBookingLeadRejectSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            reason = serializer.validated_data['reason']
            lead.reject(reason)
            
            # Telegram notification yuborish
            from apps.notifications.tasks import send_telegram_notification
            send_telegram_notification.delay(
                chat_id=lead.customer_phone,
                message=f"❌ Sizning restoran so'rovingiz rad etildi. Sabab: {reason}"
            )
            
            return Response({
                'status': 'rejected',
                'lead_id': str(lead.id),
                'rejection_reason': reason
            })
            
        except RestaurantBookingLead.DoesNotExist:
            return Response(
                {'error': 'Lead topilmadi'},
                status=status.HTTP_404_NOT_FOUND
            )
        except RestaurantStaff.DoesNotExist:
            return Response(
                {'error': 'Restoran xodimi topilmadi'},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema(
    tags=[_LEAD_TAG],
    summary='Lead vaqtini yangilash (muzokara)',
    request=RestaurantBookingLeadUpdateTimeSerializer,
    responses={
        200: OpenApiResponse(description='Vaqt yangilandi'),
        400: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
        404: ErrorResponseSerializer,
    },
)
class RestaurantBookingLeadUpdateTimeView(APIView):
    """PATCH /api/crm/restaurant/leads/{id}/update-time/ — Lead vaqtini yangilash."""
    
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser, IsRestaurantStaffPermission]
    
    def patch(self, request, pk):
        try:
            lead = RestaurantBookingLead.objects.get(pk=pk)
            staff = RestaurantStaff.objects.get(user=request.user, is_active=True)
            
            # Xodim faqat o'z restoranining leadini yangilashi mumkin
            if lead.restaurant != staff.restaurant:
                raise PermissionDenied('Siz bu restoran leadini yangilay olmaysiz.')
            
            serializer = RestaurantBookingLeadUpdateTimeSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            new_time = serializer.validated_data['actual_time']
            lead.update_actual_time(new_time)
            
            # Telegram notification yuborish
            from apps.notifications.tasks import send_telegram_notification
            send_telegram_notification.delay(
                chat_id=lead.customer_phone,
                message=f"⏰ Restoran vaqti yangilandi: {new_time}. Tasdiqlangan vaqt: {lead.actual_time}"
            )
            
            return Response({
                'status': 'confirmed',
                'lead_id': str(lead.id),
                'actual_time': lead.actual_time.strftime('%H:%M')
            })
            
        except RestaurantBookingLead.DoesNotExist:
            return Response(
                {'error': 'Lead topilmadi'},
                status=status.HTTP_404_NOT_FOUND
            )
        except RestaurantStaff.DoesNotExist:
            return Response(
                {'error': 'Restoran xodimi topilmadi'},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
