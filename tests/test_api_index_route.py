import unittest

from fastapi.testclient import TestClient

from eight_characters import __version__
from eight_characters.main import app

EXPLORER_ASSETS = ('styles.css', 'vendor/d3.v7.min.js', 'data.js', 'app.js')


class TestApiIndexRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_index_renders_single_page_application(self) -> None:
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers['content-type'].startswith('text/html'))
        self.assertIn('id="chart-form"', response.text)
        self.assertIn('id="pillars"', response.text)

    def test_relationship_view_has_accessible_controls(self) -> None:
        response = self.client.get('/')
        for element_id in (
            'relationships-heading',
            'relationship-list',
            'relationship-detail',
            'relationship-status',
            'ten-gods-toggle',
        ):
            self.assertIn(f'id="{element_id}"', response.text)
        self.assertIn('aria-live="polite"', response.text)
        self.assertLess(
            response.text.index('/static/relationships.js'),
            response.text.index('/static/app.js'),
        )
        self.assertEqual(self.client.get('/static/relationships.js').status_code, 200)

    def test_day_master_context_has_accessible_controls_and_versioned_module(
        self,
    ) -> None:
        response = self.client.get('/')
        for element_id in (
            'day-master-context',
            'day-master-heading',
            'context-controls',
            'context-detail',
            'context-status',
        ):
            self.assertIn(f'id="{element_id}"', response.text)
        self.assertLess(
            response.text.index('/static/day-master-context.js'),
            response.text.index('/static/app.js'),
        )
        self.assertEqual(
            self.client.get('/static/day-master-context.js').status_code, 200
        )

    def test_roles_module_loads_before_context_and_is_served(self) -> None:
        response = self.client.get('/')
        self.assertLess(
            response.text.index('/static/roles.js'),
            response.text.index('/static/day-master-context.js'),
        )
        self.assertEqual(self.client.get('/static/roles.js').status_code, 200)

    def test_index_versions_static_assets(self) -> None:
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        for asset in (
            'style.css',
            'localization.js',
            'relationships.js',
            'day-master-context.js',
            'roles.js',
            'app.js',
        ):
            self.assertIn(f'/static/{asset}?v={__version__}', response.text)

    def test_index_serves_its_own_fonts(self) -> None:
        response = self.client.get('/')
        for font in ('Manrope-normal-400.woff2', 'CormorantGaramond-normal-400.woff2'):
            path = f'/explorer/vendor/fonts/{font}'
            self.assertIn(f'href="{path}"', response.text)
            self.assertIn(path, self.client.get('/static/style.css').text)
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.assertNotIn(
            'fonts.googleapis.com', self.client.get('/static/style.css').text
        )

    def test_explorer_page_versions_its_assets(self) -> None:
        for path in ('/explorer/', '/explorer'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.headers['content-type'].startswith('text/html'))
            self.assertIn('id="statusBar"', response.text)
            for asset in EXPLORER_ASSETS:
                self.assertIn(f'/explorer/{asset}?v={__version__}', response.text)

    def test_explorer_assets_are_served(self) -> None:
        for asset in EXPLORER_ASSETS:
            response = self.client.get(f'/explorer/{asset}?v={__version__}')
            self.assertEqual(response.status_code, 200, asset)


if __name__ == '__main__':
    unittest.main()
