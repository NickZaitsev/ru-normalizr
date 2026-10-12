"""Эталонные хэши вывода нормализации по книжному корпусу.

Инструмент разработки, в пакет не входит. Нужен на время рефакторингов, которые
обязаны сохранять вывод байт в байт: тесты ловят разошедшиеся правила по одной
фразе, а хэш книги ловит любое расхождение вообще, включая то, на которое никто
не написал теста.

    uv run python scripts/golden_corpus.py --update   # зафиксировать эталон
    uv run python scripts/golden_corpus.py --check    # сверить с эталоном

По умолчанию берётся первые ``--prefix-chars`` знаков каждой книги: этого хватает,
чтобы поймать изменение правила, и сверка укладывается в секунды. Перед началом и
после завершения фазы рефакторинга стоит прогонять `--full` — она читает книги
целиком (около 34 млн знаков, несколько минут) и пишет отдельный раздел эталона.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from ru_normalizr import NormalizeOptions, Normalizer

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "benchmarks" / "corpus" / "MANIFEST.json"
HASHES_PATH = REPO_ROOT / "tests" / "data" / "golden_corpus_hashes.json"
DEFAULT_PREFIX_CHARS = 200_000


@dataclass(frozen=True, slots=True)
class Book:
    """Книга корпуса и её проверенный размер из манифеста."""

    name: str
    path: Path
    characters: int
    sha256: str


def load_books() -> list[Book]:
    """Книги из манифеста; пустой список, если корпус не скачан."""
    if not MANIFEST_PATH.is_file():
        return []
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    corpus_dir = REPO_ROOT / manifest["destination"]
    books: list[Book] = []
    for work in manifest["works"]:
        plain_text = work.get("plain_text_file")
        verification = work.get("verification") or {}
        if not plain_text or not verification.get("sha256"):
            continue
        path = corpus_dir / plain_text
        if not path.is_file():
            continue
        books.append(
            Book(
                name=Path(plain_text).stem,
                path=path,
                characters=int(verification["characters"]),
                sha256=str(verification["sha256"]),
            )
        )
    return books


def read_book(book: Book, prefix_chars: int | None) -> str:
    """Текст книги (или её начало) с проверкой, что файл не подменили."""
    with book.path.open("r", encoding="utf-8", newline="") as stream:
        text = stream.read()
    if len(text) != book.characters:
        raise ValueError(
            f"Книга {book.name!r} изменилась: {len(text)} знаков вместо {book.characters}"
        )
    if prefix_chars is None:
        digest = hashlib.sha256(book.path.read_bytes()).hexdigest()
        if digest != book.sha256:
            raise ValueError(f"Книга {book.name!r} изменилась: SHA-256 не совпал с манифестом")
        return text
    return text[:prefix_chars]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute(books: list[Book], prefix_chars: int | None) -> dict[str, object]:
    """Хэши вывода нормализации в режиме TTS для каждой книги."""
    normalizer = Normalizer(NormalizeOptions.tts())
    entries: dict[str, dict[str, object]] = {}
    for book in books:
        text = read_book(book, prefix_chars)
        output = normalizer.normalize(text)
        entries[book.name] = {
            "input_chars": len(text),
            "input_sha256": sha256_text(text),
            "output_chars": len(output),
            "output_sha256": sha256_text(output),
        }
    return {
        "prefix_chars": prefix_chars,
        "mode": "tts",
        "books": entries,
    }


def compare(expected: dict[str, object], actual: dict[str, object]) -> list[str]:
    """Расхождения между эталоном и пересчётом, по книге на строку."""
    problems: list[str] = []
    expected_books = expected.get("books")
    actual_books = actual.get("books")
    if not isinstance(expected_books, dict) or not isinstance(actual_books, dict):
        return ["эталон повреждён: нет раздела books"]
    if expected.get("prefix_chars") != actual.get("prefix_chars"):
        problems.append(
            f"эталон снят с prefix_chars={expected.get('prefix_chars')!r}, "
            f"сверка идёт с prefix_chars={actual.get('prefix_chars')!r}"
        )
    for name, expected_entry in expected_books.items():
        actual_entry = actual_books.get(name)
        if actual_entry is None:
            problems.append(f"{name}: книги нет в корпусе, сверить не с чем")
            continue
        if actual_entry["input_sha256"] != expected_entry["input_sha256"]:
            problems.append(f"{name}: изменился вход, эталон надо перезаписать")
            continue
        if actual_entry["output_sha256"] != expected_entry["output_sha256"]:
            problems.append(
                f"{name}: вывод изменился — {expected_entry['output_chars']} знаков "
                f"({expected_entry['output_sha256'][:12]}…) стало "
                f"{actual_entry['output_chars']} ({actual_entry['output_sha256'][:12]}…)"
            )
    for name in actual_books:
        if name not in expected_books:
            problems.append(f"{name}: книги нет в эталоне, нужен --update")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--update", action="store_true", help="перезаписать эталон")
    action.add_argument("--check", action="store_true", help="сверить с эталоном")
    parser.add_argument(
        "--prefix-chars",
        type=int,
        default=DEFAULT_PREFIX_CHARS,
        help="сколько знаков брать от начала каждой книги (по умолчанию %(default)s)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="читать книги целиком; пишет и сверяет отдельный раздел эталона",
    )
    args = parser.parse_args(argv)

    books = load_books()
    if not books:
        print("Корпус не скачан: сверять нечего", file=sys.stderr)
        return 0

    prefix_chars = None if args.full else int(args.prefix_chars)
    section = "full" if args.full else "prefix"
    actual = compute(books, prefix_chars)

    document: dict[str, object] = {}
    if HASHES_PATH.is_file():
        document = json.loads(HASHES_PATH.read_text(encoding="utf-8"))

    if args.update:
        document[section] = actual
        HASHES_PATH.parent.mkdir(parents=True, exist_ok=True)
        HASHES_PATH.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Эталон обновлён: раздел {section}, книг {len(books)}")
        return 0

    expected = document.get(section)
    if not isinstance(expected, dict):
        print(f"В эталоне нет раздела {section}: нужен --update", file=sys.stderr)
        return 1
    problems = compare(expected, actual)
    if problems:
        print(f"Вывод разошёлся с эталоном ({section}):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(f"Вывод совпал с эталоном: раздел {section}, книг {len(books)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
