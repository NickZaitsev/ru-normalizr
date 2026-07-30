from __future__ import annotations

import pytest

from ru_normalizr import normalize
from ru_normalizr._morph import parse_word
from ru_normalizr.ordinal_utils import render_ordinal_from_noun_parse


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "На конференции выступила 2-я коллега из Казани.",
            "На конференции выступила вторая коллега из Казани.",
        ),
        (
            "После аварии 2-я сирота осталась без опекуна.",
            "После аварии вторая сирота осталась без опекуна.",
        ),
        (
            "На конференции выступил 2-й коллега из Казани.",
            "На конференции выступил второй коллега из Казани.",
        ),
        (
            "После аварии 2-й сирота остался без опекуна.",
            "После аварии второй сирота остался без опекуна.",
        ),
    ],
)
def test_explicit_ordinal_suffix_wins_for_common_gender_nouns(
    source: str, expected: str
) -> None:
    assert normalize(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Экспедиция продолжалась уже 2-е сутки без остановки.",
            "Экспедиция продолжалась уже вторые сутки без остановки.",
        ),
        (
            "В мастерской заточили 2-е ножницы перед сменой.",
            "В мастерской заточили вторые ножницы перед сменой.",
        ),
        (
            "В печь положили 2-е дрова из новой партии.",
            "В печь положили вторые дрова из новой партии.",
        ),
    ],
)
def test_pluralia_tantum_ordinal_uses_inanimate_nominative_agreement(
    source: str, expected: str
) -> None:
    assert normalize(source) == expected


def test_partitive_noun_case_is_canonicalized_for_ordinal() -> None:
    assert normalize("Для 2-го чаю не хватило кипятка.") == (
        "Для второго чаю не хватило кипятка."
    )
    genitive_two = next(parse for parse in parse_word("чаю") if "gen2" in parse.tag)
    assert render_ordinal_from_noun_parse(2, genitive_two) == "второго"
