import json
from pathlib import Path
from typing import Any


def write_regression_fixture(target_file: str, payload_json: str) -> None:
    path = Path(target_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload_json, encoding='utf-8')


def read_regression_fixture(target_file: str) -> dict[str, Any]:
    path = Path(target_file)
    return json.loads(path.read_text(encoding='utf-8'))


def fixture_roundtrip_matches(
    target_file: str,
    payload_json: str,
    *,
    update_fixture: bool = False,
) -> bool:
    if update_fixture:
        write_regression_fixture(target_file, payload_json)

    path = Path(target_file)
    if not path.exists():
        return False

    loaded: dict[str, Any] = read_regression_fixture(target_file)
    return (
        json.dumps(loaded, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        == payload_json
    )
