"""Измерение и сравнение производительности полного пайплайна нормализации."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import platform
import statistics
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ru_normalizr import NormalizeOptions, Normalizer

SCHEMA_VERSION = 3
DEFAULT_MAX_REGRESSION_PERCENT = 25.0
DEFAULT_MAX_MEMORY_REGRESSION_PERCENT = 30.0
DEFAULT_BOOK_SIZE = 500_000


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """Текст книги для одного типа нагрузки."""

    name: str
    text: str
    input_sha256: str


@dataclass(frozen=True, slots=True)
class CorpusSpec:
    """Проверенный источник корпуса, загружаемый только перед своим сценарием."""

    name: str
    input_sha256: str
    input_bytes: int
    input_chars: int
    path: Path | None = None
    text: str | None = None

    def load_case(self, prefix_chars: int | None = None) -> BenchmarkCase:
        if self.text is not None:
            text = self.text
        elif self.path is not None:
            if self.path.stat().st_size != self.input_bytes:
                raise ValueError(f"Корпус {self.name!r} изменился после проверки размера")
            with self.path.open("r", encoding="utf-8", newline="") as stream:
                text = stream.read()
            if len(text) != self.input_chars or _file_sha256(self.path) != self.input_sha256:
                raise ValueError(f"Корпус {self.name!r} изменился после проверки SHA-256")
        else:
            raise ValueError(f"У корпуса {self.name!r} отсутствует источник текста")

        case_name = self.name
        input_sha256 = self.input_sha256
        if prefix_chars is not None:
            if prefix_chars > len(text):
                raise ValueError(
                    f"Префикс корпуса {self.name!r} длиннее текста: "
                    f"{prefix_chars} -> {len(text)} символов"
                )
            text = text[:prefix_chars]
            case_name = f"{self.name}_prefix_{prefix_chars}"
            input_sha256 = _sha256_text(text)
        return BenchmarkCase(case_name, text, input_sha256)


@dataclass(frozen=True)
class BenchmarkResult:
    """Агрегированные метрики одного сценария."""

    input_chars: int
    loops_per_sample: int
    samples: int
    median_seconds: float
    p95_seconds: float
    throughput_chars_per_second: float
    input_sha256: str | None = None
    output_chars: int | None = None
    output_sha256: str | None = None
    peak_rss_bytes: int | None = None


@dataclass(frozen=True)
class Regression:
    """Сценарий, вышедший за допустимую границу замедления."""

    scenario: str
    baseline_seconds: float
    current_seconds: float
    change_percent: float
    metric: str = "median_seconds"


@dataclass(frozen=True)
class _Scenario:
    name: str
    input_chars: int
    input_sha256: str
    operation: Callable[[], object]


def _repeated_sample(fragment: str, size: int) -> str:
    repetitions = size // len(fragment) + 1
    return (fragment * repetitions)[:size]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _synthetic_cases(size: int) -> dict[str, BenchmarkCase]:
    plain = _repeated_sample(
        "Обычный русский текст без специальных конструкций. "
        "Библиотека должна сохранить смысл, пробелы и пунктуацию. ",
        size,
    )
    mixed = _repeated_sample(
        "Глава IV. В 1991–2002 годах компания ABC Ltd. выпустила 15 моделей "
        "iPhone 12. Встреча 12.05.2025 в 10:07. Объём 3,5 ТБ, скорость "
        "100 МБ/с, точность 99,5%. ",
        size,
    )
    number_dense = _repeated_sample(
        "В 1995 году 125 человек купили 3,5 кг по цене 1 250 руб. "
        "с 5 по 10 января; температура 25 °C, главы IV–VI. ",
        size,
    )
    return {
        "plain": BenchmarkCase("plain", plain, _sha256_text(plain)),
        "mixed": BenchmarkCase("mixed", mixed, _sha256_text(mixed)),
        "number-dense": BenchmarkCase("number-dense", number_dense, _sha256_text(number_dense)),
    }


def _synthetic_sources(size: int) -> dict[str, CorpusSpec]:
    return {
        name: CorpusSpec(
            name=case.name,
            input_sha256=case.input_sha256,
            input_bytes=len(case.text.encode("utf-8")),
            input_chars=len(case.text),
            text=case.text,
        )
        for name, case in _synthetic_cases(size).items()
    }


def _resolve_book_text(path: Path) -> Path:
    if path.is_file():
        return path
    extracted_text = path / "text.txt"
    if extracted_text.is_file():
        return extracted_text
    raise FileNotFoundError(f"Не найден текст книги: {path}")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_sha256(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in value)
    ):
        raise ValueError(f"Некорректный SHA-256 для {label}")
    return value.lower()


def _inspect_book(
    path: Path,
    *,
    name: str,
    expected_sha256: str | None = None,
    expected_bytes: int | None = None,
    expected_chars: int | None = None,
) -> CorpusSpec:
    book_path = _resolve_book_text(path)
    actual_bytes = book_path.stat().st_size
    if expected_bytes is not None and actual_bytes != expected_bytes:
        raise ValueError(
            f"Размер корпуса {name!r} не совпадает с MANIFEST: "
            f"{expected_bytes} -> {actual_bytes} байт"
        )

    actual_sha256 = _file_sha256(book_path)
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise ValueError(
            f"SHA-256 корпуса {name!r} не совпадает с MANIFEST: "
            f"ожидался {expected_sha256}, получен {actual_sha256}"
        )

    with book_path.open("r", encoding="utf-8", newline="") as stream:
        text = stream.read()
    if expected_chars is not None and len(text) != expected_chars:
        raise ValueError(
            f"Число символов корпуса {name!r} не совпадает с MANIFEST: "
            f"{expected_chars} -> {len(text)}"
        )
    return CorpusSpec(
        name=name,
        input_sha256=actual_sha256,
        input_bytes=actual_bytes,
        input_chars=len(text),
        path=book_path,
    )


def _load_manifest(path: Path, names: Sequence[str] = ()) -> tuple[CorpusSpec, ...]:
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("works"), list):
        raise ValueError(f"MANIFEST не содержит массива works: {path}")

    books: list[CorpusSpec] = []
    seen_names: set[str] = set()
    selected_names = set(names)
    selected_found: set[str] = set()
    for index, entry in enumerate(raw["works"]):
        if not isinstance(entry, dict):
            raise ValueError(f"Некорректная запись works[{index}] в MANIFEST: {path}")
        plain_text_file = entry.get("plain_text_file")
        if not isinstance(plain_text_file, str) or not plain_text_file:
            raise ValueError(f"В works[{index}] отсутствует plain_text_file: {path}")

        relative_path = Path(plain_text_file)
        book_path = relative_path if relative_path.is_absolute() else path.parent / relative_path
        name = relative_path.stem or f"book-{index + 1}"
        if name in seen_names:
            raise ValueError(f"Дублирующееся имя корпуса {name!r} в MANIFEST: {path}")
        seen_names.add(name)
        if selected_names and name not in selected_names:
            continue
        selected_found.add(name)

        verification = entry.get("verification", {})
        if not isinstance(verification, dict):
            raise ValueError(f"Некорректный verification для {name!r} в MANIFEST: {path}")
        expected_sha256 = verification.get("sha256")
        if expected_sha256 is not None and not isinstance(expected_sha256, str):
            raise ValueError(f"Некорректный sha256 для {name!r} в MANIFEST: {path}")
        if expected_sha256 is not None:
            expected_sha256 = _validated_sha256(expected_sha256, label=name)
        expected_bytes = verification.get("bytes")
        if expected_bytes is not None and not isinstance(expected_bytes, int):
            raise ValueError(f"Некорректный bytes для {name!r} в MANIFEST: {path}")
        expected_chars = verification.get("characters")
        if expected_chars is not None and not isinstance(expected_chars, int):
            raise ValueError(f"Некорректный characters для {name!r} в MANIFEST: {path}")

        books.append(
            _inspect_book(
                book_path,
                name=name,
                expected_sha256=expected_sha256,
                expected_bytes=expected_bytes,
                expected_chars=expected_chars,
            )
        )
    unknown = sorted(selected_names - selected_found)
    if unknown:
        available = ", ".join(sorted(seen_names)) or "нет"
        raise ValueError(
            f"Неизвестный корпус: {unknown}; доступные корпуса: {available}"
        )
    if not books:
        raise ValueError(f"MANIFEST не содержит корпусов: {path}")
    return tuple(books)


def _options_for_mode(mode: str) -> NormalizeOptions:
    return NormalizeOptions.tts() if mode == "tts" else NormalizeOptions.safe()


def find_regressions(
    current: Mapping[str, BenchmarkResult],
    baseline: Mapping[str, BenchmarkResult],
    max_regression_percent: float,
    max_memory_regression_percent: float | None = None,
) -> list[Regression]:
    """Вернуть сценарии, медиана которых замедлилась сильнее допустимого."""

    if max_regression_percent < 0:
        raise ValueError("Допустимая регрессия не может быть отрицательной")
    if max_memory_regression_percent is not None and max_memory_regression_percent < 0:
        raise ValueError("Допустимая регрессия памяти не может быть отрицательной")
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
        if (
            current_result.input_sha256 is not None
            or baseline_result.input_sha256 is not None
        ) and current_result.input_sha256 != baseline_result.input_sha256:
            raise ValueError(f"SHA-256 входа сценария {name!r} изменился")
        if (
            current_result.output_chars is not None
            or baseline_result.output_chars is not None
        ) and current_result.output_chars != baseline_result.output_chars:
            raise ValueError(f"Размер результата сценария {name!r} изменился")
        if (
            current_result.output_sha256 is not None
            or baseline_result.output_sha256 is not None
        ) and current_result.output_sha256 != baseline_result.output_sha256:
            raise ValueError(f"SHA-256 результата сценария {name!r} изменился")
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
        if max_memory_regression_percent is not None:
            baseline_rss = baseline_result.peak_rss_bytes
            current_rss = current_result.peak_rss_bytes
            if (baseline_rss is None) != (current_rss is None):
                raise ValueError(f"Метрика памяти сценария {name!r} отсутствует в одном отчёте")
            if baseline_rss is not None and current_rss is not None:
                if baseline_rss <= 0:
                    raise ValueError(f"Некорректный baseline peak RSS сценария {name!r}")
                memory_change_percent = (current_rss / baseline_rss - 1) * 100
                if memory_change_percent > max_memory_regression_percent:
                    regressions.append(
                        Regression(
                            scenario=name,
                            baseline_seconds=float(baseline_rss),
                            current_seconds=float(current_rss),
                            change_percent=memory_change_percent,
                            metric="peak_rss_bytes",
                        )
                    )
    return regressions


def _build_scenarios(
    *,
    size: int,
    case_names: Sequence[str],
    modes: Sequence[str],
    books: Sequence[CorpusSpec],
    include_synthetic: bool,
    prefix_chars: int | None,
) -> Iterator[_Scenario]:
    sources: list[CorpusSpec] = []
    if include_synthetic:
        available_sources = _synthetic_sources(size)
        sources.extend(available_sources[name] for name in case_names)
    sources.extend(books)
    if not sources:
        raise ValueError("Не выбран ни один benchmark-корпус")

    for source in sources:
        case = source.load_case(prefix_chars)
        for mode in modes:
            normalizer = Normalizer(_options_for_mode(mode))
            yield _Scenario(
                name=f"{case.name}_{mode}",
                input_chars=len(case.text),
                input_sha256=case.input_sha256,
                operation=lambda case=case, normalizer=normalizer: normalizer.normalize(
                    case.text
                ),
            )


def _output_identity(value: object) -> tuple[int, str]:
    if not isinstance(value, str):
        raise ValueError("Benchmark-операция должна возвращать строку")
    return len(value), _sha256_text(value)


def _peak_rss_bytes() -> int | None:
    """Return process peak RSS where the standard library exposes it."""

    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class _ProcessMemoryCounters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("page_fault_count", wintypes.DWORD),
                    ("peak_working_set_size", ctypes.c_size_t),
                    ("working_set_size", ctypes.c_size_t),
                    ("quota_peak_paged_pool_usage", ctypes.c_size_t),
                    ("quota_paged_pool_usage", ctypes.c_size_t),
                    ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
                    ("quota_non_paged_pool_usage", ctypes.c_size_t),
                    ("pagefile_usage", ctypes.c_size_t),
                    ("peak_pagefile_usage", ctypes.c_size_t),
                    ("private_usage", ctypes.c_size_t),
                ]

            counters = _ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            win_dll = ctypes.WinDLL
            get_current_process = win_dll("kernel32").GetCurrentProcess
            get_memory_info = win_dll("psapi").GetProcessMemoryInfo
            get_current_process.restype = wintypes.HANDLE
            get_memory_info.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(_ProcessMemoryCounters),
                wintypes.DWORD,
            ]
            get_memory_info.restype = wintypes.BOOL
            if get_memory_info(
                get_current_process(), ctypes.byref(counters), counters.cb
            ):
                return int(counters.peak_working_set_size)
        except (AttributeError, OSError, TypeError):
            return None
        return None

    try:
        import resource
    except ImportError:
        return None
    value = int(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # pyright: ignore[reportAttributeAccessIssue]
    )
    # Linux reports KiB; macOS reports bytes. Windows has no resource module.
    return value if sys.platform == "darwin" else value * 1024


def _time_operation(
    operation: Callable[[], object],
    loops: int,
    expected_output: tuple[int, str] | None,
) -> tuple[float, tuple[int, str]]:
    elapsed = 0.0
    actual_output: tuple[int, str] | None = None
    for _ in range(loops):
        started = time.perf_counter()
        result = operation()
        elapsed += time.perf_counter() - started
        actual_output = _output_identity(result)
        if expected_output is not None and actual_output != expected_output:
            raise ValueError("Benchmark-операция вернула недетерминированный результат")
    if actual_output is None:
        raise ValueError("Число циклов benchmark должно быть положительным")
    return elapsed, actual_output


def _measure_scenario(
    scenario: _Scenario,
    *,
    samples: int,
    warmups: int,
    target_sample_seconds: float,
) -> BenchmarkResult:
    # Первый замер одновременно прогревает ленивые словари и даёт начальную
    # оценку длительности. Для книжного входа это экономит один дорогой проход.
    expected_output: tuple[int, str] | None = None
    for _ in range(warmups):
        _, expected_output = _time_operation(scenario.operation, 1, expected_output)

    loops = 1
    elapsed, expected_output = _time_operation(scenario.operation, loops, expected_output)
    while True:
        if elapsed >= target_sample_seconds / 2 or loops >= 1024:
            loops = max(1, round(loops * target_sample_seconds / max(elapsed, 1e-9)))
            break
        loops *= 2
        elapsed, expected_output = _time_operation(scenario.operation, loops, expected_output)

    durations: list[float] = []
    for _ in range(samples):
        gc.collect()
        elapsed, expected_output = _time_operation(scenario.operation, loops, expected_output)
        durations.append(elapsed / loops)

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
        input_sha256=scenario.input_sha256,
        output_chars=expected_output[0],
        output_sha256=expected_output[1],
        peak_rss_bytes=_peak_rss_bytes(),
    )


def _run_benchmarks(
    *,
    samples: int,
    target_sample_seconds: float,
    size: int,
    case_names: Sequence[str],
    modes: Sequence[str],
    books: Sequence[CorpusSpec],
    include_synthetic: bool,
    warmups: int,
    prefix_chars: int | None,
    partial_report: Path | None,
) -> dict[str, BenchmarkResult]:
    results: dict[str, BenchmarkResult] = {}
    for scenario in _build_scenarios(
        size=size,
        case_names=case_names,
        modes=modes,
        books=books,
        include_synthetic=include_synthetic,
        prefix_chars=prefix_chars,
    ):
        print(f"benchmark: измеряю {scenario.name} ({scenario.input_chars} символов)", flush=True)
        results[scenario.name] = _measure_scenario(
            scenario,
            samples=samples,
            warmups=warmups,
            target_sample_seconds=target_sample_seconds,
        )
        result = results[scenario.name]
        print(
            f"benchmark: готово {scenario.name}: "
            f"{result.median_seconds * 1000:.2f} мс, "
            f"{result.throughput_chars_per_second:,.0f} символов/с",
            flush=True,
        )
        if partial_report is not None:
            _write_report(
                partial_report,
                results,
                samples=samples,
                warmups=warmups,
                target_sample_seconds=target_sample_seconds,
            )
    return results


def _write_report(
    path: Path,
    results: Mapping[str, BenchmarkResult],
    *,
    samples: int,
    warmups: int,
    target_sample_seconds: float,
) -> None:
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "samples": samples,
        "warmups": warmups,
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
                input_sha256=_validated_sha256(values["input_sha256"], label=name),
                output_chars=int(values["output_chars"]),
                output_sha256=_validated_sha256(values["output_sha256"], label=name),
                peak_rss_bytes=(
                    int(values["peak_rss_bytes"])
                    if values["peak_rss_bytes"] is not None
                    else None
                ),
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Повреждён benchmark-отчёт: {path}") from exc
    return results


def _print_results(
    current: Mapping[str, BenchmarkResult], baseline: Mapping[str, BenchmarkResult] | None
) -> None:
    def rss_megabytes(result: BenchmarkResult) -> str:
        if result.peak_rss_bytes is None:
            return "-"
        return f"{result.peak_rss_bytes / (1024 * 1024):.1f}"

    if baseline is None:
        print("Сценарий            median, мс   p95, мс   символов/с   peak RSS, МБ")
        for name, result in current.items():
            print(
                f"{name:<20} {result.median_seconds * 1000:>10.2f}"
                f" {result.p95_seconds * 1000:>9.2f}"
                f" {result.throughput_chars_per_second:>12,.0f}"
                f" {rss_megabytes(result):>13}"
            )
        return

    print("Сценарий            base, мс   current, мс   изменение   символов/с   peak RSS, МБ")
    for name, result in current.items():
        baseline_result = baseline[name]
        change = (result.median_seconds / baseline_result.median_seconds - 1) * 100
        print(
            f"{name:<20} {baseline_result.median_seconds * 1000:>9.2f}"
            f" {result.median_seconds * 1000:>13.2f}"
            f" {change:>+10.1f}%"
            f" {result.throughput_chars_per_second:>12,.0f}"
            f" {rss_megabytes(result):>13}"
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


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("значение не может быть отрицательным")
    return parsed


def _load_cli_books(paths: Sequence[Path]) -> tuple[CorpusSpec, ...]:
    books: list[CorpusSpec] = []
    seen_names: set[str] = set()
    for index, path in enumerate(paths):
        resolved_path = _resolve_book_text(path)
        name = "book" if len(paths) == 1 else resolved_path.stem
        if name in seen_names:
            name = f"{name}-{index + 1}"
        seen_names.add(name)
        books.append(_inspect_book(path, name=name))
    return tuple(books)


def _select_books(books: Sequence[CorpusSpec], names: Sequence[str]) -> tuple[CorpusSpec, ...]:
    if not names:
        return tuple(books)
    by_name = {book.name: book for book in books}
    unknown = [name for name in names if name not in by_name]
    if unknown:
        available = ", ".join(sorted(by_name)) or "нет"
        raise ValueError(
            f"Неизвестный корпус: {unknown}; доступные корпуса: {available}"
        )
    return tuple(by_name[name] for name in names)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="сохранить метрики в JSON")
    parser.add_argument("--compare", type=Path, help="сравнить с JSON baseline")
    parser.add_argument(
        "--book",
        type=Path,
        action="append",
        dest="books",
        help="UTF-8 файл книги или каталог с text.txt; параметр можно повторить",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="MANIFEST.json с проверенными plain_text_file и SHA-256",
    )
    parser.add_argument(
        "--corpus",
        action="append",
        dest="corpora",
        help="имя корпуса из --manifest; параметр можно повторить",
    )
    parser.add_argument(
        "--real-only",
        action="store_true",
        help="измерять только --book/--manifest, без синтетических корпусов",
    )
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
    parser.add_argument(
        "--max-memory-regression-percent",
        type=float,
        default=DEFAULT_MAX_MEMORY_REGRESSION_PERCENT,
        help="допустимый рост peak RSS по сценарию (по умолчанию: 30)",
    )
    parser.add_argument("--samples", "--repeats", type=_positive_int, default=5)
    parser.add_argument(
        "--warmups",
        type=_nonnegative_int,
        default=1,
        help="число прогревочных проходов перед автокалибровкой (по умолчанию: 1)",
    )
    parser.add_argument(
        "--prefix-chars",
        type=_positive_int,
        help="измерять только префикс реального корпуса заданной длины",
    )
    parser.add_argument(
        "--partial-json",
        type=Path,
        help="после каждого сценария сохранять частичный JSON-отчёт",
    )
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
        requested_corpora = tuple(args.corpora or ())
        manifest_books = (
            _load_manifest(args.manifest, requested_corpora) if args.manifest else ()
        )
        cli_books = _load_cli_books(tuple(args.books or ()))
        books = _select_books((*manifest_books, *cli_books), requested_corpora)
        book_names = [book.name for book in books]
        if len(book_names) != len(set(book_names)):
            raise ValueError("Имена корпусов из --manifest и --book должны быть уникальными")
        current = _run_benchmarks(
            samples=args.samples,
            target_sample_seconds=args.target_sample_seconds,
            size=args.size,
            case_names=case_names,
            modes=modes,
            books=books,
            include_synthetic=not args.real_only,
            warmups=args.warmups,
            prefix_chars=args.prefix_chars,
            partial_report=args.partial_json,
        )
        _print_results(current, baseline)
        if args.json:
            _write_report(
                args.json,
                current,
                samples=args.samples,
                warmups=args.warmups,
                target_sample_seconds=args.target_sample_seconds,
            )
        if baseline is None:
            return 0

        regressions = find_regressions(
            current,
            baseline,
            args.max_regression_percent,
            args.max_memory_regression_percent,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"benchmark: {exc}", file=sys.stderr)
        return 2

    if regressions:
        print(
            f"Регрессия превышает допустимые {args.max_regression_percent:g}%:",
            file=sys.stderr,
        )
        for regression in regressions:
            value_unit = "байт" if regression.metric == "peak_rss_bytes" else "с"
            print(
                f"- {regression.scenario} ({regression.metric}): "
                f"{regression.change_percent:+.1f}% "
                f"({regression.baseline_seconds:.0f} -> "
                f"{regression.current_seconds:.0f} {value_unit})",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
