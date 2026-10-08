"""Run static JavaScript, strict types, or browser checks from the repository."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('check', choices=['syntax', 'types', 'browser'])
    parser.add_argument('--browser', choices=['chromium', 'webkit'])
    parser.add_argument('--suite', choices=['controls', 'foundations', 'arcs'])
    parser.add_argument('--exclude', choices=['controls'])
    parser.add_argument(
        '--name', help='Run only browser test names matching this pattern'
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    if args.check == 'types':
        return subprocess.call([sys.executable, '-m', 'pyright'], cwd=root)
    node = os.environ['EC_NODE']
    if args.check == 'syntax':
        for source in sorted((root / 'eight_characters' / 'static').glob('*.js')):
            subprocess.run([node, '--check', str(source)], cwd=root, check=True)
        return 0
    if not args.browser:
        parser.error('browser checks require --browser')
    environment = dict(os.environ, EC_BROWSER=args.browser)
    sources = sorted((root / 'tests' / 'browser').glob('*.test.mjs'))
    if args.suite:
        sources = [source for source in sources if source.stem == args.suite + '.test']
    if args.exclude:
        sources = [
            source for source in sources if source.stem != args.exclude + '.test'
        ]
    command = [node, '--test', '--test-concurrency=1', '--test-reporter=tap']
    if args.name:
        command.extend(['--test-name-pattern', args.name])
    return subprocess.call(
        [*command, *map(str, sources)],
        cwd=root,
        env=environment,
    )


if __name__ == '__main__':
    sys.exit(main())
