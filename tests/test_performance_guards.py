import pytest

from ru_normalizr.dates_time import normalize_dates_and_time
from ru_normalizr.numerals.numeric_suffixes import normalize_numeric_suffixes
from ru_normalizr.numerals.symbols import normalize_math_symbols
from ru_normalizr.numerals.versions import normalize_versions
from ru_normalizr.options import NormalizeOptions
from ru_normalizr.preprocess_utils import (
    normalize_ascii_quote_pairs,
    normalize_unary_plus_numbers,
    protect_negative_numbers,
    protect_unit_slashes,
)
from ru_normalizr.text_scan import DECIMAL_DIGIT_PATTERN, contains_pattern
from ru_normalizr.years import normalize_years


@pytest.mark.parametrize(
    "pattern, text, expected",
    [
        (DECIMAL_DIGIT_PATTERN, "Обычный текст.", False),
        (DECIMAL_DIGIT_PATTERN, "Текст 12.", True),
    ],
)
def test_contains_pattern_checks_compiled_candidate(pattern, text, expected):
    assert contains_pattern(text, pattern) is expected


@pytest.mark.parametrize(
    ("normalizer", "source"),
    [
        (normalize_ascii_quote_pairs, "Обычный текст без кавычек."),
        (normalize_math_symbols, "Обычный текст без математических знаков."),
        (normalize_numeric_suffixes, "Обычный текст без числовых окончаний."),
        (normalize_versions, "Обычный текст без версий."),
        (protect_negative_numbers, "Обычный текст без чисел."),
        (normalize_unary_plus_numbers, "Обычный текст без плюса."),
        (protect_unit_slashes, "Обычный текст без косой черты."),
        (
            lambda value: normalize_dates_and_time(value, NormalizeOptions.tts()),
            "Обычный текст без цифр.",
        ),
        (
            lambda value: normalize_years(value, NormalizeOptions.tts()),
            "Обычный текст без цифр.",
        ),
    ],
)
def test_candidate_gates_preserve_text_without_required_literals(normalizer, source):
    assert normalizer(source) == source
