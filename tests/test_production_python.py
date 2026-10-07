"""Every gate, the linters and the package name the Python that production runs.

Production runs the Dockerfile's image, rebuilt on the server within minutes of a
merge to main. A gate on a newer Python passes code that image cannot run: an
f-string that reuses its quotes or a `type` statement (3.12 syntax) stops the app
from starting, and `itertools.batched` (new in 3.12) fails the request that calls
it. A newer gate also checks other numbers: from 3.12, `sum()` adds floats with
compensation, so the explorer's results differ from 3.11's in their last digits.
"""

import re
import tomllib
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github' / 'workflows'

FROM_IMAGE = re.compile(r'^FROM\s+(\S+)', re.MULTILINE)
PYTHON_IMAGE = re.compile(r'python:(\d+\.\d+)(?:[.@:-]\S*)?')
SETUP_PYTHON = re.compile(r'^\s*(?:-\s+)?uses:\s*actions/setup-python@', re.MULTILINE)
PYTHON_VERSION = re.compile(r'^\s*python-version:\s*(.*?)\s*$', re.MULTILINE)
VERSION_VALUE = re.compile(r'(["\']?)(\d+\.\d+)\1')


def production_python() -> str:
    """The Python of the image production runs, as major.minor."""
    images = FROM_IMAGE.findall((ROOT / 'Dockerfile').read_text(encoding='utf-8'))
    versions: set[str] = set()
    for image in images:
        match = PYTHON_IMAGE.fullmatch(image)
        if match is None:
            raise AssertionError(
                f'Dockerfile: FROM {image} is not a python:<major>.<minor> image, '
                'so the Python production runs is unknown.'
            )
        versions.add(match.group(1))
    if len(versions) != 1:
        raise AssertionError(
            f'Dockerfile: expected one Python, found {sorted(versions) or "none"}.'
        )
    return versions.pop()


class ProductionPythonTest(unittest.TestCase):
    # Up to 0.30.0 the image ran 3.11, while the test gates ran 3.13, the style
    # and type gates 3.12, ruff targeted 3.12, pyright checked for 3.12 and
    # requires-python allowed 3.9.

    version: str
    pyproject: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.version = production_python()
        cls.pyproject = tomllib.loads(
            (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
        )

    def test_the_package_requires_production_python(self) -> None:
        # A lower floor promises versions no gate tests; a higher one would refuse
        # to install in the image.
        self.assertEqual(
            self.pyproject['project']['requires-python'],
            f'>={self.version}',
            f"requires-python must be >={self.version}, the Dockerfile's Python.",
        )

    def test_ruff_targets_production_python(self) -> None:
        self.assertEqual(
            self.pyproject['tool']['ruff']['target-version'],
            'py' + self.version.replace('.', ''),
            f"ruff must target the Dockerfile's Python, {self.version}.",
        )

    def test_pyright_checks_for_production_python(self) -> None:
        self.assertEqual(
            self.pyproject['tool']['pyright']['pythonVersion'],
            self.version,
            f"pyright must check for the Dockerfile's Python, {self.version}.",
        )

    def test_every_workflow_runs_production_python(self) -> None:
        workflows = sorted([*WORKFLOWS.glob('*.yml'), *WORKFLOWS.glob('*.yaml')])
        self.assertTrue(workflows, f'No workflows in {WORKFLOWS}.')
        for workflow in workflows:
            with self.subTest(workflow=workflow.name):
                text = workflow.read_text(encoding='utf-8')
                setups = len(SETUP_PYTHON.findall(text))
                values = PYTHON_VERSION.findall(text)
                # Without actions/setup-python a job runs the runner's own Python.
                self.assertGreater(
                    setups,
                    0,
                    f'{workflow.name} sets up no Python with actions/setup-python.',
                )
                # A matrix or a python-version-file would name versions this test
                # cannot read, so each step names its one version itself.
                self.assertEqual(
                    len(values),
                    setups,
                    f'{workflow.name}: each actions/setup-python step must name its '
                    'Python in one python-version line, and nothing else may.',
                )
                for value in values:
                    match = VERSION_VALUE.fullmatch(value)
                    if match is None:
                        self.fail(
                            f'{workflow.name}: python-version: {value} is not one '
                            'major.minor version.'
                        )
                    self.assertEqual(
                        match.group(2),
                        self.version,
                        f'{workflow.name} runs Python {match.group(2)}; production '
                        f'runs {self.version} (Dockerfile).',
                    )


if __name__ == '__main__':
    unittest.main()
