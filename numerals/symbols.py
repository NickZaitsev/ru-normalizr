from __future__ import annotations

import re

from ._constants import (
    CURRENCY_STANDALONE,
    GREEK_LETTERS,
    MATH_SYMBOLS,
    STANDALONE_CURRENCY_PATTERN,
)


def normalize_greek_letters(text: str) -> str:
    for char, replacement in GREEK_LETTERS.items():
        text = text.replace(char, replacement)
    return text


def normalize_math_symbols(text: str) -> str:
    for char, replacement in MATH_SYMBOLS.items():
        text = text.replace(char, replacement)
    return text


def normalize_standalone_currency(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return CURRENCY_STANDALONE[match.group(0)]

    return STANDALONE_CURRENCY_PATTERN.sub(repl, text)
