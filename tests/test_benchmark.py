import hashlib
import json

import pytest

from scripts.benchmark import (
    BenchmarkResult,
    _load_manifest,
    _load_report,
    _write_report,
    find_output_changes,
    find_regressions,
    find_throughput_shortfalls,
)


def _result(
    median_seconds: float,
    input_sha256: str | None = None,
    *,
    output_chars: int | None = None,
    output_sha256: str | None = None,
    peak_rss_bytes: int | None = None,
) -> BenchmarkResult:
    return BenchmarkResult(
        input_chars=100,
        loops_per_sample=1,
        samples=9,
        median_seconds=median_seconds,
        p95_seconds=median_seconds,
        throughput_chars_per_second=100 / median_seconds if median_seconds else 0,
        input_sha256=input_sha256,
        output_chars=output_chars,
        output_sha256=output_sha256,
        peak_rss_bytes=peak_rss_bytes,
    )


def test_find_throughput_shortfalls_reports_only_scenarios_below_the_floor() -> None:
    # _result(median) даёт throughput = 100 / median.
    current = {"fast": _result(0.001), "slow": _result(1.0)}

    shortfalls = find_throughput_shortfalls(current, 1000.0)

    assert shortfalls == [("slow", 100.0)]


def test_find_throughput_shortfalls_is_disabled_without_a_floor() -> None:
    """Порог по умолчанию не проверяется, иначе PR-gate стал бы флаки на CI."""
    current = {"slow": _result(1.0)}

    assert find_throughput_shortfalls(current, None) == []


def test_find_throughput_shortfalls_accepts_a_scenario_exactly_at_the_floor() -> None:
    current = {"exact": _result(1.0)}

    assert find_throughput_shortfalls(current, 100.0) == []


def test_find_throughput_shortfalls_rejects_a_negative_floor() -> None:
    with pytest.raises(ValueError, match="не может быть отрицательным"):
        find_throughput_shortfalls({"any": _result(1.0)}, -1.0)


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


def test_find_regressions_compares_timings_despite_a_different_output_hash() -> None:
    """Осознанная смена нормализации не должна ронять сравнение времени."""
    regressions = find_regressions(
        {
            "scenario": _result(1.5, "a" * 64, output_chars=11, output_sha256="c" * 64)
        },
        {
            "scenario": _result(1.0, "a" * 64, output_chars=10, output_sha256="d" * 64)
        },
        max_regression_percent=25.0,
    )

    assert [regression.scenario for regression in regressions] == ["scenario"]


def test_find_output_changes_reports_a_different_output_hash() -> None:
    current = {"scenario": _result(1.0, "a" * 64, output_chars=10, output_sha256="c" * 64)}
    baseline = {"scenario": _result(1.0, "a" * 64, output_chars=10, output_sha256="d" * 64)}

    assert find_output_changes(current, baseline) == ["scenario"]


def test_find_output_changes_reports_a_different_output_size() -> None:
    current = {"scenario": _result(1.0, "a" * 64, output_chars=11, output_sha256="c" * 64)}
    baseline = {"scenario": _result(1.0, "a" * 64, output_chars=10, output_sha256="c" * 64)}

    assert find_output_changes(current, baseline) == ["scenario"]


def test_find_output_changes_is_silent_when_the_output_matches() -> None:
    current = {
        "stable": _result(1.0, "a" * 64, output_chars=10, output_sha256="c" * 64),
        "no_output_metrics": _result(1.0, "a" * 64),
    }
    baseline = {
        "stable": _result(2.0, "a" * 64, output_chars=10, output_sha256="c" * 64),
        "no_output_metrics": _result(2.0, "a" * 64),
    }

    assert find_output_changes(current, baseline) == []


def test_find_output_changes_skips_a_scenario_missing_from_baseline() -> None:
    """Расхождение наборов сценариев — забота find_regressions, не этой функции."""
    current = {"added": _result(1.0, "a" * 64, output_chars=10, output_sha256="c" * 64)}

    assert find_output_changes(current, {}) == []


def test_find_regressions_reports_peak_rss_regression() -> None:
    regressions = find_regressions(
        {"scenario": _result(1.0, peak_rss_bytes=131)},
        {"scenario": _result(1.0, peak_rss_bytes=100)},
        max_regression_percent=25.0,
        max_memory_regression_percent=30.0,
    )

    assert [(item.metric, item.change_percent) for item in regressions] == [
        ("peak_rss_bytes", pytest.approx(31.0))
    ]


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

    assert [(book.name, book.input_chars, book.input_sha256) for book in books] == [
        ("example", len(text), hashlib.sha256(raw).hexdigest())
    ]
    assert books[0].text is None
    assert books[0].load_case().text == text
    prefix = books[0].load_case(10)
    assert prefix.name == "example_prefix_10"
    assert prefix.input_sha256 == hashlib.sha256(text[:10].encode("utf-8")).hexdigest()
    with pytest.raises(ValueError, match="длиннее текста"):
        books[0].load_case(len(text) + 1)
    book.write_text("изменённая версия", encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="изменился после проверки"):
        books[0].load_case()


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


def test_report_round_trip_preserves_output_and_memory_metrics(tmp_path) -> None:
    report_path = tmp_path / "benchmark.json"
    result = _result(
        1.25,
        "a" * 64,
        output_chars=123,
        output_sha256="b" * 64,
        peak_rss_bytes=456,
    )

    _write_report(
        report_path,
        {"scenario": result},
        samples=9,
        warmups=1,
        target_sample_seconds=0.15,
    )

    assert _load_report(report_path) == {"scenario": result}
