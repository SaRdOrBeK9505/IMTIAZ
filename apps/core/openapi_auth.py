"""
drf-spectacular authentication extensionlari.

Har bir JWT audience uchun alohida Swagger "Authorize" tugmasi ko'rsatiladi.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension

from apps.core.authentication import (
    AdminJWTAuthentication,
    CRMJWTAuthentication,
    MobileJWTAuthentication,
)


class _JWTSchemeBase(OpenApiAuthenticationExtension):
    """Subklasslar target_class va name ni belgilaydi."""

    audience = ''
    login_path = ''

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
            'description': (
                f'Bearer JWT token (`aud={self.audience}`).\n\n'
                f'Login: `POST {self.login_path}`\n\n'
                'Header: `Authorization: Bearer <access_token>`'
            ),
        }


class MobileJWTAuthenticationScheme(_JWTSchemeBase):
    target_class = MobileJWTAuthentication
    name = 'BearerMobile'
    audience = 'mobile'
    login_path = '/api/auth/login/'


class CRMJWTAuthenticationScheme(_JWTSchemeBase):
    target_class = CRMJWTAuthentication
    name = 'BearerCRM'
    audience = 'crm'
    login_path = '/api/crm/auth/login/'


class AdminJWTAuthenticationScheme(_JWTSchemeBase):
    target_class = AdminJWTAuthentication
    name = 'BearerAdmin'
    audience = 'admin'
    login_path = '/api/admin/auth/login/'


class DefaultJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Global default JWTAuthentication — audience tekshiruvsiz."""

    target_class = 'rest_framework_simplejwt.authentication.JWTAuthentication'
    name = 'BearerAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
            'description': (
                'Bearer JWT. Audience qarab tegishli login endpointidan oling:\n'
                '- Mobile: `POST /api/auth/login/` (aud=mobile)\n'
                '- CRM: `POST /api/crm/auth/login/` (aud=crm)\n'
                '- Admin: `POST /api/admin/auth/login/` (aud=admin)'
            ),
        }
