"""
Bookhara API HTTP client — token boshqaruvi bilan.
Token Redis'da keshlanadi, muddati tugaganda avtomatik yangilanadi.
"""

from __future__ import annotations

import logging
import httpx
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

BOOKHARA_TOKEN_CACHE_KEY = 'bookhara_api_token'
BOOKHARA_TOKEN_TTL       = 60 * 55  # 55 daqiqa (token 60 daqiqa amal qiladi)


class BookharaAPIClient:
    """
    Bookhara REST API uchun low-level HTTP client.
    Barcha so'rovlarga Bearer token qo'shadi.
    401 kelsa — tokenni yangilab qayta urinadi.
    """

    def __init__(self):
        self.base_url  = settings.BOOKHARA_BASE_URL
        self.login     = settings.BOOKHARA_LOGIN
        self.password  = settings.BOOKHARA_PASSWORD
        self._session  = httpx.Client(timeout=30)

    # ── Token ─────────────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        token = cache.get(BOOKHARA_TOKEN_CACHE_KEY)
        if token:
            return token
        return self._refresh_token()

    def _refresh_token(self) -> str:
        """POST /api/v1/auth/token — yangi token oladi."""
        try:
            resp = self._session.post(
                f'{self.base_url}/api/v1/auth/token',
                json={'login': self.login, 'password': self.password},
            )
            resp.raise_for_status()
            data  = resp.json()
            token = data.get('token') or data.get('access_token') or data['data']['token']
            cache.set(BOOKHARA_TOKEN_CACHE_KEY, token, BOOKHARA_TOKEN_TTL)
            logger.info('Bookhara token yangilandi')
            return token
        except Exception as e:
            logger.exception('Bookhara token olishda xato: %s', e)
            raise

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self._get_token()}',
            'Content-Type':  'application/json',
            'Accept':        'application/json',
        }

    # ── HTTP metodlar ─────────────────────────────────────────────────────────

    def get(self, path: str, params: dict | None = None) -> dict:
        return self._request('GET', path, params=params)

    def post(self, path: str, body: dict | None = None) -> dict:
        return self._request('POST', path, json=body)

    def delete(self, path: str) -> dict:
        return self._request('DELETE', path)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f'{self.base_url}{path}'
        try:
            resp = self._session.request(
                method, url, headers=self._headers(), **kwargs
            )
            # 401 — tokenni yangilab qayta urinish
            if resp.status_code == 401:
                logger.warning('Bookhara 401, token yangilanmoqda...')
                cache.delete(BOOKHARA_TOKEN_CACHE_KEY)
                resp = self._session.request(
                    method, url, headers=self._headers(), **kwargs
                )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                'Bookhara HTTP xato: %s %s → %s',
                method, path, e.response.status_code,
            )
            raise
        except Exception as e:
            logger.exception('Bookhara so\'rov xatosi: %s %s — %s', method, path, e)
            raise
