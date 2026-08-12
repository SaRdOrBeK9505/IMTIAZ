"""API docs (Swagger) production guard testlari."""

from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(DEBUG=False, ENABLE_API_DOCS=False)
class APIDocsDisabledTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_schema_not_exposed(self):
        resp = self.client.get('/api/schema/')
        self.assertEqual(resp.status_code, 404)

    def test_swagger_not_exposed(self):
        resp = self.client.get('/api/docs/')
        self.assertEqual(resp.status_code, 404)

    def test_root_not_exposed_when_docs_disabled(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 404)


@override_settings(DEBUG=True, ENABLE_API_DOCS=True)
class APIDocsEnabledTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_schema_available(self):
        resp = self.client.get('/api/schema/')
        self.assertEqual(resp.status_code, 200)

    def test_swagger_ui_available(self):
        resp = self.client.get('/api/docs/')
        self.assertEqual(resp.status_code, 200)

    def test_root_is_swagger_when_docs_enabled(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'swagger', resp.content.lower())

    def test_root_is_swagger_when_debug_even_if_docs_flag_false(self):
        with self.settings(DEBUG=True, ENABLE_API_DOCS=False):
            resp = self.client.get('/')
            self.assertEqual(resp.status_code, 200)

    def test_disabled_crm_endpoints_visible_in_schema(self):
        from drf_spectacular.generators import SchemaGenerator

        schema = SchemaGenerator().get_schema(request=None, public=True)
        paths = schema.get('paths', {})
        disabled = [
            '/crm/auth/register/request-otp/',
            '/crm/auth/register/verify-otp/',
            '/crm/auth/register/complete/',
            '/crm/auth/',
        ]
        disabled_tag = 'Auth — CRM (O\'chirilgan)'
        for path in disabled:
            self.assertIn(path, paths, msg=f'{path} should be visible in Swagger')
            for method, operation in paths[path].items():
                if method == 'parameters':
                    continue
                self.assertTrue(operation.get('deprecated'), msg=f'{path} {method} should be deprecated')
                self.assertIn(disabled_tag, operation.get('tags', []))

    def test_token_refresh_in_schema(self):
        from drf_spectacular.generators import SchemaGenerator

        schema = SchemaGenerator().get_schema(request=None, public=True)
        paths = schema.get('paths', {})
        self.assertIn('/auth/token/refresh/', paths)
