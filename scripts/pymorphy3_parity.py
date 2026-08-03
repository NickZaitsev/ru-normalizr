"""Create and compare deterministic public-API parity snapshots for pymorphy3.

Run this script from the repository root in two clean environments.  The
baseline must contain the portable DAWG backend and the candidate the compiled
backend; ``snapshot`` rejects an environment whose backend does not match the
declared expectation.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import num2words
import pymorphy3
from pymorphy3 import dawg

from ru_normalizr import normalize
from ru_normalizr.numerals._constants import UNITS_DATA

CASES = ("nomn", "gent", "datv", "accs", "ablt", "loct")
NUMBERS = ("sing", "plur")
GENDERS = ("masc", "femn", "neut")
SHAPE_FIXTURES = (
    "",
    "123",
    "XIV",
    "hello",
    "!",
    "неологизмоподобный",
    "Фёдор",
    "фёдор",
    "Федор",
    "федор",
)
AMBIGUOUS_FIXTURES = (
    "коллега",
    "сирота",
    "сутки",
    "ножницы",
    "дрова",
    "лира",
    "шекель",
    "грей",
    "паскаль",
    "вебер",
    "зиверт",
    "тенге",
    "вона",
    "фарад",
    "тесла",
    "моль",
    "пасть",
    "достигаем",
    "часовой",
)
CARDINAL_BOUNDARIES = (0, 1, 2, 4, 5, 11, 21, 22, 25, 99, 100, 101, 999, 1000, 2000)
ORDINAL_BOUNDARIES = (1, 2, 3, 20, 21, 100, 101, 1000, 2020, 9999)


def _unit_parts(info: object) -> tuple[str, ...]:
    if isinstance(info, tuple):
        return tuple(str(value) for value in info if value)
    values = []
    for name in ("lemma", "suffix", "morphology_seed"):
        value = getattr(info, name, None)
        if value:
            values.append(str(value))
    return tuple(values)


def _test_string_literals(root: Path) -> set[str]:
    values: set[str] = set()
    for path in sorted((root / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value.strip()
                if value and any(char.isalpha() for char in value):
                    values.add(value)
    return values


def _generated_words() -> set[str]:
    words: set[str] = set()
    for value in CARDINAL_BOUNDARIES:
        words.update(num2words.num2words(value, lang="ru").replace("-", " ").split())
    for value in ORDINAL_BOUNDARIES:
        words.update(
            num2words.num2words(value, lang="ru", to="ordinal").replace("-", " ").split()
        )
    return words


def build_corpora(root: Path) -> tuple[list[str], list[str], list[str]]:
    unit_values = {
        part
        for token, info in UNITS_DATA.items()
        for part in (str(token), *_unit_parts(info))
        if part
    }
    test_strings = _test_string_literals(root)
    normalize_corpus = sorted(test_strings)
    morphology_corpus = sorted(
        {
            *SHAPE_FIXTURES,
            *AMBIGUOUS_FIXTURES,
            *_generated_words(),
            *unit_values,
            *(word for text in test_strings for word in text.split()),
        }
    )
    lexeme_corpus = sorted({*AMBIGUOUS_FIXTURES, *_generated_words(), *unit_values})
    return normalize_corpus, morphology_corpus, lexeme_corpus


def _parse_signature(parse: Any) -> dict[str, object]:
    return {
        "normal_form": parse.normal_form,
        "score": parse.score,
        "tag": str(parse.tag),
        "word": parse.word,
    }


def _call_signature(callable_: Any, *args: object) -> dict[str, object]:
    try:
        return {"result": callable_(*args)}
    except Exception as exc:  # parity includes the public failure contract
        return {"exception": f"{type(exc).__module__}.{type(exc).__qualname__}: {exc}"}


def _inflect_signature(parse: Any, grammemes: list[str]) -> object:
    inflected = parse.inflect(set(grammemes))
    if inflected is None:
        return None
    return {
        "normal_form": inflected.normal_form,
        "tag": str(inflected.tag),
        "word": inflected.word,
    }


def _inflection_signatures(morph: pymorphy3.MorphAnalyzer, words: Iterable[str]) -> object:
    result: dict[str, object] = {}
    grammeme_sets = [
        {case, number}
        for case in CASES
        for number in NUMBERS
    ]
    grammeme_sets.extend(
        {case, "sing", gender}
        for case in CASES
        for gender in GENDERS
    )
    for word in words:
        entries = []
        for parse_index, parse in enumerate(morph.parse(word)):
            forms = []
            for grammemes in grammeme_sets:
                ordered = sorted(grammemes)
                forms.append(
                    {
                        "grammemes": ordered,
                        **_call_signature(_inflect_signature, parse, ordered),
                    }
                )
            entries.append({"parse_index": parse_index, "forms": forms})
        result[word] = entries
    return result


def make_snapshot(root: Path, expect_extension: bool) -> dict[str, object]:
    if dawg.EXTENSION_AVAILABLE is not expect_extension:
        raise RuntimeError(
            "Unexpected DAWG backend: "
            f"expected extension={expect_extension}, got {dawg.EXTENSION_AVAILABLE}"
        )

    normalize_corpus, morphology_corpus, lexeme_corpus = build_corpora(root)
    morph = pymorphy3.MorphAnalyzer()
    return {
        "backend": {
            "extension_available": dawg.EXTENSION_AVAILABLE,
            "pymorphy3": pymorphy3.__version__,
        },
        "normalize": {
            text: _call_signature(normalize, text) for text in normalize_corpus
        },
        "parse": {
            word: [_parse_signature(parse) for parse in morph.parse(word)]
            for word in morphology_corpus
        },
        "inflect": _inflection_signatures(morph, lexeme_corpus),
        "lexeme": {
            word: [
                [_parse_signature(form) for form in parse.lexeme]
                for parse in morph.parse(word)
            ]
            for word in lexeme_corpus
        },
    }


def write_snapshot(path: Path, snapshot: dict[str, object]) -> None:
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def comparable_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    copy = dict(snapshot)
    backend_source = copy["backend"]
    if not isinstance(backend_source, dict):
        raise TypeError("snapshot backend must be a JSON object")
    backend: dict[str, object] = dict(backend_source)
    backend.pop("extension_available", None)
    copy["backend"] = backend
    return copy


def compare_snapshots(baseline_path: Path, candidate_path: Path) -> bool:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    return comparable_snapshot(baseline) == comparable_snapshot(candidate)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("output", type=Path)
    snapshot_parser.add_argument(
        "--expect-extension",
        choices=("true", "false"),
        required=True,
    )
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("baseline", type=Path)
    compare_parser.add_argument("candidate", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parents[1]
    if args.command == "snapshot":
        snapshot = make_snapshot(root, args.expect_extension == "true")
        write_snapshot(args.output, snapshot)
        return 0
    if compare_snapshots(args.baseline, args.candidate):
        return 0
    print("pymorphy3 backend snapshots differ", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
