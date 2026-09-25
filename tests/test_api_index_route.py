import unittest

from fastapi.testclient import TestClient

from eight_characters import __version__
from eight_characters.main import app


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

    def test_index_versions_static_assets(self) -> None:
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        for asset in ('style.css', 'localization.js', 'relationships.js', 'app.js'):
            self.assertIn(f'/static/{asset}?v={__version__}', response.text)


if __name__ == '__main__':
    unittest.main()
