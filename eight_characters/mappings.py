"""The app's two lookup tables, read once: each branch's hidden stems, and each
stem's Ten God to each Day Master (eight_characters/resources/mappings/)."""

import csv
from functools import lru_cache
from pathlib import Path

from eight_characters.ten_gods import TenGodName, parse_ten_gods_mapping

MAPPINGS_DIR = Path(__file__).resolve().parent / 'resources' / 'mappings'


def _extract_hidden_stem_char(entry: str) -> str:
    token = entry.strip()
    if not token:
        raise ValueError('Hidden stem entry cannot be empty.')
    parts = token.split()
    return parts[-1]


@lru_cache(maxsize=1)
def hidden_stems_lookup() -> dict[str, list[str]]:
    """Each branch's hidden stems, main qi first."""
    csv_path = MAPPINGS_DIR / 'hidden-stems.csv'
    if not csv_path.exists():
        raise RuntimeError(f'Hidden stems lookup not found: {csv_path}')

    lookup: dict[str, list[str]] = {}
    with csv_path.open('r', encoding='utf-8', newline='') as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            branch_col = (row.get('Earthly Branch') or '').strip()
            hidden_col = (
                row.get('Hidden Stems (Main, Middle, Residual Qi)') or ''
            ).strip()
            if not branch_col or not hidden_col:
                continue
            branch_char = branch_col[-1]
            entries = [item for item in hidden_col.split(',') if item.strip()]
            lookup[branch_char] = [_extract_hidden_stem_char(item) for item in entries]

    if not lookup:
        raise RuntimeError('Hidden stems lookup is empty.')
    return lookup


@lru_cache(maxsize=1)
def ten_gods_lookup() -> dict[tuple[str, str], TenGodName]:
    """Each (Day Master, stem) pair's Ten God."""
    return parse_ten_gods_mapping(MAPPINGS_DIR / 'ten-gods.csv')
