"""Restaurant vertikal CRM view'lar."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.authentication import CRMJWTAuthentication
from apps.core.openapi_schemas import (
    ErrorResponseSerializer,
    RestaurantOrganizationResponseSerializer,
)
from apps.core.permissions import IsRestaurantCRMUser
from apps.crm.models import RestaurantTable, StaffActivityLog
from apps.crm_core.mixins import BranchScopedMixin, RestaurantCRMViewSet
from apps.users.models import UserRole

from apps.crm_core.onboarding import OwnerProvisioningError, create_branch_for_owner

from .helpers import log_staff_activity, require_restaurant_permission, resolve_branch
from .models import FeaturedItem, MenuCategory, MenuItem
from .serializers import (
    BranchCreateSerializer,
    BranchProfileSerializer,
    FeaturedItemSerializer,
    MenuCategorySerializer,
    MenuItemSerializer,
    OrganizationProfileSerializer,
    RestaurantTableSerializer,
    RestaurantTableWriteSerializer,
)

_TABLE_TAG = 'CRM Restaurant — Tables'
_MENU_TAG = 'CRM Restaurant — Menu'
_FEATURED_TAG = 'CRM Restaurant — Featured'
_ORG_TAG = 'CRM Restaurant — Organization'


@extend_schema_view(
    list=extend_schema(
        tags=[_TABLE_TAG],
        summary='Stollar ro\'yxati',
        description='Owner — barcha filiallar. Staff — o\'z filiali stollari.',
    ),
    create=extend_schema(
        tags=[_TABLE_TAG],
        summary='Yangi stol qo\'shish',
        request=RestaurantTableWriteSerializer,
        responses={201: RestaurantTableSerializer, 403: ErrorResponseSerializer},
    ),
    retrieve=extend_schema(tags=[_TABLE_TAG], summary='Stol tafsilotlari'),
    update=extend_schema(tags=[_TABLE_TAG], summary='Stolni yangilash', request=RestaurantTableWriteSerializer),
    partial_update=extend_schema(tags=[_TABLE_TAG], summary='Stolni qisman yangilash'),
    destroy=extend_schema(tags=[_TABLE_TAG], summary='Stolni o\'chirish'),
)
class RestaurantTableViewSet(RestaurantCRMViewSet):
    queryset = RestaurantTable.objects.select_related('branch')
    serializer_class = RestaurantTableSerializer

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return RestaurantTableWriteSerializer
        return RestaurantTableSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by('section', 'table_number')
        params = self.request.query_params
        if section := params.get('section'):
            qs = qs.filter(section=section)
        if params.get('is_active') is not None:
            qs = qs.filter(is_active=params.get('is_active', '').lower() == 'true')
        if current_status := params.get('status'):
            qs = qs.filter(current_status=current_status)
        return qs

    def perform_create(self, serializer):
        require_restaurant_permission(self.request.user, 'manage_bookings')
        branch = resolve_branch(
            self.request.user,
            self.request.data.get('branch_id'),
        ) or self.get_user_branch()
        if branch is None:
            raise PermissionDenied('Filial aniqlanmadi.')
        table = serializer.save(branch=branch)
        log_staff_activity(
            self.request.user,
            action_type=StaffActivityLog.ActionType.ADD_TABLE,
            entity_type='RestaurantTable',
            entity_id=table.id,
            description=f'Yangi stol: {table.table_number}',
            request=self.request,
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])


@extend_schema_view(
    list=extend_schema(tags=[_MENU_TAG], summary='Menyu kategoriyalari'),
    create=extend_schema(tags=[_MENU_TAG], summary='Kategoriya qo\'shish', request=MenuCategorySerializer),
    retrieve=extend_schema(tags=[_MENU_TAG], summary='Kategoriya tafsilotlari'),
    update=extend_schema(tags=[_MENU_TAG], summary='Kategoriyani yangilash'),
    partial_update=extend_schema(tags=[_MENU_TAG], summary='Kategoriyani qisman yangilash'),
    destroy=extend_schema(tags=[_MENU_TAG], summary='Kategoriyani o\'chirish'),
)
class MenuCategoryViewSet(RestaurantCRMViewSet):
    queryset = MenuCategory.objects.select_related('branch')
    serializer_class = MenuCategorySerializer

    def perform_create(self, serializer):
        require_restaurant_permission(self.request.user, 'manage_bookings')
        branch = resolve_branch(self.request.user) or self.get_user_branch()
        if branch is None:
            raise PermissionDenied('Filial aniqlanmadi.')
        serializer.save(branch=branch)


@extend_schema_view(
    list=extend_schema(tags=[_MENU_TAG], summary='Menyu elementlari'),
    create=extend_schema(tags=[_MENU_TAG], summary='Taom qo\'shish', request=MenuItemSerializer),
    retrieve=extend_schema(tags=[_MENU_TAG], summary='Taom tafsilotlari'),
    update=extend_schema(tags=[_MENU_TAG], summary='Taomni yangilash'),
    partial_update=extend_schema(tags=[_MENU_TAG], summary='Taomni qisman yangilash'),
    destroy=extend_schema(tags=[_MENU_TAG], summary='Taomni o\'chirish'),
)
class MenuItemViewSet(RestaurantCRMViewSet):
    queryset = MenuItem.objects.select_related('category', 'category__branch')
    serializer_class = MenuItemSerializer
    organization_lookup = 'category__branch__organization'
    branch_lookup = 'category__branch'

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return MenuItem.objects.none()
        qs = super().get_queryset()
        branch = self.get_user_branch()
        if branch is not None:
            return qs.filter(category__branch=branch)
        organization = self.get_user_organization()
        if organization:
            return qs.filter(category__branch__organization=organization)
        return qs.none()


@extend_schema_view(
    list=extend_schema(tags=[_FEATURED_TAG], summary='Tavsiya etilgan takliflar'),
    create=extend_schema(tags=[_FEATURED_TAG], summary='Taklif qo\'shish', request=FeaturedItemSerializer),
    retrieve=extend_schema(tags=[_FEATURED_TAG], summary='Taklif tafsilotlari'),
    update=extend_schema(tags=[_FEATURED_TAG], summary='Taklifni yangilash'),
    partial_update=extend_schema(tags=[_FEATURED_TAG], summary='Taklifni qisman yangilash'),
    destroy=extend_schema(tags=[_FEATURED_TAG], summary='Taklifni o\'chirish'),
)
class FeaturedItemViewSet(RestaurantCRMViewSet):
    queryset = FeaturedItem.objects.select_related('branch', 'menu_item')
    serializer_class = FeaturedItemSerializer

    def perform_create(self, serializer):
        require_restaurant_permission(self.request.user, 'manage_bookings')
        branch = resolve_branch(self.request.user) or self.get_user_branch()
        if branch is None:
            raise PermissionDenied('Filial aniqlanmadi.')
        serializer.save(branch=branch)


@extend_schema_view(
    get=extend_schema(
        tags=[_ORG_TAG],
        summary='Tashkilot va filiallar profili',
        responses={200: RestaurantOrganizationResponseSerializer, 404: ErrorResponseSerializer},
    ),
    patch=extend_schema(
        tags=[_ORG_TAG],
        summary='Profil yangilash',
        responses={200: OpenApiResponse(description='Yangilangan profil')},
    ),
)
class RestaurantOrganizationView(BranchScopedMixin, APIView):
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]
    serializer_class = RestaurantOrganizationResponseSerializer

    def get(self, request):
        organization = request.user.organization
        if not organization:
            return Response({'message': 'Tashkilot topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        branches = organization.branches.filter(is_active=True)
        return Response({
            'organization': OrganizationProfileSerializer(organization).data,
            'branches': BranchProfileSerializer(branches, many=True).data,
        })

    def patch(self, request):
        organization = request.user.organization
        if not organization:
            return Response({'message': 'Tashkilot topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        branch_id = request.data.get('branch_id')
        branch_payload = request.data.get('branch', {})

        if branch_id or branch_payload:
            branch = organization.branches.filter(id=branch_id or branch_payload.get('id')).first()
            if not branch:
                return Response({'message': 'Filial topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
            if request.user.role == UserRole.RESTAURANT_STAFF:
                staff = request.user.branch_staff_profile
                if staff.branch_id != branch.id:
                    return Response({'message': 'Ruxsat yo\'q.'}, status=status.HTTP_403_FORBIDDEN)
            serializer = BranchProfileSerializer(branch, data=branch_payload or request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        if request.user.role != UserRole.OWNER_RESTAURANT:
            return Response({'message': 'Tashkilot profilini faqat egasi yangilay oladi.'}, status=status.HTTP_403_FORBIDDEN)

        org_data = request.data.get('organization', request.data)
        org_serializer = OrganizationProfileSerializer(organization, data=org_data, partial=True)
        org_serializer.is_valid(raise_exception=True)
        org_serializer.save()
        return Response(org_serializer.data)


class RestaurantBranchCreateView(APIView):
    """POST /api/crm/restaurant/branches/ — yangi filial qo'shish (faqat owner)."""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    @extend_schema(
        tags=[_ORG_TAG],
        summary='Yangi filial qo\'shish',
        request=BranchCreateSerializer,
        responses={201: BranchProfileSerializer, 403: ErrorResponseSerializer},
    )
    def post(self, request):
        if request.user.role != UserRole.OWNER_RESTAURANT:
            return Response(
                {'message': 'Faqat restoran egasi filial qo\'sha oladi.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BranchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            branch = create_branch_for_owner(
                owner=request.user,
                name=data['name'],
                city=data.get('city', ''),
                address=data.get('address', ''),
                phone=data.get('phone', ''),
            )
        except OwnerProvisioningError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(BranchProfileSerializer(branch).data, status=status.HTTP_201_CREATED)
