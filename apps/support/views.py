"""User Inquiry/Support views."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi_schemas import ErrorResponseSerializer

from .models import UserInquiry
from .serializers import (
    AdminInquiryResolveSerializer,
    AdminInquiryResponseSerializer,
    UserInquiryCreateSerializer,
    UserInquirySerializer,
)

_USER_TAG = 'User — Support'
_ADMIN_TAG = 'Admin — Support'


@extend_schema(
    tags=[_USER_TAG],
    summary='Mening so\'rovlari',
    description='Foydalanuvchining barcha so\'rovlari.',
    responses={200: UserInquirySerializer(many=True), 401: ErrorResponseSerializer},
)
class UserInquiryListView(APIView):
    """GET /api/support/inquiries/ — List user's inquiries."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        inquiries = UserInquiry.get_user_inquiries(request.user)
        serializer = UserInquirySerializer(inquiries, many=True)
        return Response(serializer.data)


@extend_schema(
    tags=[_USER_TAG],
    summary='So\'rov yaratish',
    description='Yangi so\'rov yuborish.',
    request=UserInquiryCreateSerializer,
    responses={
        201: UserInquirySerializer,
        400: ErrorResponseSerializer,
    },
)
class CreateInquiryView(APIView):
    """POST /api/support/inquiries/ — Create new inquiry."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = UserInquiryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        inquiry = UserInquiry.objects.create(
            user=request.user,
            **serializer.validated_data
        )
        
        # Send notification to admin
        from apps.notifications.tasks import send_telegram_notification
        send_telegram_notification.delay(
            chat_id='ADMIN_CHAT_ID',  # Should be configured
            message=f"🆕 Yangi so'rov!\n\nFoydalanuvchi: {request.user.get_full_name()}\nMavzu: {inquiry.subject}\nKategoriya: {inquiry.get_category_display()}\nPrioritet: {inquiry.get_priority_display()}"
        )
        
        response_serializer = UserInquirySerializer(inquiry)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=[_USER_TAG],
    summary='So\'rov tafsilotlari',
    description='So\'rov tafsilotlarini ko\'rish.',
    responses={
        200: UserInquirySerializer,
        404: ErrorResponseSerializer,
    },
)
class InquiryDetailView(APIView):
    """GET /api/support/inquiries/{id}/ — Get inquiry details."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        try:
            inquiry = UserInquiry.objects.get(pk=pk, user=request.user)
            serializer = UserInquirySerializer(inquiry)
            return Response(serializer.data)
        except UserInquiry.DoesNotExist:
            return Response(
                {'error': 'So\'rov topilmadi'},
                status=status.HTTP_404_NOT_FOUND
            )


@extend_schema_view(
    list=extend_schema(
        tags=[_ADMIN_TAG],
        summary='Barcha so\'rovlari (admin)',
        description='Admin uchun barcha so\'rovlari.',
    ),
    retrieve=extend_schema(tags=[_ADMIN_TAG], summary='So\'rov tafsilotlari (admin)'),
)
class AdminInquiryViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin viewset for inquiries."""
    
    queryset = UserInquiry.objects.select_related('user', 'responded_by')
    serializer_class = UserInquirySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        category = self.request.query_params.get('category')
        priority = self.request.query_params.get('priority')
        
        if status_filter:
            qs = qs.filter(status=status_filter)
        if category:
            qs = qs.filter(category=category)
        if priority:
            qs = qs.filter(priority=priority)
        
        return qs.order_by('-priority', '-created_at')
    
    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        """POST /api/admin/support/inquiries/{id}/respond/ — Respond to inquiry."""
        inquiry = self.get_object()
        serializer = AdminInquiryResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        inquiry.respond(
            admin_user=request.user,
            response=serializer.validated_data['response']
        )
        
        if serializer.validated_data.get('status'):
            inquiry.status = serializer.validated_data['status']
            inquiry.save(update_fields=['status', 'updated_at'])
        
        response_serializer = self.get_serializer(inquiry)
        return Response(response_serializer.data)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """POST /api/admin/support/inquiries/{id}/resolve/ — Resolve inquiry."""
        inquiry = self.get_object()
        serializer = AdminInquiryResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        inquiry.resolve(serializer.validated_data.get('resolution_notes', ''))
        
        response_serializer = self.get_serializer(inquiry)
        return Response(response_serializer.data)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """POST /api/admin/support/inquiries/{id}/close/ — Close inquiry."""
        inquiry = self.get_object()
        inquiry.close()
        
        response_serializer = self.get_serializer(inquiry)
        return Response(response_serializer.data)
    
    @action(detail=False, methods=['get'])
    def open(self, request):
        """GET /api/admin/support/inquiries/open/ — Get open inquiries."""
        open_inquiries = UserInquiry.get_open_inquiries()
        serializer = self.get_serializer(open_inquiries, many=True)
        return Response(serializer.data)
