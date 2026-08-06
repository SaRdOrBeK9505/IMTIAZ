"""Membership app views."""

from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MembershipTier, UserMembership, WaitlistApplication, Subscription, PromoCode
from .serializers import (
    MembershipTierSerializer,
    UserMembershipSerializer,
    WaitlistApplicationSerializer,
    WaitlistApplySerializer,
    SubscriptionSerializer,
)


class MembershipTierListView(generics.ListAPIView):
    """GET /api/membership/tiers/"""
    permission_classes = [AllowAny]
    serializer_class   = MembershipTierSerializer
    queryset           = MembershipTier.objects.all()


class MyMembershipView(APIView):
    """GET /api/membership/my/ — joriy foydalanuvchi a'zoligi"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: UserMembershipSerializer},
        summary="Joriy a'zolik darajasi",
        tags=['Membership'],
    )
    def get(self, request):
        try:
            membership = request.user.membership_tier
            return Response(UserMembershipSerializer(membership).data)
        except Exception:
            return Response({'status': 'no_membership', 'message': "A'zolik mavjud emas."})


class WaitlistApplyView(APIView):
    """GET / POST /api/membership/waitlist/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: WaitlistApplicationSerializer},
        summary='Waitlist ariza holati',
        tags=['Membership'],
    )
    def get(self, request):
        try:
            app = request.user.waitlist_application
            return Response(WaitlistApplicationSerializer(app).data)
        except WaitlistApplication.DoesNotExist:
            return Response({'status': 'not_applied', 'message': 'Ariza topshirilmagan.'})

    @extend_schema(
        request=WaitlistApplySerializer,
        responses={201: WaitlistApplicationSerializer},
        summary="Waitlist ga ariza topshirish",
        tags=['Membership'],
    )
    def post(self, request):
        if hasattr(request.user, 'waitlist_application'):
            return Response(
                {'message': 'Siz allaqachon ariza topshirgansiz.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = WaitlistApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        promo_code = serializer.validated_data.get('promo_code')
        app_status = WaitlistApplication.Status.PENDING
        tier       = None

        if promo_code:
            promo      = PromoCode.objects.get(code=promo_code)
            app_status = WaitlistApplication.Status.APPROVED
            tier       = promo.tier
            promo.used_count += 1
            promo.save(update_fields=['used_count'])

        app = WaitlistApplication.objects.create(
            user=request.user,
            status=app_status,
            notes=serializer.validated_data.get('notes', ''),
            promo_code=promo_code,
            reviewed_at=timezone.now() if promo_code else None,
        )

        # Promo-kod bilan tasdiqlangan → UserMembership yaratish
        if app_status == WaitlistApplication.Status.APPROVED and tier:
            um, created = UserMembership.objects.get_or_create(
                user=request.user,
                defaults={'tier': tier},
            )
            if not created:
                um.tier = tier
                um.save(update_fields=['tier', 'updated_at'])
            um.sync_from_tier()

            # Foydalanuvchiga xabar
            from apps.notifications.tasks import notify_user
            notify_user(
                request.user,
                notification_type='waitlist_approved',
                title="A'zolikka qabul qilindingiz!",
                body=f"Tabriklaymiz! {tier.name} darajasiga qabul qilindingiz.",
                metadata={'tier_name': tier.name},
            )

        return Response(WaitlistApplicationSerializer(app).data, status=status.HTTP_201_CREATED)


class SubscriptionView(APIView):
    """GET /api/membership/subscription/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: SubscriptionSerializer},
        summary='Joriy obuna',
        tags=['Membership'],
    )
    def get(self, request):
        try:
            sub = Subscription.objects.filter(
                user=request.user,
                status__in=['active', 'past_due', 'trial'],
            ).select_related('tier').latest('created_at')
            return Response(SubscriptionSerializer(sub).data)
        except Subscription.DoesNotExist:
            return Response({'status': 'no_subscription', 'message': 'Faol obuna mavjud emas.'})
