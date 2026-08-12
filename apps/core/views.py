"""
Core views — health check va boshqa utility endpoint'lar.
"""

from __future__ import annotations

import time
import logging

from django.db import connection
from django.core.cache import cache
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """
    GET /health/
    Load balancer va monitoring uchun sog'lik tekshiruvi.
    Barcha komponentlar: DB, Redis, Celery.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Health'],
        summary='Sog\'lik tekshiruvi',
        description='Auth talab qilmaydi. DB, Redis va Celery holatini qaytaradi.',
        responses={
            200: OpenApiResponse(
                description='Barcha komponentlar ishlayapti',
                examples=[
                    OpenApiExample(
                        'OK',
                        value={
                            'status': 'ok',
                            'checks': {'database': 'ok', 'redis': 'ok', 'celery': 'ok'},
                            'duration_ms': 12,
                        },
                    ),
                ],
            ),
            503: OpenApiResponse(description='Kamida bitta komponent ishlamayapti'),
        },
    )
    def get(self, request):
        start  = time.monotonic()
        checks = {}
        ok     = True

        # ── PostgreSQL / SQLite ───────────────────────────────────────────────
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            checks['database'] = 'ok'
        except Exception as e:
            checks['database'] = f'error: {e}'
            ok = False
            logger.error('Health check DB xato: %s', e)

        # ── Redis ─────────────────────────────────────────────────────────────
        try:
            cache.set('_health_check', 'ok', timeout=5)
            val = cache.get('_health_check')
            checks['redis'] = 'ok' if val == 'ok' else 'error: wrong value'
            if val != 'ok':
                ok = False
        except Exception as e:
            checks['redis'] = f'error: {e}'
            ok = False
            logger.error('Health check Redis xato: %s', e)

        # ── Celery (Inspect) ──────────────────────────────────────────────────
        try:
            from celery.app.control import Inspect
            from config.celery import app as celery_app
            i = celery_app.control.inspect(timeout=1)
            active = i.ping()
            checks['celery'] = 'ok' if active else 'no workers'
        except Exception:
            checks['celery'] = 'unavailable'
            # Celery ishlamayotgani critical emas

        duration_ms = int((time.monotonic() - start) * 1000)

        status_code = 200 if ok else 503
        return Response(
            {
                'status':      'ok' if ok else 'degraded',
                'checks':      checks,
                'duration_ms': duration_ms,
            },
            status=status_code,
        )


def _api_docs_enabled() -> bool:
    from django.conf import settings
    return getattr(settings, 'ENABLE_API_DOCS', settings.DEBUG)


class APIDocsGuardMixin:
    """Swagger/Redoc faqat ENABLE_API_DOCS=True bo'lganda."""

    def dispatch(self, request, *args, **kwargs):
        from django.http import Http404
        if not _api_docs_enabled():
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class RootView(APIView):
    """Production: /health/ ga yo'naltirish; DEBUG: Swagger UI."""
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Health'],
        summary='Bosh sahifa',
        description='DEBUG + API docs yoqilgan bo\'lsa `/api/docs/` ga, aks holda `/health/` ga yo\'naltiradi.',
        responses={302: OpenApiResponse(description='Redirect')},
    )
    def get(self, request):
        from django.conf import settings
        from django.shortcuts import redirect

        if _api_docs_enabled() and settings.DEBUG:
            return redirect('/api/docs/')
        return redirect('/health/')

