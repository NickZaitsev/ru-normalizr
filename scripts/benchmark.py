"""Измерение и сравнение производительности полного пайплайна нормализации."""

from __future__ import annotations

import argparse
import gc
import json
import math
import platform
import statistics
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ru_normalizr import NormalizeOptions, Normalizer

SCHEMA_VERSION = 1
DEFAULT_MAX_REGRESSION_PERCENT = 25.0
DEFAULT_BOOK_SIZE = 500_000


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """Текст книги для одного типа нагрузки."""

    name: str
    text: str


@dataclass(frozen=True)
class BenchmarkResult:
    """Агрегированные метрики одного сценария."""

    input_chars: int
    loops_per_sample: int
    samples: int
    median_seconds: float
    p95_seconds: float
    throughput_chars_per_second: float


@dataclass(frozen=True)
class Regression:
    """Сценарий, вышедший за допустимую границу замедления."""

    scenario: str
    baseline_seconds: float
    current_seconds: float
    change_percent: float


@dataclass(frozen=True)
class _Scenario:
    name: str
    input_chars: int
    operation: Callable[[], object]


def _repeated_sample(fragment: str, size: int) -> str:
    repetitions = size // len(fragment) + 1
    return (fragment * repetitions)[:size]


def _synthetic_cases(size: int) -> dict[str, BenchmarkCase]:
    return {
        "plain": BenchmarkCase(
            "plain",
            _repeated_sample(
                "Обычный русский текст без специальных конструкций. "
                "Библиотека должна сохранить смысл, пробелы и пунктуацию. ",
                size,
            ),
        ),
        "mixed": BenchmarkCase(
            "mixed",
            _repeated_sample(
                "Глава IV. В 1991–2002 годах компания ABC Ltd. выпустила 15 моделей "
                "iPhone 12. Встреча 12.05.2025 в 10:07. Объём 3,5 ТБ, скорость "
                "100 МБ/с, точность 99,5%. ",
                size,
            ),
        ),
        "number-dense": BenchmarkCase(
            "number-dense",
            _repeated_sample(
                "В 1995 году 125 человек купили 3,5 кг по цене 1 250 руб. "
                "с 5 по 10 января; температура 25 °C, главы IV–VI. ",
                size,
            ),
        ),
    }


def _resolve_book_text(path: Path) -> Path:
    if path.is_file():
        return path
    extracted_text = path / "text.txt"
    if extracted_text.is_file():
        return extracted_text
    raise FileNotFoundError(f"Не найден текст книги: {path}")


def _options_for_mode(mode: str) -> NormalizeOptions:
    return NormalizeOptions.tts() if mode == "tts" else NormalizeOptions.safe()


def find_regressions(
    current: Mapping[str, BenchmarkResult],
    baseline: Mapping[str, BenchmarkResult],
    max_regression_percent: float,
) -> list[Regression]:
    """Вернуть сценарии, медиана которых замедлилась сильнее допустимого."""

    if max_regression_percent < 0:
        raise ValueError("Допустимая регрессия не может быть отрицательной")
    if current.keys() != baseline.keys():
        missing = sorted(baseline.keys() - current.keys())
        extra = sorted(current.keys() - baseline.keys())
        raise ValueError(
            "Наборы сценариев не совпадают"
            f" (отсутствуют: {missing or 'нет'}; лишние: {extra or 'нет'})"
        )

    regressions: list[Regression] = []
    for name, current_result in current.items():
        baseline_result = baseline[name]
        if current_result.input_chars != baseline_result.input_chars:
            raise ValueError(
                f"Размер входа сценария {name!r} изменился: "
                f"{baseline_result.input_chars} -> {current_result.input_chars}"
            )
        if baseline_result.median_seconds <= 0:
            raise ValueError(f"Некорректная baseline-медиана сценария {name!r}")
        change_percent = (
            current_result.median_seconds / baseline_result.median_seconds - 1
        ) * 100
        if change_percent > max_regression_percent:
            regressions.append(
                Regression(
                    scenario=name,
                    baseline_seconds=baseline_result.median_seconds,
                    current_seconds=current_result.median_seconds,
                    change_percent=change_percent,
                )
            )
    return regressions


def _build_scenarios(
    *, size: int, case_names: Sequence[str], modes: Sequence[str], book: Path | None
) -> tuple[_Scenario, ...]:
    available_cases = _synthetic_cases(size)
    cases = [available_cases[name] for name in case_names]
    if book is not None:
        book_path = _resolve_book_text(book)
        cases.append(BenchmarkCase("book", book_path.read_text(encoding="utf-8")))

    scenarios: list[_Scenario] = []
    for case in cases:
        for mode in modes:
            normalizer = Normalizer(_options_for_mode(mode))
            scenarios.append(
                _Scenario(
                    name=f"{case.name}_{mode}",
                    input_chars=len(case.text),
                    operation=lambda case=case, normalizer=normalizer: normalizer.normalize(
                        case.text
                    ),
                )
            )
    return tuple(scenarios)


def _time_operation(operation: Callable[[], object], loops: int) -> float:
    started = time.perf_counter()
    for _ in range(loops):
        operation()
    return time.perf_counter() - started


def _measure_scenario(
    scenario: _Scenario, *, samples: int, target_sample_seconds: float
) -> BenchmarkResult:
    # Первый замер одновременно прогревает ленивые словари и даёт начальную
    # оценку длительности. Для книжного входа это экономит один дорогой проход.
    loops = 1
    elapsed = _time_operation(scenario.operation, loops)
    while True:
        if elapsed >= target_sample_seconds / 2 or loops >= 1024:
            loops = max(1, round(loops * target_sample_seconds / max(elapsed, 1e-9)))
            break
        loops *= 2
        elapsed = _time_operation(scenario.operation, loops)

    durations: list[float] = []
    for _ in range(samples):
        gc.collect()
        durations.append(_time_operation(scenario.operation, loops) / loops)

    ordered = sorted(durations)
    median_seconds = statistics.median(ordered)
    p95_index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return BenchmarkResult(
        input_chars=scenario.input_chars,
        loops_per_sample=loops,
        samples=samples,
        median_seconds=median_seconds,
        p95_seconds=ordered[p95_index],
        throughput_chars_per_second=scenario.input_chars / median_seconds,
    )


def _run_benchmarks(
    *,
    samples: int,
    target_sample_seconds: float,
    size: int,
    case_names: Sequence[str],
    modes: Sequence[str],
    book: Path | None,
) -> dict[str, BenchmarkResult]:
    return {
        scenario.name: _measure_scenario(
            scenario,
            samples=samples,
            target_sample_seconds=target_sample_seconds,
        )
        for scenario in _build_scenarios(
            size=size,
            case_names=case_names,
            modes=modes,
            book=book,
        )
    }


def _write_report(
    path: Path,
    results: Mapping[str, BenchmarkResult],
    *,
    samples: int,
    target_sample_seconds: float,
) -> None:
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "samples": samples,
        "target_sample_seconds": target_sample_seconds,
        "scenarios": {name: asdict(result) for name, result in results.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_report(path: Path) -> dict[str, BenchmarkResult]:
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Неподдерживаемая схема benchmark-отчёта: {path}")
    scenarios = raw.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        raise ValueError(f"Benchmark-отчёт не содержит сценариев: {path}")

    results: dict[str, BenchmarkResult] = {}
    try:
        for name, values in scenarios.items():
            if not isinstance(name, str) or not isinstance(values, dict):
                raise TypeError
            results[name] = BenchmarkResult(
                input_chars=int(values["input_chars"]),
                loops_per_sample=int(values["loops_per_sample"]),
                samples=int(values["samples"]),
                median_seconds=float(values["median_seconds"]),
                p95_seconds=float(values["p95_seconds"]),
                throughput_chars_per_second=float(values["throughput_chars_per_second"]),
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Повреждён benchmark-отчёт: {path}") from exc
    return results


def _print_results(
    current: Mapping[str, BenchmarkResult], baseline: Mapping[str, BenchmarkResult] | None
) -> None:
    if baseline is None:
        print("Сценарий            median, мс   p95, мс   символов/с")
        for name, result in current.items():
            print(
                f"{name:<20} {result.median_seconds * 1000:>10.2f}"
                f" {result.p95_seconds * 1000:>9.2f}"
                f" {result.throughput_chars_per_second:>12,.0f}"
            )
        return

    print("Сценарий            base, мс   current, мс   изменение   символов/с")
    for name, result in current.items():
        baseline_result = baseline[name]
        change = (result.median_seconds / baseline_result.median_seconds - 1) * 100
        print(
            f"{name:<20} {baseline_result.median_seconds * 1000:>9.2f}"
            f" {result.median_seconds * 1000:>13.2f}"
            f" {change:>+10.1f}%"
            f" {result.throughput_chars_per_second:>12,.0f}"
        )


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("значение должно быть больше нуля")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("значение должно быть больше нуля")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="сохранить метрики в JSON")
    parser.add_argument("--compare", type=Path, help="сравнить с JSON baseline")
    parser.add_argument("--book", type=Path, help="UTF-8 файл книги или каталог с text.txt")
    parser.add_argument("--mode", choices=("safe", "tts", "both"), default="both")
    parser.add_argument(
        "--case",
        choices=("plain", "mixed", "number-dense"),
        action="append",
        dest="cases",
        help="синтетическая книга; параметр можно повторить (по умолчанию: все)",
    )
    parser.add_argument(
        "--size",
        type=_positive_int,
        default=DEFAULT_BOOK_SIZE,
        help="размер каждой синтетической книги в символах (по умолчанию: 500000)",
    )
    parser.add_argument(
        "--max-regression-percent",
        type=float,
        default=DEFAULT_MAX_REGRESSION_PERCENT,
        help="допустимое замедление медианы по сценарию (по умолчанию: 25)",
    )
    parser.add_argument("--samples", "--repeats", type=_positive_int, default=5)
    parser.add_argument(
        "--target-sample-seconds",
        type=_positive_float,
        default=0.15,
        help="целевая длительность одного замера после автокалибровки",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        baseline = _load_report(args.compare) if args.compare else None
        modes = ("safe", "tts") if args.mode == "both" else (args.mode,)
        case_names = tuple(args.cases or ("plain", "mixed", "number-dense"))
        current = _run_benchmarks(
            samples=args.samples,
            target_sample_seconds=args.target_sample_seconds,
            size=args.size,
            case_names=case_names,
            modes=modes,
            book=args.book,
        )
        _print_results(current, baseline)
        if args.json:
            _write_report(
                args.json,
                current,
                samples=args.samples,
                target_sample_seconds=args.target_sample_seconds,
            )
        if baseline is None:
            return 0

        regressions = find_regressions(current, baseline, args.max_regression_percent)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"benchmark: {exc}", file=sys.stderr)
        return 2

    if regressions:
        print(
            f"Регрессия превышает допустимые {args.max_regression_percent:g}%:",
            file=sys.stderr,
        )
        for regression in regressions:
            print(
                f"- {regression.scenario}: {regression.change_percent:+.1f}%",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
