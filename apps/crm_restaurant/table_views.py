"""Restoran stollari — qo'shimcha operatsiyalar (status, grouped, availability)."""

from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.authentication import CRMJWTAuthentication
from apps.core.permissions import IsRestaurantCRMUser
from apps.crm.models import RestaurantTable, TableStatus, StaffActivityLog, TableTimeSlot
from apps.crm.serializers import RestaurantTableSerializer, TableTimeSlotSerializer
from apps.crm_core.mixins import BranchScopedMixin

from .helpers import log_staff_activity, require_restaurant_permission, resolve_branch
from .serializers import TableSlotGenerateSerializer, TableSlotUpdateSerializer, TableStatusUpdateSerializer
from .services.table_slots import (
    ensure_slots_for_branch,
    ensure_slots_for_table,
    generate_slots_for_branch,
    parse_target_date,
)

_TABLE_TAG = 'CRM Restaurant — Tables'


class RestaurantTableStatusView(BranchScopedMixin, APIView):
    """PATCH /api/crm/restaurant/tables/<id>/status/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    @extend_schema(
        tags=[_TABLE_TAG],
        summary='Stol holatini yangilash',
        request=TableStatusUpdateSerializer,
        responses={200: RestaurantTableSerializer},
    )
    def patch(self, request, pk):
        require_restaurant_permission(request.user, 'manage_bookings')
        serializer = TableStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data['current_status']

        qs = self.scope_queryset_to_branch(RestaurantTable.objects.all())
        try:
            table = qs.get(pk=pk)
        except RestaurantTable.DoesNotExist:
            return Response({'message': 'Stol topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        table.current_status = new_status
        table.status_updated_at = timezone.now()
        table.save(update_fields=['current_status', 'status_updated_at', 'updated_at'])

        log_staff_activity(
            request.user,
            action_type=StaffActivityLog.ActionType.UPDATE_TABLE_STATUS,
            entity_type='RestaurantTable',
            entity_id=table.id,
            description=f'{table.table_number} → {new_status}',
            request=request,
        )
        return Response(RestaurantTableSerializer(table).data)


class RestaurantTableAvailabilityView(BranchScopedMixin, APIView):
    """GET /api/crm/restaurant/tables/availability/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    @extend_schema(
        tags=[_TABLE_TAG],
        summary='Kun bo\'yicha stol mavjudligi',
        parameters=[
            OpenApiParameter('date', str, description='YYYY-MM-DD'),
            OpenApiParameter('time', str, description='HH:MM'),
            OpenApiParameter('branch_id', str, required=False),
        ],
        responses={200: OpenApiResponse(description='Mavjudlik')},
    )
    def get(self, request):
        require_restaurant_permission(request.user, 'view_bookings')
        branch = resolve_branch(request.user, request.query_params.get('branch_id'))
        if not branch:
            return Response({'message': 'Filial topilmadi.'}, status=status.HTTP_400_BAD_REQUEST)

        date_str = request.query_params.get('date', timezone.now().date().isoformat())
        time_str = request.query_params.get('time')

        try:
            target_date = parse_target_date(date_str)
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        ensure_slots_for_branch(branch, target_date)

        tables = RestaurantTable.objects.filter(branch=branch, is_active=True).order_by(
            'section', 'table_number',
        )

        result = []
        for table in tables:
            slots_qs = table.time_slots.filter(date=target_date)
            if time_str:
                slots_qs = slots_qs.filter(start_time__lte=time_str, end_time__gte=time_str)
            booked_slots = slots_qs.filter(is_available=False).count()
            result.append({
                'id': str(table.id),
                'table_number': table.table_number,
                'section': table.section,
                'capacity': table.capacity,
                'is_vip': table.is_vip,
                'features': table.features,
                'current_status': table.current_status,
                'booked_slots': booked_slots,
                'is_free': table.current_status == TableStatus.AVAILABLE,
            })

        return Response({'date': target_date.isoformat(), 'branch_id': str(branch.id), 'tables': result})


class RestaurantTableSlotListView(BranchScopedMixin, APIView):
    """GET /api/crm/restaurant/tables/<id>/slots/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    @extend_schema(
        tags=[_TABLE_TAG],
        summary='Stol vaqt slotlari',
        parameters=[OpenApiParameter('date', str, description='YYYY-MM-DD')],
        responses={200: TableTimeSlotSerializer(many=True)},
    )
    def get(self, request, pk):
        require_restaurant_permission(request.user, 'view_bookings')
        qs = self.scope_queryset_to_branch(RestaurantTable.objects.all())
        try:
            table = qs.get(pk=pk)
        except RestaurantTable.DoesNotExist:
            return Response({'message': 'Stol topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            target_date = parse_target_date(request.query_params.get('date'))
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        ensure_slots_for_table(table, target_date)
        slots = table.time_slots.filter(date=target_date).order_by('start_time')
        return Response(TableTimeSlotSerializer(slots, many=True).data)


class RestaurantTableSlotGenerateView(APIView):
    """POST /api/crm/restaurant/tables/slots/generate/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    @extend_schema(
        tags=[_TABLE_TAG],
        summary='Filial stollari uchun slotlar generatsiya qilish',
        request=TableSlotGenerateSerializer,
        responses={200: OpenApiResponse(description='Generatsiya natijasi')},
    )
    def post(self, request):
        require_restaurant_permission(request.user, 'manage_bookings')
        serializer = TableSlotGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        branch = resolve_branch(request.user, data.get('branch_id'))
        if not branch:
            return Response({'message': 'Filial topilmadi.'}, status=status.HTTP_400_BAD_REQUEST)

        result = generate_slots_for_branch(
            branch,
            data['date'],
            data.get('end_date'),
            slot_minutes=data['slot_minutes'],
        )
        return Response(result)


class RestaurantTableSlotUpdateView(BranchScopedMixin, APIView):
    """PATCH /api/crm/restaurant/tables/<table_id>/slots/<slot_id>/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    @extend_schema(
        tags=[_TABLE_TAG],
        summary='Slot holatini yangilash (bloklash/bo\'shatish)',
        request=TableSlotUpdateSerializer,
        responses={200: TableTimeSlotSerializer},
    )
    def patch(self, request, pk, slot_id):
        require_restaurant_permission(request.user, 'manage_bookings')
        qs = self.scope_queryset_to_branch(RestaurantTable.objects.all())
        try:
            table = qs.get(pk=pk)
        except RestaurantTable.DoesNotExist:
            return Response({'message': 'Stol topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            slot = table.time_slots.get(pk=slot_id)
        except TableTimeSlot.DoesNotExist:
            return Response({'message': 'Slot topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TableSlotUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updates = serializer.validated_data

        if 'is_available' in updates and slot.booking_id and updates['is_available']:
            return Response(
                {'message': 'Bron bilan bog\'langan slotni bo\'shatish mumkin emas. Avval bronni bekor qiling.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for field, value in updates.items():
            setattr(slot, field, value)
        slot.save(update_fields=[*updates.keys(), 'updated_at'])
        return Response(TableTimeSlotSerializer(slot).data)


class RestaurantTablesGroupedView(BranchScopedMixin, APIView):
    """GET /api/crm/restaurant/tables/grouped/"""
    authentication_classes = [CRMJWTAuthentication]
    permission_classes = [IsAuthenticated, IsRestaurantCRMUser]

    @extend_schema(
        tags=[_TABLE_TAG],
        summary='Stollar bo\'limlar bo\'yicha guruhlangan (filtr bilan)',
        parameters=[
            OpenApiParameter('location', str, description='Filter by location: all|ichki|tashqi|vip|teras'),
            OpenApiParameter('branch_id', str, required=False),
        ],
        responses={200: OpenApiResponse(description='Guruhlangan stollar')},
    )
    def get(self, request):
        require_restaurant_permission(request.user, 'view_bookings')
        branch = resolve_branch(request.user, request.query_params.get('branch_id'))
        if not branch:
            return Response({'message': 'Filial topilmadi.'}, status=status.HTTP_400_BAD_REQUEST)

        qs = RestaurantTable.objects.filter(branch=branch, is_active=True).order_by(
            'section', 'table_number',
        )
        
        # Filter by location
        location_filter = request.query_params.get('location', 'all')
        if location_filter != 'all':
            location_mapping = {
                'ichki': 'Ichki zal',
                'tashqi': 'Tashqi',
                'vip': 'VIP',
                'teras': 'Teras',
            }
            section_filter = location_mapping.get(location_filter.lower())
            if section_filter:
                qs = qs.filter(section__iexact=section_filter)

        sections: dict = {}
        for table in qs:
            key = table.section or 'Boshqa'
            sections.setdefault(key, {'section': key, 'count': 0, 'tables': []})
            sections[key]['count'] += 1
            
            # Map status to UI format
            status_mapping = {
                'available': 'bosh',
                'occupied': 'band',
                'reserved': 'band_mijoz',
                'maintenance': 'band',
            }
            ui_status = status_mapping.get(table.current_status, 'bosh')
            
            table_data = RestaurantTableSerializer(table).data
            table_data['ui_status'] = ui_status
            sections[key]['tables'].append(table_data)

        return Response({
            'branch_id': str(branch.id),
            'sections': list(sections.values()),
            'total': qs.count(),
        })
