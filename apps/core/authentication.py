"""
Audience-aware JWT Authentication.

Har bir panel uchun alohida authentication class —
tekshiruv 401 darajasida amalga oshadi (permission darajasida emas).
Bu shuni anglatadiki, yangi view yozganda 'aud tekshirishni unutdim' degan xato
umuman bo'lmaydi, chunki base class dan meros olinadi.

Token audience mapping (users/models.py -> User.jwt_audience):
    customer / (boshqa)  → 'mobile'
    owner / branch_staff → 'crm'
    admin                → 'admin'

Ishlatilish:
    class MyCRMView(CRMBaseAPIView):
        def get(self, request): ...

    class MyAdminView(AdminBaseAPIView):
        def get(self, request): ...

    class MyMobileView(MobileBaseAPIView):
        def get(self, request): ...
"""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed


class AudienceJWTAuthentication(JWTAuthentication):
    """
    JWTAuthentication kengaytmasi — tokenning 'aud' claim ni tekshiradi.
    Subklasslar `required_audience` ni belgilaydi.
    """
    required_audience: str | None = None

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, validated_token = result

        if self.required_audience is not None:
            token_aud = validated_token.get('aud')
            if token_aud != self.required_audience:
                raise AuthenticationFailed(
                    f"Bu token ushbu panel uchun yaroqsiz. "
                    f"Kerakli audience: '{self.required_audience}', "
                    f"token audience: '{token_aud}'."
                )

        return user, validated_token


class MobileJWTAuthentication(AudienceJWTAuthentication):
    """Telegram Mini App va Flutter Mobile uchun."""
    required_audience = 'mobile'


class CRMJWTAuthentication(AudienceJWTAuthentication):
    """CRM paneli (owner, branch_staff) uchun."""
    required_audience = 'crm'


class AdminJWTAuthentication(AudienceJWTAuthentication):
    """Admin paneli (ichki xodimlar) uchun."""
    required_audience = 'admin'


# ─── Base View classlar ───────────────────────────────────────────────────────

class MobileBaseAPIView(APIView):
    """
    Barcha Mobile/Telegram endpoint'lar shu klassdan meros oladi.
    Faqat 'mobile' audience li tokenlar qabul qilinadi.
    """
    authentication_classes = [MobileJWTAuthentication]
    permission_classes     = [IsAuthenticated]


class CRMBaseAPIView(APIView):
    """
    Barcha CRM endpoint'lar shu klassdan meros oladi.
    Faqat 'crm' audience li tokenlar qabul qilinadi (owner/branch_staff).
    """
    authentication_classes = [CRMJWTAuthentication]
    permission_classes     = [IsAuthenticated]


class AdminBaseAPIView(APIView):
    """
    Barcha Admin panel endpoint'lar shu klassdan meros oladi.
    Faqat 'admin' audience li tokenlar qabul qilinadi.
    """
    authentication_classes = [AdminJWTAuthentication]
    permission_classes     = [IsAuthenticated]
