"""CRM owner self-register — o'chirilgan (faqat admin panel)."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.response import Response

from apps.core.authentication import PublicAPIView

_MESSAGE = (
    'CRM egasi self-register qo\'llab-quvvatlanmaydi. '
    'Administrator Django admin orqali User + Organization yaratadi.'
)

_DISABLED_SCHEMA_KWARGS = dict(
    exclude=True,
    deprecated=True,
)


@extend_schema_view(
    post=extend_schema(**_DISABLED_SCHEMA_KWARGS),
    get=extend_schema(**_DISABLED_SCHEMA_KWARGS),
)
class CRMOwnerRegisterDisabledView(PublicAPIView):
    def post(self, request):
        return Response({'detail': _MESSAGE}, status=status.HTTP_410_GONE)

    def get(self, request):
        return self.post(request)