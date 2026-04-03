from __future__ import annotations

import re

from ._morph import get_morph

BIRTH_YEAR_ABBREVIATION_PATTERN = re.compile(
    r"(?<!\w)(?P<year>\d{2,4})\s*г\.\s*р\.(?!\w)",
    re.IGNORECASE,
)
MASS_GRAM_ABBREVIATION_PATTERN = re.compile(
    r"(?P<context>\b(?:вес|масса)\b\s+)(?P<num>\d+)\s*г\.?(?!\w)",
    re.IGNORECASE,
)


def normalize_birth_year_abbreviations(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        tail = text[match.end() :].lstrip()
        keep_terminal_dot = not tail or tail[:1].isupper() or tail[:1].isdigit()
        return f"{match.group('year')} г. рождения{'.' if keep_terminal_dot else ''}"

    return BIRTH_YEAR_ABBREVIATION_PATTERN.sub(repl, text)


def normalize_mass_gram_abbreviations(text: str) -> str:
    return MASS_GRAM_ABBREVIATION_PATTERN.sub(r"\g<context>\g<num> грамм", text)


def allows_short_abbreviated_year(
    source_text: str,
    end: int,
    prep: str | None,
) -> bool:
    if prep:
        return True
    tail = source_text[end:]
    stripped_tail = tail.lstrip()
    if not stripped_tail:
        return False
    next_token_match = re.match(r"([А-Яа-яЁёA-Za-z]+)", stripped_tail)
    if next_token_match is None:
        return False
    next_token = next_token_match.group(1).lower()
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
        parsed = get_morph().parse(token)
        if not parsed:
            continue
        candidate = next(
            (item for item in parsed if "NOUN" in item.tag),
            parsed[0],
        )
        if candidate.normal_form in {"вес", "масса"}:
            return True
    return False
