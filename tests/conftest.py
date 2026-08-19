"""Общие фикстуры E2E-тестов нормализации.

Большая часть тестов проекта — это таблицы «фраза → ожидаемое чтение» в режиме
TTS. Здесь лежат две фикстуры, которые убирают из этих таблиц повторяющуюся
обвязку: `tts` нормализует строку профилем TTS, `check_tts` сверяет результат и
на расхождении печатает, в каком именно слове оно случилось.
"""

from __future__ import annotations

import difflib
from collections.abc import Callable

import pytest

from ru_normalizr import NormalizeOptions, normalize

#: Тип фикстуры `tts`: строка на входе — прочитанная строка на выходе.
Tts = Callable[[str], str]
#: Тип фикстуры `check_tts`: фраза и ожидаемое чтение.
CheckTts = Callable[[str, str], None]


@pytest.fixture(scope="session")
def tts() -> Tts:
    """Нормализация строки профилем TTS по умолчанию."""

    def _tts(source: str) -> str:
        return normalize(source, NormalizeOptions.tts())

    return _tts


def _first_word_difference(expected: str, actual: str) -> str:
    """Первое разошедшееся слово с соседями — чтобы не искать глазами в абзаце."""
    expected_words = expected.split()
    actual_words = actual.split()
    matcher = difflib.SequenceMatcher(a=expected_words, b=actual_words, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        context = " ".join(expected_words[max(0, i1 - 3) : i1])
        return (
            f"  первое расхождение после «{context}»:\n"
            f"    ожидалось: {' '.join(expected_words[i1:i2]) or '(ничего)'}\n"
            f"    получено:  {' '.join(actual_words[j1:j2]) or '(ничего)'}"
        )
    # Строки различаются только пробелами или переводами строк.
    return "  строки различаются только пробелами"


@pytest.fixture(scope="session")
def check_tts(tts: Tts) -> CheckTts:
    """Сверить чтение фразы с ожиданием и показать читаемое расхождение."""

    def _check(source: str, expected: str) -> None:
        actual = tts(source)
        if actual == expected:
            return
        pytest.fail(
            "TTS-нормализация разошлась с ожиданием.\n"
            f"  вход:      {source}\n"
            f"  ожидалось: {expected}\n"
            f"  получено:  {actual}\n" + _first_word_difference(expected, actual),
            pytrace=False,
        )

    return _check
