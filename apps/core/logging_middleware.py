"""
Request/Response logging middleware.
Har bir API so'rov va javob log qilinadi.
Muhim: parollar, tokenlar va shaxsiy ma'lumotlar filtered.
"""

from __future__ import annotations

import json
import logging
import time
import uuid

logger = logging.getLogger('apps.requests')

# Bu fieldlar log'dan o'chiriladi
SENSITIVE_FIELDS = frozenset({
    'password', 'token', 'access', 'refresh',
    'secret', 'api_key', 'code', 'otp',
    'card_number', 'cvv', 'pin',
})


def _filter_sensitive(data: dict) -> dict:
    """Nozik maydonlarni *** bilan almashtiradi."""
    if not isinstance(data, dict):
        return data
    return {
        k: '***' if k.lower() in SENSITIVE_FIELDS else _filter_sensitive(v)
        if isinstance(v, dict) else v
        for k, v in data.items()
    }


class RequestLoggingMiddleware:
    """
    Har bir request:
        - request_id (UUID) bilan belgilanadi
        - method, path, user, IP, status_code, duration log qilinadi
        - Xatolar (4xx, 5xx) alohida WARN/ERROR darajasida
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id  = str(uuid.uuid4())[:8]
        start_time  = time.monotonic()

        # Request ID ni headerlarga qo'shish (frontend trace uchun)
        request.request_id = request_id

        response = self.get_response(request)

        duration_ms = int((time.monotonic() - start_time) * 1000)

        user_id = (
            request.user.id
            if hasattr(request, 'user') and request.user.is_authenticated
            else 'anon'
        )

        log_data = {
            'request_id':  request_id,
            'method':      request.method,
            'path':        request.path,
            'status':      response.status_code,
            'duration_ms': duration_ms,
            'user_id':     user_id,
            'ip':          self._get_client_ip(request),
            'user_agent':  request.META.get('HTTP_USER_AGENT', '')[:100],
        }

        level = logging.INFO
        if response.status_code >= 500:
            level = logging.ERROR
        elif response.status_code >= 400:
            level = logging.WARNING

        logger.log(level, 'API %s %s → %s [%dms]',
                   request.method, request.path,
                   response.status_code, duration_ms,
                   extra={'data': log_data})

        # Request ID ni response headerga qo'shish
        response['X-Request-ID'] = request_id
        return response

    @staticmethod
    def _get_client_ip(request) -> str:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
