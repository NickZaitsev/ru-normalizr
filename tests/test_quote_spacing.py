"""Отбивка кавычек, склеенных в исходнике с соседним словом или знаком.

Склейка вида «Мысль,"как странно"» — дефект вычитки: синтез съедает на ней
паузу, а иногда и сливает два слова. Правило вставляет пробел, но только там,
где сторону кавычки видно наверняка: открывающая узнаётся по чётности кавычек в
строке, а кавычка после цифры — это дюймы или секунды, и её не трогают.
"""

from __future__ import annotations

import pytest

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.quotes import normalize_ascii_quote_pairs

GLUED_QUOTE_CASES = (
    # Кавычка сразу за запятой, точкой с запятой или двоеточием открывает цитату.
    ('Мысль,"как странно" мелькнула.', 'Мысль, "как странно" мелькнула.'),
    ('Он сказал:"привет" и ушёл.', 'Он сказал: "привет" и ушёл.'),
    ('Одно;"другое" третье.', 'Одно; "другое" третье.'),
    # Кавычка между буквами: слева открывающая, справа закрывающая.
    ('Слово"дом" простое.', 'Слово "дом" простое.'),
    ('Он сказал "дом"и ушёл.', 'Он сказал "дом" и ушёл.'),
    ('Он сказал"дом"и ушёл.', 'Он сказал "дом" и ушёл.'),
    # Форма кавычек приводится к одной до отбивки, поэтому «ёлочки» ведут себя так же.
    ("Мысль,«как странно» мелькнула.", 'Мысль, "как странно" мелькнула.'),
)

PRESERVED_CASES = (
    # Кавычка после цифры — дюймы или секунды, а не открытие цитаты.
    ('Экран 27"и подставка.', 'Экран 27"и подставка.'),
    ('Ширина 5", высота 7".', 'Ширина 5", высота 7".'),
    # Непарное число кавычек в строке: где открывающая — неизвестно, молчим.
    ('Он сказал"дом и ушёл.', 'Он сказал"дом и ушёл.'),
    # Кавычка уже отбита или обнимает текст — вставлять нечего.
    ('Он сказал "дом" и ушёл.', 'Он сказал "дом" и ушёл.'),
    ('"Дом" стоит.', '"Дом" стоит.'),
    # Двойная кавычка подряд — не склейка с буквой.
    ('Он сказал ""дом"" и ушёл.', 'Он сказал ""дом"" и ушёл.'),
)


@pytest.mark.parametrize(("source", "expected"), GLUED_QUOTE_CASES)
def test_glued_quote_gets_a_space_on_the_outer_side(source: str, expected: str) -> None:
    assert normalize_ascii_quote_pairs(source) == expected


@pytest.mark.parametrize(("source", "expected"), PRESERVED_CASES)
def test_ambiguous_and_already_spaced_quotes_stay_untouched(
    source: str, expected: str
) -> None:
    assert normalize_ascii_quote_pairs(source) == expected


@pytest.mark.parametrize(("source", "expected"), GLUED_QUOTE_CASES)
def test_quote_spacing_is_idempotent(source: str, expected: str) -> None:
    assert normalize_ascii_quote_pairs(expected) == expected


def test_parity_is_counted_per_line() -> None:
    """Чётность считается по строке: непарная строка не портит соседнюю."""
    source = 'Он сказал"дом и ушёл.\nОн сказал"дом" вчера.'
    assert normalize_ascii_quote_pairs(source) == (
        'Он сказал"дом и ушёл.\nОн сказал "дом" вчера.'
    )


def test_glued_quote_is_spaced_end_to_end() -> None:
    assert normalize('Мысль,"как странно" мелькнула.', NormalizeOptions.tts()) == (
        'Мысль, "как странно" мелькнула.'
    )


def test_inch_mark_after_a_spoken_number_keeps_its_glue() -> None:
    assert normalize('Экран 27" большой.', NormalizeOptions.tts()) == (
        'Экран двадцать семь" большой.'
    )
