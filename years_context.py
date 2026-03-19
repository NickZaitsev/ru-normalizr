from __future__ import annotations

import re

from ._morph import get_morph
from .numerals._constants import ALL_UNITS
from .text_context import normalize_context_token, simple_tokenize

_TRIVIA_TOKENS = {",", ";", ":", ".", "!", "?", "…", "»", '"', "”", ")", "]", "}"}
_NON_YEAR_LEMMAS = {"раз", "место"}
_NON_YEAR_SYMBOL_TOKENS = {"%"}


def _leading_context_tokens(text: str, start: int, limit: int = 3) -> list[str]:
    tokens: list[str] = []
    for token in simple_tokenize(text[start:]):
        normalized = normalize_context_token(token)
        candidate = normalized or token.strip()
        if not candidate or candidate in _TRIVIA_TOKENS:
            continue
        tokens.append(candidate.lower())
        if len(tokens) >= limit:
            break
    return tokens


def _consume_following_number(tokens: list[str], start: int) -> tuple[str | None, int]:
    if start >= len(tokens) or not tokens[start].isdigit():
        return None, start
    parts = [tokens[start]]
    idx = start + 1
    while idx < len(tokens) and tokens[idx].isdigit() and len(tokens[idx]) == 3:
        parts.append(tokens[idx])
        idx += 1
    return "".join(parts), idx


def _is_non_year_following_token(token: str) -> bool:
    if token in ALL_UNITS or token in _NON_YEAR_SYMBOL_TOKENS:
        return True
    parsed = get_morph().parse(token)
    if not parsed:
        return False
    lemma = parsed[0].normal_form
    return lemma in ALL_UNITS or lemma in _NON_YEAR_LEMMAS


def should_treat_as_implicit_year(
    text: str,
    start: int,
    *,
    explicit_year_word_pattern: re.Pattern[str],
    year_suffix_tail_pattern: re.Pattern[str] | None = None,
) -> bool:
    if year_suffix_tail_pattern and year_suffix_tail_pattern.match(text, start):
        return False
    if explicit_year_word_pattern.match(text, start):
        return False

    following_tokens = _leading_context_tokens(text, start, limit=4)
    if not following_tokens:
        return True
    if len(following_tokens) >= 2 and following_tokens[0] in {"до", "по"}:
        range_number, next_idx = _consume_following_number(following_tokens, 1)
        if range_number is not None:
            if 3 <= len(range_number) <= 4:
                return False
            if len(range_number) > 4:
                return False
            if next_idx < len(following_tokens) and _is_non_year_following_token(
                following_tokens[next_idx]
            ):
                return False
    return not _is_non_year_following_token(following_tokens[0])
