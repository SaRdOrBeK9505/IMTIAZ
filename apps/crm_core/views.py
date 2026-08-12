"""CRM staff va dashboard view'lar — restoran va tur alohida."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.authentication import CRMJWTAuthentication
from apps.core.openapi_schemas import ErrorResponseSerializer, OwnerDashboardResponseSerializer
from apps.core.permissions import IsRestaurantOwner, IsTourOwner

from .mixins import OwnerDashboardMixin, RestaurantStaffManagementMixin, TourStaffManagementMixin
from .serializers import (
    BranchStaffCreateSerializer,
    BranchStaffListSerializer,
    BranchStaffUpdateSerializer,
)


class RestaurantStaffListCreateView(RestaurantStaffManagementMixin, APIView):
    """
    GET/POST /api/crm/restaurant/staff/
    Faqat owner_restaurant — o'z restoran kompaniyasiga xodim qo'shadi.
    Yangi xodim roli: restaurant_staff (CRM login orqali kiradi).
    """
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantOwner]

    @extend_schema(
        tags=['CRM Restaurant — Staff'],
        summary='Restoran xodimlari ro\'yxati',
        responses={200: BranchStaffListSerializer(many=True), 403: ErrorResponseSerializer},
    )
    def get(self, request):
        staff = self.get_staff_queryset()
        return Response(BranchStaffListSerializer(staff, many=True).data)

    @extend_schema(
        tags=['CRM Restaurant — Staff'],
        summary='Restoranga yangi xodim qo\'shish',
        description='Yaratilgan user roli: `restaurant_staff`. Faqat owner qo\'shgan xodim CRM ga kira oladi.',
        request=BranchStaffCreateSerializer,
        responses={201: BranchStaffListSerializer, 400: ErrorResponseSerializer},
    )
    def post(self, request):
        serializer = BranchStaffCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            staff = self.create_staff_user(serializer.validated_data)
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BranchStaffListSerializer(staff).data, status=status.HTTP_201_CREATED)


class RestaurantStaffDetailView(RestaurantStaffManagementMixin, APIView):
    """PATCH/DELETE /api/crm/restaurant/staff/<id>/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantOwner]

    def _get_staff(self, pk):
        return self.get_staff_queryset().filter(pk=pk).first()

    @extend_schema(
        tags=['CRM Restaurant — Staff'],
        summary='Restoran xodimini yangilash',
        request=BranchStaffUpdateSerializer,
        responses={200: BranchStaffListSerializer, 404: ErrorResponseSerializer},
    )
    def patch(self, request, pk):
        staff = self._get_staff(pk)
        if not staff:
            return Response({'message': 'Xodim topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = BranchStaffUpdateSerializer(
            staff, data=request.data, partial=True, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BranchStaffListSerializer(staff).data)

    @extend_schema(
        tags=['CRM Restaurant — Staff'],
        summary='Restoran xodimini deaktivatsiya qilish',
        responses={204: OpenApiResponse(description='OK'), 404: ErrorResponseSerializer},
    )
    def delete(self, request, pk):
        staff = self._get_staff(pk)
        if not staff:
            return Response({'message': 'Xodim topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        staff.is_active = False
        staff.user.is_active = False
        staff.save(update_fields=['is_active', 'updated_at'])
        staff.user.save(update_fields=['is_active', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class RestaurantOwnerDashboardView(OwnerDashboardMixin, APIView):
    """GET /api/crm/restaurant/dashboard/ — faqat owner_restaurant."""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantOwner]

    @extend_schema(
        tags=['CRM Restaurant — Dashboard'],
        summary='Restoran owner dashboard',
        responses={200: OwnerDashboardResponseSerializer, 403: ErrorResponseSerializer},
    )
    def get(self, request):
        organization = request.user.organization
        return Response(self.build_owner_dashboard(organization, panel='restaurant'))


class TourStaffListCreateView(TourStaffManagementMixin, APIView):
    """
    GET/POST /api/crm/tour/staff/
    Faqat owner_tour — o'z tur kompaniyasiga xodim qo'shadi.
    """
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTourOwner]

    @extend_schema(
        tags=['CRM Travel — Staff'],
        summary='Tur kompaniyasi xodimlari ro\'yxati',
        responses={200: BranchStaffListSerializer(many=True), 403: ErrorResponseSerializer},
    )
    def get(self, request):
        staff = self.get_staff_queryset()
        return Response(BranchStaffListSerializer(staff, many=True).data)

    @extend_schema(
        tags=['CRM Travel — Staff'],
        summary='Tur kompaniyasiga yangi xodim qo\'shish',
        description='Yaratilgan user roli: `tour_staff`.',
        request=BranchStaffCreateSerializer,
        responses={201: BranchStaffListSerializer, 400: ErrorResponseSerializer},
    )
    def post(self, request):
        serializer = BranchStaffCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            staff = self.create_staff_user(serializer.validated_data)
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BranchStaffListSerializer(staff).data, status=status.HTTP_201_CREATED)


class TourStaffDetailView(TourStaffManagementMixin, APIView):
    """PATCH/DELETE /api/crm/tour/staff/<id>/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTourOwner]

    def _get_staff(self, pk):
        return self.get_staff_queryset().filter(pk=pk).first()

    @extend_schema(
        tags=['CRM Travel — Staff'],
        summary='Tur xodimini yangilash',
        request=BranchStaffUpdateSerializer,
        responses={200: BranchStaffListSerializer, 404: ErrorResponseSerializer},
    )
    def patch(self, request, pk):
        staff = self._get_staff(pk)
        if not staff:
            return Response({'message': 'Xodim topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = BranchStaffUpdateSerializer(
            staff, data=request.data, partial=True, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BranchStaffListSerializer(staff).data)

    @extend_schema(
        tags=['CRM Travel — Staff'],
        summary='Tur xodimini deaktivatsiya qilish',
        responses={204: OpenApiResponse(description='OK'), 404: ErrorResponseSerializer},
    )
    def delete(self, request, pk):
        staff = self._get_staff(pk)
        if not staff:
            return Response({'message': 'Xodim topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        staff.is_active = False
        staff.user.is_active = False
        staff.save(update_fields=['is_active', 'updated_at'])
        staff.user.save(update_fields=['is_active', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class TourOwnerDashboardView(OwnerDashboardMixin, APIView):
    """GET /api/crm/tour/dashboard/ — faqat owner_tour."""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTourOwner]

    @extend_schema(
        tags=['CRM Travel — Dashboard'],
        summary='Tur kompaniyasi owner dashboard',
        responses={200: OwnerDashboardResponseSerializer, 403: ErrorResponseSerializer},
    )
    def get(self, request):
        organization = request.user.organization
        return Response(self.build_owner_dashboard(organization, panel='tour'))
