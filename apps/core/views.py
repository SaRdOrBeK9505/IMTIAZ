"""
Core views — health check va boshqa utility endpoint'lar.
"""

from __future__ import annotations

import time
import logging

from django.db import connection
from django.core.cache import cache
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
