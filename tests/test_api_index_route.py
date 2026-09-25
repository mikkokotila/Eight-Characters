import hashlib
import unittest

from fastapi.testclient import TestClient

from eight_characters import __version__
from eight_characters.main import app
from eight_characters.policy import MAX_SUPPORTED_YEAR, MIN_SUPPORTED_YEAR

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

    def test_birth_date_field_takes_the_engine_scope(self) -> None:
        response = self.client.get('/')
        self.assertIn(f'min="{MIN_SUPPORTED_YEAR:04d}-01-01"', response.text)
        self.assertIn(f'max="{MAX_SUPPORTED_YEAR:04d}-12-31"', response.text)
        # The page validates itself, so its messages follow the chosen language.
        self.assertIn('<form id="chart-form" novalidate>', response.text)

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

    def test_chart_characters_have_their_own_font_and_licence(self) -> None:
        # The stems and branches are drawn from a subset of Noto Serif TC; its source
        # and SHA-256 are recorded in static/fonts/README.md.
        path = '/static/fonts/NotoSerifTC-stems-branches.woff2'
        self.assertIn(path, self.client.get('/static/style.css').text)
        font = self.client.get(path)
        self.assertEqual(font.status_code, 200)
        self.assertEqual(
            hashlib.sha256(font.content).hexdigest(),
            'd1e4af3d46b33eaa85125a01d008a6f0faec9c3ac4e839f7b170b8a4d772869f',
        )
        licence = self.client.get('/static/fonts/NotoSerifTC-OFL.txt')
        self.assertEqual(licence.status_code, 200)
        self.assertIn('SIL OPEN FONT LICENSE Version 1.1', licence.text)

    def test_tab_icon_is_linked_and_served(self) -> None:
        response = self.client.get('/')
        self.assertIn('<link rel="icon" href="/favicon.ico"', response.text)
        svg_path = f'/static/favicon.svg?v={__version__}'
        self.assertIn(f'href="{svg_path}" type="image/svg+xml"', response.text)
        icon = self.client.get('/favicon.ico')
        self.assertEqual(icon.status_code, 200)
        self.assertEqual(icon.headers['content-type'], 'image/vnd.microsoft.icon')
        self.assertTrue(icon.content.startswith(b'\x00\x00\x01\x00'))
        svg = self.client.get(svg_path)
        self.assertEqual(svg.status_code, 200)
        self.assertTrue(svg.headers['content-type'].startswith('image/svg+xml'))

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
