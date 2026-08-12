"""CRM owner self-register — o'chirilgan (faqat admin panel)."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

_MESSAGE = (
    'CRM egasi self-register qo\'llab-quvvatlanmaydi. '
    'Administrator Django admin orqali User + Organization yaratadi.'
)

_DISABLED_CRM_AUTH_TAG = 'Auth — CRM (O\'chirilgan)'

_DISABLED_SCHEMA_KWARGS = dict(
    tags=[_DISABLED_CRM_AUTH_TAG],
    summary='CRM owner register — o\'chirilgan (410)',
    description=(
        f'{_MESSAGE}\n\n'
        '**O\'rniga:** Django admin → User + Organization yaratish.\n\n'
        'Endpoint keyinroq butunlay olib tashlanadi.'
    ),
    request=None,
    responses={410: OpenApiResponse(description='Self-register qo\'llab-quvvatlanmaydi')},
    deprecated=True,
)


@extend_schema_view(
    post=extend_schema(**_DISABLED_SCHEMA_KWARGS),
    get=extend_schema(**_DISABLED_SCHEMA_KWARGS),
)
class CRMOwnerRegisterDisabledView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        return Response({'detail': _MESSAGE}, status=status.HTTP_410_GONE)

    def get(self, request):
        return self.post(request)
