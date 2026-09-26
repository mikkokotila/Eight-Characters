import hashlib
import re
import unittest

from fastapi.testclient import TestClient

from eight_characters import __version__
from eight_characters.data import BRANCHES, STEMS
from eight_characters.engine import TERM_LABEL_BY_TARGET
from eight_characters.main import app
from eight_characters.policy import MAX_SUPPORTED_YEAR, MIN_SUPPORTED_YEAR

EXPLORER_ASSETS = ('styles.css', 'vendor/d3.v7.min.js', 'data.js', 'app.js')


SPACING_PROPERTIES = re.compile(
    r'^(margin|padding)(-(top|right|bottom|left|block|inline)(-(start|end))?)?$|^(row-|column-)?gap$'
)
RAW_LENGTH = re.compile(r'(?<![\w.-])-?\d*\.?\d+(px|em|rem)\b')


def _css_declarations(css: str) -> list[tuple[str, str, str]]:
    """(selector, property, value) of every declaration, with its innermost selector."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    selectors: list[str] = []
    found: list[tuple[str, str, str]] = []
    buffer = ''
    for char in css:
        if char in '{};':
            text = buffer.strip()
            buffer = ''
            if char == '{':
                selectors.append(text)
                continue
            if ':' in text:
                name, value = (part.strip() for part in text.split(':', 1))
                found.append((selectors[-1] if selectors else '', name, value))
            if char == '}':
                selectors.pop()
        else:
            buffer += char
    return found


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
            'relationships-topic',
            'relationships-heading',
            'relationship-list',
            'relationship-detail',
            'relationship-status',
        ):
            self.assertIn(f'id="{element_id}"', response.text)
        self.assertIn('aria-live="polite"', response.text)
        self.assertLess(
            response.text.index('/static/relationships.js'),
            response.text.index('/static/app.js'),
        )
        self.assertEqual(self.client.get('/static/relationships.js').status_code, 200)

    def test_chart_view_has_its_bar_and_panel(self) -> None:
        response = self.client.get('/')
        for element_id in (
            'display-switch',
            'view-switch',
            'chart-language',
            'copy-link-btn',
            'back-btn',
            'new-chart-btn',
            'chart-panel',
        ):
            self.assertIn(f'id="{element_id}"', response.text)
        # The view is chosen on a chart, not before one.
        self.assertNotIn('data-mode=', response.text)

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
            'palette.js',
            'spotlight.js',
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

    def test_pillar_change_view_names_what_the_engine_names(self) -> None:
        # The view names a change's far-side pillar and its solar term from its own
        # tables; both must match the engine's.
        script = self.client.get('/static/pillar-changes.js').text
        pinyin_block = re.search(r'const PINYIN = \{(.*?)\};', script, re.S)
        terms_block = re.search(r'const TERMS = \{(.*?)\};', script, re.S)
        if pinyin_block is None or terms_block is None:
            self.fail('pillar-changes.js has no PINYIN or TERMS table')
        pinyin = dict(re.findall(r"(\S): '([A-Za-z]+)'", pinyin_block.group(1)))
        self.assertEqual(
            pinyin,
            {
                char: info['pinyin']
                for char, info in (*STEMS.items(), *BRANCHES.items())
            },
        )
        terms = dict(re.findall(r"(\w+): '([A-Za-z]+)'", terms_block.group(1)))
        self.assertEqual(
            terms,
            {
                label: label.split('_')[0].capitalize()
                for label in TERM_LABEL_BY_TARGET.values()
            },
        )

    def test_stylesheet_takes_spacing_type_and_ink_from_its_tokens(self) -> None:
        # Values are defined once, as tokens on :root; everything else refers to them.
        problems: list[str] = []
        css = self.client.get('/static/style.css').text
        for selector, name, value in _css_declarations(css):
            if selector == ':root' or selector.startswith('@font-face'):
                continue
            where = f'{selector} {{ {name}: {value} }}'
            if 'rgba(42,37,32' in re.sub(r'\s+', '', value):
                problems.append(f'raw ink: {where}')
            tokens_removed = re.sub(r'var\(--[a-z0-9-]+\)', '', value)
            if name == 'font-size' and not re.fullmatch(r'var\(--text-\d\)', value):
                problems.append(f'font size off the scale: {where}')
            elif name == 'letter-spacing' and not re.fullmatch(
                r'var\(--tracking-\d\)|0|normal', value
            ):
                problems.append(f'tracking off the scale: {where}')
            elif SPACING_PROPERTIES.match(name) and RAW_LENGTH.search(tokens_removed):
                problems.append(f'raw spacing: {where}')
        self.assertEqual(problems, [])

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
