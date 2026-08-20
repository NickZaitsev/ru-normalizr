"""Golden-тесты токенизации.

`TOKEN_PATTERN` — не набор независимых альтернатив: порядок ветвей и есть
правила разрешения неоднозначностей. «А.С.П.» должно уйти в инициалы раньше,
чем в «слово + точка», «Ту-154» — раньше, чем в три отдельных токена. Переписать
паттерн, ничего не заметив, легко: разбиение меняется молча и проявляется через
несколько стадий как искажённое чтение. Поэтому здесь закреплён ожидаемый
результат на фиксированных образцах, а не свойства паттерна.
"""

from __future__ import annotations

import pytest

from ru_normalizr.placeholders import NEGATIVE_NUMBER_PLACEHOLDER
from ru_normalizr.text_context import TOKEN_PATTERN, simple_tokenize

NEG = NEGATIVE_NUMBER_PLACEHOLDER

GOLDEN_CASES: list[tuple[str, str, list[str]]] = [
    (
        "paragraph_break_is_one_token",
        "первый\n\n\nвторой",
        ["первый", "\n\n\n", "второй"],
    ),
    (
        "protected_negative_number_keeps_its_marker",
        f"температура {NEG}42 ночью",
        ["температура", f"{NEG}42", "ночью"],
    ),
    (
        "protected_negative_decimal_stays_whole",
        f"сдвиг {NEG}3,14 радиан",
        ["сдвиг", f"{NEG}3,14", "радиан"],
    ),
    (
        "single_letter_hyphenated_abbreviation_is_one_token",
        "т.-е. так",
        ["т.-е.", "так"],
    ),
    (
        "multi_letter_hyphenated_abbreviation_splits",
        # Ветка «сокращение через дефис» требует однобуквенных частей, поэтому
        # многобуквенное «ген.-майор.» распадается на пять токенов. На вывод это
        # не влияет — сокращения такой формы разбираются не по токенам, — но
        # закреплено здесь, чтобы правка паттерна не поменяла разбиение молча.
        "ген.-майор. прибыл",
        ["ген", ".", "-", "майор", ".", "прибыл"],
    ),
    (
        "initials_stay_together",
        "А.С.П. писал",
        ["А.С.П.", "писал"],
    ),
    (
        "two_initials_before_a_surname",
        "А.С. Пушкин",
        ["А.С.", "Пушкин"],
    ),
    (
        "number_with_a_latin_suffix",
        "5-th place",
        ["5-th", "place"],
    ),
    (
        "word_with_a_numeric_index",
        "самолёт Ту-154 сел",
        ["самолёт", "Ту-154", "сел"],
    ),
    (
        "compound_word_is_one_token",
        "жёлто-зелёный шар",
        ["жёлто-зелёный", "шар"],
    ),
    (
        "plus_joined_word_keeps_its_sign",
        "режим плюс-минус",
        ["режим", "плюс-минус"],
    ),
    (
        "currency_symbols_are_separate_tokens",
        "цена 100₽ и 20$",
        ["цена", "100", "₽", "и", "20", "$"],
    ),
    (
        "decimal_comma_splits_into_number_punctuation_number",
        "ровно 12,5 метра",
        ["ровно", "12", ",", "5", "метра"],
    ),
    (
        "ellipsis_becomes_three_tokens",
        "он молчал...",
        ["он", "молчал", ".", ".", "."],
    ),
    (
        "em_dash_is_its_own_token",
        "жизнь — движение",
        ["жизнь", "—", "движение"],
    ),
    (
        "whitespace_never_becomes_a_token",
        "два  \t пробела и тонкий",
        ["два", "пробела", "и", "тонкий"],
    ),
]


@pytest.mark.parametrize(
    ("source", "expected"),
    [(source, expected) for _, source, expected in GOLDEN_CASES],
    ids=[name for name, _, _ in GOLDEN_CASES],
)
def test_tokenization_is_stable(source: str, expected: list[str]) -> None:
    assert simple_tokenize(source) == expected


def test_verbose_pattern_ignores_its_own_whitespace_and_comments() -> None:
    """VERBOSE-режим не должен затащить в паттерн пробелы из его оформления."""
    # Если бы пробелы попали в паттерн, слово с пробелом внутри стало бы одним
    # токеном, а комментарий сделал бы часть альтернатив недостижимой.
    assert simple_tokenize("одно слово") == ["одно", "слово"]
    assert TOKEN_PATTERN.findall("#") == ["#"]
    assert TOKEN_PATTERN.findall(" ") == []


def test_every_character_of_the_input_is_accounted_for() -> None:
    """Токены плюс пробелы должны покрывать вход целиком — без потерь."""
    source = "Ген.-майор А.С.П. купил Ту-154 за 100₽; сдача — 12,5 копейки..."

    joined = "".join(simple_tokenize(source))
    assert joined == "".join(source.split(" ")).replace(" ", "")
