from __future__ import annotations

import argparse
import hashlib
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from ru_normalizr import NormalizeOptions, Normalizer


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    name: str
    text: str


def _repeated_sample(fragment: str, size: int) -> str:
    repetitions = size // len(fragment) + 1
    return (fragment * repetitions)[:size]


def _synthetic_cases(size: int) -> list[BenchmarkCase]:
    return [
        BenchmarkCase(
            "plain",
            _repeated_sample(
                "Обычный русский текст без специальных конструкций. "
                "Библиотека должна сохранить смысл, пробелы и пунктуацию. ",
                size,
            ),
        ),
        BenchmarkCase(
            "mixed",
            _repeated_sample(
                "Глава IV. В 1991–2002 годах компания ABC Ltd. выпустила 15 моделей "
                "iPhone 12. Встреча 12.05.2025 в 10:07. Объём 3,5 ТБ, скорость "
                "100 МБ/с, точность 99,5%. ",
                size,
            ),
        ),
        BenchmarkCase(
            "number-dense",
            _repeated_sample(
                "В 1995 году 125 человек купили 3,5 кг по цене 1 250 руб. "
                "с 5 по 10 января; температура 25 °C, главы IV–VI. ",
                size,
            ),
        ),
    ]


def _resolve_book_text(path: Path) -> Path:
    if path.is_file():
        return path
    extracted_text = path / "text.txt"
    if extracted_text.is_file():
        return extracted_text
    raise FileNotFoundError(f"No readable book text found at {path}")


def _options_for_mode(mode: str) -> NormalizeOptions:
    return NormalizeOptions.tts() if mode == "tts" else NormalizeOptions.safe()


def _run_case(
    case: BenchmarkCase,
    *,
    mode: str,
    repeats: int,
    warmups: int,
) -> None:
    normalizer = Normalizer(_options_for_mode(mode))
    for _ in range(warmups):
        normalizer.normalize(case.text)

    timings: list[float] = []
    output = ""
    for _ in range(repeats):
        started = time.perf_counter()
        output = normalizer.normalize(case.text)
        timings.append(time.perf_counter() - started)

    median_seconds = statistics.median(timings)
    throughput = len(case.text) / median_seconds
    digest = hashlib.sha256(output.encode("utf-8")).hexdigest()[:16]
    print(
        f"{case.name:14} {mode:4} chars={len(case.text):>8} "
        f"median={median_seconds:>8.3f}s throughput={throughput:>10,.0f} char/s "
        f"out={len(output):>8} sha256={digest}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark ru-normalizr workloads")
    parser.add_argument("--book", type=Path, help="UTF-8 text file or directory with text.txt")
    parser.add_argument("--mode", choices=("safe", "tts", "both"), default="both")
    parser.add_argument("--size", type=int, default=50_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    args = parser.parse_args()

    if args.size <= 0 or args.repeats <= 0 or args.warmups < 0:
        parser.error("--size and --repeats must be positive; --warmups cannot be negative")

    cases = _synthetic_cases(args.size)
    if args.book is not None:
        book_path = _resolve_book_text(args.book)
        cases.append(BenchmarkCase("book", book_path.read_text(encoding="utf-8")))

    modes = ("safe", "tts") if args.mode == "both" else (args.mode,)
    for case in cases:
        for mode in modes:
            _run_case(
                case,
                mode=mode,
                repeats=args.repeats,
                warmups=args.warmups,
            )


if __name__ == "__main__":
    main()
