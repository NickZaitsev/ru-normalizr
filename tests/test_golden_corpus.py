"""Вывод нормализации по книгам корпуса совпадает с зафиксированным эталоном.

Сеть безопасности для рефакторингов, которые обязаны сохранять вывод байт в байт.
Обычные тесты проверяют фразы, на которые кто-то догадался их написать; хэш книги
ловит любое расхождение, включая незамеченное. Эталон лежит в
`tests/data/golden_corpus_hashes.json` и перезаписывается только осознанно:

    uv run python scripts/golden_corpus.py --update

Если тест упал, а изменение вывода было задумано — сначала объясните расхождение
(какое правило и почему), потом обновляйте эталон. Порядок обратный означает, что
сеть выключена.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HASHES_PATH = REPO_ROOT / "tests" / "data" / "golden_corpus_hashes.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "golden_corpus.py"


def _load_golden_corpus_module() -> ModuleType:
    """Загрузить `scripts/golden_corpus.py`: он не пакет и импортом не достаётся."""
    spec = importlib.util.spec_from_file_location("golden_corpus", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        pytest.skip(f"не удалось загрузить {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_corpus_output_matches_the_frozen_golden_hashes() -> None:
    if not SCRIPT_PATH.is_file():
        pytest.skip("нет scripts/golden_corpus.py")
    if not HASHES_PATH.is_file():
        pytest.skip("эталон не зафиксирован: scripts/golden_corpus.py --update")

    golden = _load_golden_corpus_module()
    books = golden.load_books()
    if not books:
        pytest.skip("книжный корпус не скачан, сверять нечего")

    document = json.loads(HASHES_PATH.read_text(encoding="utf-8"))
    expected = document.get("prefix")
    assert isinstance(expected, dict), "в эталоне нет раздела prefix"

    actual = golden.compute(books, expected.get("prefix_chars"))
    problems = golden.compare(expected, actual)
    if problems:
        pytest.fail(
            "Вывод нормализации разошёлся с эталоном:\n  " + "\n  ".join(problems),
            pytrace=False,
        )
