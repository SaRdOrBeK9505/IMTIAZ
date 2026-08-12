"""Swagger / OpenAPI — runtime guard (ENABLE_API_DOCS)."""

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.core.views import APIDocsGuardMixin


class GuardedSpectacularAPIView(APIDocsGuardMixin, SpectacularAPIView):
    pass


class GuardedSpectacularSwaggerView(APIDocsGuardMixin, SpectacularSwaggerView):
    pass


class GuardedSpectacularRedocView(APIDocsGuardMixin, SpectacularRedocView):
    pass
