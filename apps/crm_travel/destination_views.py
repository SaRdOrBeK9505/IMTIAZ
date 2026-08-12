"""Tur kompaniyasi yo'nalishlari — CRM CRUD va galereya."""

from __future__ import annotations

from django.db.models import Count, Min, Prefetch, Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi_schemas import ErrorResponseSerializer
from apps.crm.models import StaffActivityLog
from apps.crm_travel.helpers import get_crm_org, log_staff_activity
from apps.tours.models import TourDestination, TourDestinationImage
from apps.tours.permissions import CanManageTourDestinations, IsTourCompanyStaff
from apps.tours.serializers import (
    TourDestinationCRMSerializer,
    TourDestinationCRMWriteSerializer,
    TourDestinationImageSerializer,
    TourDestinationImageUploadSerializer,
)
from apps.tours.views.crm_views import TourCRMMixin

_DESTINATIONS_TAG = 'CRM Travel — Destinations'


def _save_destination_images(request, destination: TourDestination) -> None:
    files = request.FILES.getlist('images') or []
    if single := request.FILES.get('image'):
        files.append(single)
    for idx, image_file in enumerate(files):
        is_cover = idx == 0 and not destination.images.exists()
        TourDestinationImage.objects.create(
            destination=destination,
            image=image_file,
            sort_order=idx,
            is_cover=is_cover,
        )


def _org_destinations_qs(org):
    return TourDestination.objects.filter(
        organization=org,
    ).prefetch_related(
        Prefetch('images', queryset=TourDestinationImage.objects.order_by('sort_order', 'created_at')),
    ).annotate(
        package_count=Count('packages', filter=Q(packages__is_active=True)),
        min_price=Min('packages__base_price', filter=Q(packages__is_active=True)),
    )


class TourDestinationCRMListCreateView(TourCRMMixin, generics.ListCreateAPIView):
    """
    GET  /api/crm/tour/destinations/ — kompaniya yo'nalishlari (grid UI)
    POST /api/crm/tour/destinations/ — yangi yo'nalish
    """
    permission_classes = [IsAuthenticated, CanManageTourDestinations]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TourDestinationCRMWriteSerializer
        return TourDestinationCRMSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TourDestination.objects.none()
        org = get_crm_org(self.request.user)
        qs = _org_destinations_qs(org)
        if country := self.request.query_params.get('country'):
            qs = qs.filter(country__icontains=country)
        if is_active := self.request.query_params.get('is_active'):
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        return qs.order_by('-is_popular', 'country', 'name')

    @extend_schema(
        tags=[_DESTINATIONS_TAG],
        summary='Tur yo\'nalishlari ro\'yxati (CRM grid)',
        parameters=[
            OpenApiParameter('country', str, required=False),
            OpenApiParameter('is_active', bool, required=False),
        ],
        responses={200: TourDestinationCRMSerializer(many=True), 403: ErrorResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=[_DESTINATIONS_TAG],
        summary='Yangi sayohat yo\'nalishi yaratish',
        request=TourDestinationCRMWriteSerializer,
        responses={201: TourDestinationCRMSerializer, 400: ErrorResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = TourDestinationCRMWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = get_crm_org(request.user)
        destination = TourDestination.objects.create(
            organization=org,
            **serializer.validated_data,
        )
        _save_destination_images(request, destination)
        log_staff_activity(
            request.user,
            action_type=StaffActivityLog.ActionType.MANAGE_PACKAGES,
            entity_type='TourDestination',
            entity_id=destination.id,
            description=f'Yangi yo\'nalish: {destination.name}, {destination.country}',
            request=request,
        )
        dest = _org_destinations_qs(org).get(pk=destination.pk)
        return Response(TourDestinationCRMSerializer(dest).data, status=status.HTTP_201_CREATED)


class TourDestinationCRMDetailView(TourCRMMixin, generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/crm/tour/destinations/<id>/"""
    permission_classes = [IsAuthenticated, CanManageTourDestinations]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = TourDestinationCRMSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TourDestination.objects.none()
        org = get_crm_org(self.request.user)
        return _org_destinations_qs(org)

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return TourDestinationCRMWriteSerializer
        return TourDestinationCRMSerializer

    def perform_update(self, serializer):
        instance = serializer.save()
        _save_destination_images(self.request, instance)
        log_staff_activity(
            self.request.user,
            action_type=StaffActivityLog.ActionType.MANAGE_PACKAGES,
            entity_type='TourDestination',
            entity_id=instance.id,
            description=f'Yo\'nalish yangilandi: {instance.name}',
            request=self.request,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.packages.filter(is_active=True).exists():
            return Response(
                {'message': 'Faol turlari bor yo\'nalishni o\'chirib bo\'lmaydi. Avval turlarni o\'chiring.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])
        log_staff_activity(
            request.user,
            action_type=StaffActivityLog.ActionType.MANAGE_PACKAGES,
            entity_type='TourDestination',
            entity_id=instance.id,
            description=f'Yo\'nalish o\'chirildi: {instance.name}',
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(tags=[_DESTINATIONS_TAG], summary='Yo\'nalish tafsiloti')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(tags=[_DESTINATIONS_TAG], summary='Yo\'nalishni yangilash')
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(tags=[_DESTINATIONS_TAG], summary='Yo\'nalishni o\'chirish (soft)')
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class TourDestinationImageListCreateView(TourCRMMixin, APIView):
    """
    GET  /api/crm/tour/destinations/<id>/images/
    POST /api/crm/tour/destinations/<id>/images/ — bir yoki bir nechta rasm
    """
    permission_classes = [IsAuthenticated, CanManageTourDestinations]
    parser_classes = [MultiPartParser, FormParser]

    def _get_destination(self, request, pk):
        org = get_crm_org(request.user)
        return TourDestination.objects.filter(id=pk, organization=org).first()

    @extend_schema(
        tags=[_DESTINATIONS_TAG],
        summary='Yo\'nalish rasmlari ro\'yxati',
        responses={200: TourDestinationImageSerializer(many=True)},
    )
    def get(self, request, pk):
        destination = self._get_destination(request, pk)
        if not destination:
            return Response({'message': 'Yo\'nalish topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        images = destination.images.order_by('sort_order', 'created_at')
        return Response(TourDestinationImageSerializer(images, many=True).data)

    @extend_schema(
        tags=[_DESTINATIONS_TAG],
        summary='Yo\'nalishga rasm(lar) yuklash',
        request=TourDestinationImageUploadSerializer,
        responses={201: TourDestinationImageSerializer(many=True)},
    )
    def post(self, request, pk):
        destination = self._get_destination(request, pk)
        if not destination:
            return Response({'message': 'Yo\'nalish topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        files = request.FILES.getlist('images') or []
        if single := request.FILES.get('image'):
            files.append(single)
        if not files:
            return Response({'message': 'Kamida bitta rasm yuklang.'}, status=status.HTTP_400_BAD_REQUEST)

        caption = request.data.get('caption', '')
        is_cover = str(request.data.get('is_cover', '')).lower() in ('true', '1', 'yes')
        start_order = destination.images.count()
        created = []

        for idx, image_file in enumerate(files):
            img = TourDestinationImage.objects.create(
                destination=destination,
                image=image_file,
                caption=caption if idx == 0 else '',
                sort_order=start_order + idx,
                is_cover=is_cover and idx == 0,
            )
            created.append(img)

        return Response(
            TourDestinationImageSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    delete=extend_schema(
        tags=[_DESTINATIONS_TAG],
        summary='Rasmni o\'chirish',
        responses={204: OpenApiResponse(description='O\'chirildi')},
    ),
    patch=extend_schema(
        tags=[_DESTINATIONS_TAG],
        summary='Rasm metadata yangilash (cover, tartib)',
        responses={200: TourDestinationImageSerializer},
    ),
)
class TourDestinationImageDetailView(TourCRMMixin, APIView):
    """DELETE/PATCH /api/crm/tour/destinations/<id>/images/<image_id>/"""
    permission_classes = [IsAuthenticated, CanManageTourDestinations]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = TourDestinationImageSerializer

    def delete(self, request, pk, image_id):
        org = get_crm_org(request.user)
        try:
            image = TourDestinationImage.objects.get(
                id=image_id,
                destination_id=pk,
                destination__organization=org,
            )
        except TourDestinationImage.DoesNotExist:
            return Response({'message': 'Rasm topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, pk, image_id):
        org = get_crm_org(request.user)
        try:
            image = TourDestinationImage.objects.get(
                id=image_id,
                destination_id=pk,
                destination__organization=org,
            )
        except TourDestinationImage.DoesNotExist:
            return Response({'message': 'Rasm topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        if 'caption' in request.data:
            image.caption = request.data['caption']
        if 'sort_order' in request.data:
            image.sort_order = int(request.data['sort_order'])
        if 'is_cover' in request.data:
            image.is_cover = str(request.data['is_cover']).lower() in ('true', '1', 'yes')
        image.save()

        if image.is_cover and image.image:
            image.destination.cover_image = image.image
            image.destination.save(update_fields=['cover_image', 'updated_at'])

        return Response(TourDestinationImageSerializer(image).data)


class TourDestinationGridView(TourCRMMixin, APIView):
    """
    GET /api/crm/tour/destinations/grid/
    UI kartochkalari: mamlakat, rasmlar, tur soni, minimal narx.
    """
    permission_classes = [IsAuthenticated, IsTourCompanyStaff]

    @extend_schema(
        tags=[_DESTINATIONS_TAG],
        summary='Yo\'nalishlar grid (CRM UI kartochkalari)',
        responses={200: TourDestinationCRMSerializer(many=True)},
    )
    def get(self, request):
        org = get_crm_org(request.user)
        qs = _org_destinations_qs(org).filter(is_active=True).order_by('-is_popular', 'country')
        return Response(TourDestinationCRMSerializer(qs, many=True).data)
