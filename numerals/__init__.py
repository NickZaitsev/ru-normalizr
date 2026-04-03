from __future__ import annotations

from ..options import NormalizeOptions
from ..text_context import simple_tokenize
from ._constants import ALL_UNITS
from ._helpers import get_numeral_case
from .cardinals import (
    normalize_all_digits_everywhere,
    normalize_cardinal_numerals,
    normalize_numeric_unit_ranges,
    normalize_remaining_post_numeral_abbreviations,
)
from .decimals import normalize_decimals
from .fractions import normalize_fractions
from .ordinals import (
    normalize_compound_numeric_adjectives,
    normalize_heading_numbers,
    normalize_heading_ranges,
    normalize_hyphenated_words,
    normalize_ordinals,
)
from .symbols import (
    normalize_greek_letters,
    normalize_math_symbols,
    normalize_standalone_currency,
)


def normalize_numerals(text: str, options: NormalizeOptions | None = None) -> str:
    del options
    text = normalize_heading_ranges(text)
    text = normalize_heading_numbers(text)
    text = normalize_numeric_unit_ranges(text)
    text = normalize_math_symbols(text)
    text = normalize_cardinal_numerals(text)
    text = normalize_remaining_post_numeral_abbreviations(text)
    text = normalize_greek_letters(text)
    text = normalize_standalone_currency(text)
    text = normalize_all_digits_everywhere(text)
    return text


__all__ = [
    "ALL_UNITS",
    "get_numeral_case",
    "normalize_all_digits_everywhere",
    "normalize_compound_numeric_adjectives",
    "normalize_cardinal_numerals",
    "normalize_decimals",
    "normalize_fractions",
    "normalize_greek_letters",
    "normalize_heading_numbers",
    "normalize_heading_ranges",
    "normalize_hyphenated_words",
    "normalize_math_symbols",
    "normalize_numerals",
    "normalize_numeric_unit_ranges",
    "normalize_ordinals",
    "normalize_remaining_post_numeral_abbreviations",
    "normalize_standalone_currency",
    "simple_tokenize",
]
