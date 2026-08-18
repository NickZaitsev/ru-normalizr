from __future__ import annotations

import functools
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


_ABBREVIATION_TAIL_PATTERN = re.compile(
    r"(?<![\w.])(?P<token>[A-Za-zА-Яа-яЁё]{1,10})\Z"
)
_ABBREVIATION_TAIL_MAX_LOOKBACK = 16
_INITIAL_SEQUENCE_TAIL_PATTERN = re.compile(r"(?:\b[A-ZА-ЯЁ]\.\s*)+[A-ZА-ЯЁ]\Z")


def _has_dictionary_continuation(token: str) -> bool:
    """Check whether the dictionary holds a longer word starting with ``token``.

    ``iterkeys`` is the only prefix lookup shared by both DAWG backends: the
    pure-Python ``dawg_python`` fallback has no ``has_keys_with_prefix``.
    """
    from ._morph import get_morph

    return next(iter(get_morph().dictionary.words.iterkeys(token)), None) is not None


@functools.lru_cache(maxsize=4096)
def is_abbreviation_fragment(token: str) -> bool:
    """Check whether a short lowercase token before a dot is an abbreviation.

    A dotted single letter is an abbreviation or an initial by orthography,
    whatever its case: «Т. II», «Ю. Гагарин», «д. 5». The one-letter words that
    could stand before a real sentence end are all prepositions and
    conjunctions, which cannot end a sentence at all. «я» is the exception and
    keeps its boundary.

    Longer fragments need two disjoint signals, because pymorphy knows some
    abbreviations and guesses at the rest:

    * every reading is tagged ``Abbr`` — «стр», «руб», «ул»;
    * no dictionary reading at all, while the dictionary does hold longer words
      that start with the token — «мкр», «пом», «примеч» are truncations of
      «микрорайон», «помещение», «примечание».

    The continuation check is what keeps an unknown *whole* word out: «деплой»
    has no dictionary reading either, but nothing in the dictionary extends it,
    so it keeps its sentence boundary. A short real word that merely happens to
    end a sentence («сто», «раз», «дом») fails both signals as well.
    """

    if len(token) == 1:
        return token.lower() != "я"
    if not token.islower():
        return False
    parses = parse_word(token)
    if not parses:
        return False
    if all("Abbr" in parse.tag for parse in parses):
        return True
    if any(getattr(parse, "is_known", False) for parse in parses):
        return False
    return _has_dictionary_continuation(token)


def ends_with_abbreviation(text: str, dot_index: int) -> bool:
    """Check whether the dot at ``dot_index`` closes an abbreviation or initial."""
    if _INITIAL_SEQUENCE_TAIL_PATTERN.search(text[max(0, dot_index - 8) : dot_index]):
        return True
    start = max(0, dot_index - _ABBREVIATION_TAIL_MAX_LOOKBACK)
    match = _ABBREVIATION_TAIL_PATTERN.search(text, start, dot_index)
    if match is None:
        return False
    return is_abbreviation_fragment(match.group("token"))


@functools.lru_cache(maxsize=4096)
def _is_plain_word(token: str) -> bool:
    """Check whether ``token`` is a full dictionary word with no abbreviation reading."""
    parses = parse_word(token)
    if not parses:
        return False
    if not any(getattr(parse, "is_known", False) for parse in parses):
        return False
    return not any("Abbr" in parse.tag for parse in parses)


def ends_with_plain_word(text: str, dot_index: int) -> bool:
    """Check whether the dot at ``dot_index`` follows an unambiguous full word.

    Deciding that a dot is stray has to be conservative: the abbreviation
    readings pymorphy offers for «пер» or «стр» are enough to leave the dot
    alone, because a wrongly kept dot only costs a redundant character while a
    wrongly dropped one destroys phrase structure.
    """
    start = max(0, dot_index - _ABBREVIATION_TAIL_MAX_LOOKBACK)
    match = _ABBREVIATION_TAIL_PATTERN.search(text, start, dot_index)
    if match is None:
        return False
    return _is_plain_word(match.group("token").lower())
