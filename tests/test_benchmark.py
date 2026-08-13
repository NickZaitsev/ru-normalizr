import pytest

from scripts.benchmark import BenchmarkResult, find_regressions


def _result(median_seconds: float) -> BenchmarkResult:
    return BenchmarkResult(
        input_chars=100,
        loops_per_sample=1,
        samples=9,
        median_seconds=median_seconds,
        p95_seconds=median_seconds,
        throughput_chars_per_second=100 / median_seconds if median_seconds else 0,
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
