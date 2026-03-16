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

    following_tokens = _leading_context_tokens(text, start)
    if not following_tokens:
        return True
    if (
        len(following_tokens) >= 2
        and following_tokens[0] in {"до", "по"}
        and following_tokens[1].isdigit()
        and 3 <= len(following_tokens[1]) <= 4
    ):
        return False
    return not _is_non_year_following_token(following_tokens[0])
