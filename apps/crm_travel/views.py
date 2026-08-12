"""Tur kompaniyasi vertikal CRM view'lar."""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.authentication import CRMJWTAuthentication
from apps.core.openapi_schemas import ErrorResponseSerializer, TravelOrganizationResponseSerializer
from apps.core.permissions import IsTourCRMUser
from apps.crm_core.onboarding import OwnerProvisioningError, create_branch_for_owner
from apps.crm_restaurant.serializers import BranchCreateSerializer, BranchProfileSerializer
from apps.users.models import UserRole

_ORG_TAG = 'CRM Travel — Organization'


class TourOrganizationView(APIView):
    """GET /api/crm/tour/organization/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTourCRMUser]

    @extend_schema(
        tags=[_ORG_TAG],
        summary='Tur kompaniyasi profili',
        responses={200: TravelOrganizationResponseSerializer, 404: ErrorResponseSerializer},
    )
    def get(self, request):
        organization = request.user.organization
        if not organization:
            return Response({'message': 'Tashkilot topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'organization': {
                'id': str(organization.id),
                'name': organization.name,
            },
        })


class TourBranchCreateView(APIView):
    """POST /api/crm/tour/branches/ — yangi filial (faqat owner)."""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsTourCRMUser]

    @extend_schema(
        tags=[_ORG_TAG],
        summary='Yangi filial qo\'shish',
        request=BranchCreateSerializer,
        responses={201: BranchProfileSerializer, 403: ErrorResponseSerializer},
    )
    def post(self, request):
        if request.user.role != UserRole.OWNER_TOUR:
            return Response(
                {'message': 'Faqat tur kompaniyasi egasi filial qo\'sha oladi.'},
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
