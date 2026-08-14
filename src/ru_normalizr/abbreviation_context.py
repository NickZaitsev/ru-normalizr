from __future__ import annotations

import re

from ._morph import parse_word
from .text_scan import first_non_whitespace_index

BIRTH_YEAR_ABBREVIATION_PATTERN = re.compile(
    r"(?<!\w)(?P<year>\d{2,4})\s*г\.\s*р\.(?!\w)",
    re.IGNORECASE,
)
MASS_GRAM_ABBREVIATION_PATTERN = re.compile(
    r"(?P<context>\b(?:вес|масса)\b\s+)(?P<num>\d+)\s*г(?P<dot>\.)?(?!\w)",
    re.IGNORECASE,
)
_SHORT_ABBREVIATED_YEAR_TOKEN_PATTERN = re.compile(r"[А-Яа-яЁёA-Za-z]+")


def should_keep_terminal_abbreviation_dot(source_text: str, match_end: int) -> bool:
    next_index, saw_newline = first_non_whitespace_index(source_text, match_end)
    if next_index >= len(source_text):
        return True

    if saw_newline:
        return True

    next_char = source_text[next_index]
    if next_char in ".!?…" or next_char.isupper():
        return True
    if next_char in '"»”)]}':
        after_index, _ = first_non_whitespace_index(source_text, next_index + 1)
        return after_index >= len(source_text) or source_text[after_index].isupper()
    return False


def normalize_birth_year_abbreviations(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        next_index, _ = first_non_whitespace_index(text, match.end())
        keep_terminal_dot = (
            next_index >= len(text)
            or text[next_index].isupper()
            or text[next_index].isdigit()
        )
        return f"{match.group('year')} г. рождения{'.' if keep_terminal_dot else ''}"

    return BIRTH_YEAR_ABBREVIATION_PATTERN.sub(repl, text)


def normalize_mass_gram_abbreviations(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        keep_dot = bool(match.group("dot")) and should_keep_terminal_abbreviation_dot(
            text, match.end()
        )
        return f"{match.group('context')}{match.group('num')} грамм{'.' if keep_dot else ''}"

    return MASS_GRAM_ABBREVIATION_PATTERN.sub(repl, text)


def allows_short_abbreviated_year(
    source_text: str,
    end: int,
    prep: str | None,
) -> bool:
    if prep:
        return True
    next_index, _ = first_non_whitespace_index(source_text, end)
    if next_index >= len(source_text):
        return False
    next_token_match = _SHORT_ABBREVIATED_YEAR_TOKEN_PATTERN.match(
        source_text, next_index
    )
    if next_token_match is None:
        return False
    next_token = next_token_match.group(0).lower()
    return next_token.startswith("рожд")


def has_mass_measurement_context(source_text: str, match_start: int) -> bool:
    from .text_context import normalize_context_token, simple_tokenize

    left_context = source_text[max(0, match_start - 40) : match_start]
    left_tokens = [
        normalize_context_token(token)
        for token in simple_tokenize(left_context)
        if normalize_context_token(token)
    ]
    for token in reversed(left_tokens[-3:]):
        parsed = parse_word(token)
        if not parsed:
            continue
        candidate = next(
            (item for item in parsed if "NOUN" in item.tag),
            parsed[0],
        )
        if candidate.normal_form in {"вес", "масса"}:
            return True
    return False
