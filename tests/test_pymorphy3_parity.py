from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.pymorphy3_parity import (
    comparable_snapshot,
    compare_snapshots,
    write_snapshot,
)


def test_snapshot_json_is_stable_utf8(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    write_snapshot(path, {"слово": "ёж", "backend": {"extension_available": False}})
    assert path.read_bytes() == (
        '{\n  "backend": {\n    "extension_available": false\n'
        '  },\n  "слово": "ёж"\n}\n'
    ).encode()


def test_comparison_ignores_only_backend_implementation(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    common = {"parse": {"ёж": [{"word": "ёж"}]}}
    baseline.write_text(
        json.dumps(
            {**common, "backend": {"extension_available": False, "pymorphy3": "2.0.6"}}
        ),
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(
            {**common, "backend": {"extension_available": True, "pymorphy3": "2.0.6"}}
        ),
        encoding="utf-8",
    )
    assert compare_snapshots(baseline, candidate)


def test_comparison_detects_public_difference(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(
        json.dumps({"backend": {}, "normalize": {"1": {"result": "один"}}}),
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps({"backend": {}, "normalize": {"1": {"result": "раз"}}}),
        encoding="utf-8",
    )
    assert not compare_snapshots(baseline, candidate)


def test_comparable_snapshot_does_not_mutate_source() -> None:
    source = {"backend": {"extension_available": False, "pymorphy3": "2.0.6"}}
    assert comparable_snapshot(source) == {"backend": {"pymorphy3": "2.0.6"}}
    assert source["backend"]["extension_available"] is False


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_snapshot_fixture_can_be_read_with_explicit_utf8(
    tmp_path: Path, encoding: str
) -> None:
    path = tmp_path / "snapshot.json"
    path.write_text('{"backend": {}}', encoding=encoding)
    if encoding == "utf-8-sig":
        with pytest.raises(json.JSONDecodeError):
            json.loads(path.read_text(encoding="utf-8"))
    else:
        assert json.loads(path.read_text(encoding="utf-8")) == {"backend": {}}
