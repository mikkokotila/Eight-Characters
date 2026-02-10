import json
from pathlib import Path


def write_regression_fixture(target_file: str, payload_json: str) -> None:
    path = Path(target_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload_json, encoding='utf-8')


def read_regression_fixture(target_file: str) -> dict:
    path = Path(target_file)
    return json.loads(path.read_text(encoding='utf-8'))


def fixture_roundtrip_matches(target_file: str, payload_json: str) -> bool:
    write_regression_fixture(target_file, payload_json)
    loaded = read_regression_fixture(target_file)
    return json.dumps(loaded, ensure_ascii=False, sort_keys=True, separators=(',', ':')) == payload_json
