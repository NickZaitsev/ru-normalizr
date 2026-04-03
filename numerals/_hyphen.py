from __future__ import annotations

import re
from typing import Literal

from ..preprocess_utils import NEGATIVE_NUMBER_PLACEHOLDER
from ._constants import UNIT_TOKEN_FRAGMENT, UNITS_DATA

ORDINAL_SUFFIXES = {
    "й",
    "ый",
    "ий",
    "ой",
    "я",
    "ая",
    "е",
    "ее",
    "ое",
    "ые",
    "ых",
    "ыми",
    "го",
    "ого",
    "му",
    "ому",
    "м",
    "ом",
    "ем",
    "ю",
    "ую",
    "ей",
    "ым",
    "им",
}
CARDINAL_CASE_SUFFIXES = {"ти", "ми", "х", "мя", "и", "у"}
AMBIGUOUS_SINGLE_LETTER_HYPHEN_UNITS = {"г", "л", "м", "н", "р", "с", "т", "ф", "ч"}
NUMERIC_UNIT_HYPHEN_PATTERN = re.compile(
    rf"(?<![\d{re.escape(NEGATIVE_NUMBER_PLACEHOLDER)}])"
    rf"(?P<num>(?:{re.escape(NEGATIVE_NUMBER_PLACEHOLDER)}|-)?\d+(?:[.,]\d+)?)"
    rf"\s*[-–—]\s*"
    rf"(?P<unit>{UNIT_TOKEN_FRAGMENT})(?P<unit_dot>\.)?"
    rf"(?!\w)",
    re.UNICODE,
)
SPACED_NUMERIC_HYPHEN_WORD_PATTERN = re.compile(
    r"(?<!\d)(?P<num>\d+)\s+-\s+(?P<rhs>[а-яА-ЯёЁ]{1,})(?!\w)",
    re.UNICODE,
)

NumericHyphenKind = Literal["unit", "ordinal_suffix", "cardinal_case_suffix", "word"]


def is_safe_numeric_hyphen_unit(unit_raw: str) -> bool:
    unit_key = unit_raw.lower().strip(".")
    if unit_key in ORDINAL_SUFFIXES or unit_key in CARDINAL_CASE_SUFFIXES:
        return False
    if unit_key not in UNITS_DATA:
        return False
    if len(unit_key) == 1 and unit_key in AMBIGUOUS_SINGLE_LETTER_HYPHEN_UNITS:
        return False
    return True


def classify_numeric_hyphen_rhs(word: str) -> NumericHyphenKind:
    word_lower = word.lower().strip(".")
    if is_safe_numeric_hyphen_unit(word):
        return "unit"
    if word_lower in ORDINAL_SUFFIXES:
        return "ordinal_suffix"
    if word_lower in CARDINAL_CASE_SUFFIXES:
        return "cardinal_case_suffix"
    return "word"


def normalize_numeric_unit_hyphen_links(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        unit = match.group("unit")
        unit_dot = match.group("unit_dot") or ""
        if not is_safe_numeric_hyphen_unit(unit + unit_dot):
            return match.group(0)
        return f"{match.group('num')} {unit}{unit_dot}"

    return NUMERIC_UNIT_HYPHEN_PATTERN.sub(repl, text)


def normalize_spaced_numeric_hyphen_words(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return f"{match.group('num')}-{match.group('rhs')}"

    return SPACED_NUMERIC_HYPHEN_WORD_PATTERN.sub(repl, text)
