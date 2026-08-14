import hashlib
import json

import pytest

from scripts.benchmark import BenchmarkResult, _load_manifest, find_regressions


def _result(median_seconds: float, input_sha256: str | None = None) -> BenchmarkResult:
    return BenchmarkResult(
        input_chars=100,
        loops_per_sample=1,
        samples=9,
        median_seconds=median_seconds,
        p95_seconds=median_seconds,
        throughput_chars_per_second=100 / median_seconds if median_seconds else 0,
        input_sha256=input_sha256,
    )


def test_find_regressions_reports_only_scenario_above_threshold() -> None:
    baseline = {"stable": _result(1.0), "slow": _result(1.0)}
    current = {"stable": _result(1.25), "slow": _result(1.251)}

    regressions = find_regressions(current, baseline, max_regression_percent=25.0)

    assert [regression.scenario for regression in regressions] == ["slow"]
    assert regressions[0].change_percent == pytest.approx(25.1)


def test_find_regressions_rejects_mismatched_scenarios() -> None:
    with pytest.raises(ValueError, match="Наборы сценариев не совпадают"):
        find_regressions(
            {"current": _result(1.0)},
            {"baseline": _result(1.0)},
            max_regression_percent=25.0,
        )


def test_find_regressions_rejects_invalid_baseline() -> None:
    with pytest.raises(ValueError, match="Некорректная baseline-медиана"):
        find_regressions(
            {"scenario": _result(1.0)},
            {"scenario": _result(0.0)},
            max_regression_percent=25.0,
        )


def test_find_regressions_rejects_different_book_size() -> None:
    baseline = _result(1.0)
    current = BenchmarkResult(
        input_chars=101,
        loops_per_sample=1,
        samples=9,
        median_seconds=1.0,
        p95_seconds=1.0,
        throughput_chars_per_second=101.0,
    )

    with pytest.raises(ValueError, match="Размер входа"):
        find_regressions(
            {"scenario": current},
            {"scenario": baseline},
            max_regression_percent=25.0,
        )


def test_find_regressions_rejects_different_input_hash() -> None:
    with pytest.raises(ValueError, match="SHA-256 входа"):
        find_regressions(
            {"scenario": _result(1.0, "a" * 64)},
            {"scenario": _result(1.0, "b" * 64)},
            max_regression_percent=25.0,
        )


def test_load_manifest_reads_and_verifies_plain_text(tmp_path) -> None:
    book = tmp_path / "example.txt"
    text = "В 1856 году было 12 измерений.\n"
    book.write_text(text, encoding="utf-8", newline="")
    raw = book.read_bytes()
    manifest = tmp_path / "MANIFEST.json"
    manifest.write_text(
        json.dumps(
            {
                "works": [
                    {
                        "plain_text_file": book.name,
                        "verification": {
                            "bytes": len(raw),
                            "characters": len(text),
                            "sha256": hashlib.sha256(raw).hexdigest(),
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    books = _load_manifest(manifest)

    assert [(book.name, len(book.text), book.input_sha256) for book in books] == [
        ("example", len(text), hashlib.sha256(raw).hexdigest())
    ]


def test_load_manifest_rejects_changed_plain_text(tmp_path) -> None:
    book = tmp_path / "example.txt"
    book.write_text("исходная версия", encoding="utf-8")
    manifest = tmp_path / "MANIFEST.json"
    manifest.write_text(
        json.dumps(
            {
                "works": [
                    {
                        "plain_text_file": book.name,
                        "verification": {"sha256": "a" * 64},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="SHA-256 корпуса"):
        _load_manifest(manifest)
