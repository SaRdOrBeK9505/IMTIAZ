"""
Bookhara API — low-level HTTP klient.

Token boshqaruvi:
    POST /api/v1/accounts/tokens
    body: {email, password, access_type: "avia"}
    Javob: {"data": {"token": "..."}} yoki {"token": "..."}

Token Redis'da 55 daqiqa keshlanadi (token 60 daqiqa amal qiladi).
401 kelsa — keshni tozalab, tokenni qayta olib, so'rovni bir marta
qayta yuboradi.
"""

from __future__ import annotations

import logging

import httpx
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TOKEN_CACHE_KEY = 'bookhara_access_token'
TOKEN_TTL_SECONDS = 55 * 60  # 55 daqiqa


class BookharaClient:
    """Bookhara REST API uchun low-level HTTP klient."""

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ):
        self.base_url = (base_url or settings.BOOKHARA_BASE_URL).rstrip('/')
        self.email    = email    or settings.BOOKHARA_EMAIL
        self.password = password or settings.BOOKHARA_PASSWORD
        self._http    = httpx.Client(timeout=30)

    # -------------------------------------------------------------------
    # Token boshqaruvi
    # -------------------------------------------------------------------

    def _get_token(self) -> str:
        token = cache.get(TOKEN_CACHE_KEY)
        if token:
            return token
        return self._fetch_token()

    def _fetch_token(self) -> str:
        """POST /api/v1/accounts/tokens — yangi token oladi."""
        url = f'{self.base_url}/api/v1/accounts/tokens'
        resp = self._http.post(
            url,
            json={
                'email':       self.email,
                'password':    self.password,
                'access_type': 'avia',
            },
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        )
        resp.raise_for_status()
        body  = resp.json()
        token = (
            body.get('token')
            or body.get('access_token')
            or (body.get('data') or {}).get('token')
        )
        if not token:
            raise ValueError(f'Bookhara token javobida topilmadi. Body: {body}')
        cache.set(TOKEN_CACHE_KEY, token, TOKEN_TTL_SECONDS)
        logger.info('Bookhara token yangilandi')
        return token

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self._get_token()}',
            'Content-Type':  'application/json',
            'Accept':        'application/json',
        }

    # -------------------------------------------------------------------
    # HTTP metodlar
    # -------------------------------------------------------------------

    def get(self, path: str, params: dict | None = None) -> dict:
        return self._request('GET', path, params=params)

    def post(self, path: str, body: dict | None = None) -> dict:
        return self._request('POST', path, json=body or {})

    def delete(self, path: str) -> dict:
        return self._request('DELETE', path)

    # -------------------------------------------------------------------
    # Ichki so'rov yuboruvchi
    # -------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f'{self.base_url}{path}'
        resp = self._http.request(method, url, headers=self._headers(), **kwargs)

        if resp.status_code == 401:
            # Token eskirgan — tozalab, qayta olish, bir marta qayta urinish
            logger.warning('Bookhara 401 — token yangilanmoqda: %s %s', method, path)
            cache.delete(TOKEN_CACHE_KEY)
            resp = self._http.request(method, url, headers=self._headers(), **kwargs)

        resp.raise_for_status()
        return resp.json()
