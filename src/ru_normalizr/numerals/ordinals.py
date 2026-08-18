from __future__ import annotations

import logging
import re

from .._morph import canonicalize_case, parse_word
from ..ordinal_utils import (
    render_ordinal,
)
from ..text_context import simple_tokenize
from ..text_scan import compile_scan
from ._constants import HYPHENATED_WORD_PATTERN
from ._helpers import get_numeral_case, inflect_numeral_string
from ._hyphen import classify_numeric_hyphen_rhs
from .numeric_suffixes import is_numeric_suffix, normalize_numeric_suffixes

logger = logging.getLogger(__name__)

HEADING_WORDS_PATTERN = (
    r"глава|главы|главе|главу|главой|главами|главах|"
    r"часть|части|частью|частях|"
    r"раздел|раздела|разделе|разделу|разделом|разделах|"
    r"том|тома|томе|томом|томах|"
    r"книга|книги|книге|книгой|книгах|"
    r"квартал|квартала|квартале|кварталу|кварталом|кварталах"
)
AMBIGUOUS_HEADING_WORDS = {
    "главы",
    "части",
    "раздела",
    "тома",
    "книги",
    "квартала",
}
HEADING_CONTEXT_CASES = {
    "в": "loct",
    "во": "loct",
    "о": "loct",
    "об": "loct",
    "обо": "loct",
    "при": "loct",
    "к": "datv",
    "ко": "datv",
    "по": "datv",
    "с": "gent",
    "со": "gent",
    "из": "gent",
    "до": "gent",
    "от": "gent",
    "у": "gent",
    "без": "gent",
    "после": "gent",
    "для": "gent",
    "около": "gent",
    "возле": "gent",
    "вокруг": "gent",
    "кроме": "gent",
    "начало": "gent",
    "конец": "gent",
    "середина": "gent",
    "см": "accs",
    "смотри": "accs",
}
SINGULAR_HEADING_WORDS_PATTERN = (
    r"глава|главы|главе|главу|главой|"
    r"часть|части|частью|"
    r"раздел|раздела|разделе|разделу|"
    r"книга|книги|книге|книгой|"
    r"квартал|квартала|квартале|кварталу|кварталом"
)
HEADING_RANGE_PATTERN = compile_scan(
    rf"\b(?P<head>{HEADING_WORDS_PATTERN})\s+(?P<left>\d+)\s*[–—-]\s*(?P<right>\d+)\b",
    re.IGNORECASE | re.UNICODE,
)
HEADING_SINGLE_PATTERN = compile_scan(
    rf"\b(?P<head>{SINGULAR_HEADING_WORDS_PATTERN})\s+(?P<number>\d+)\b",
    re.IGNORECASE | re.UNICODE,
)
ABBREVIATED_HEADING_RANGE_PATTERN = compile_scan(
    r"\b(?P<head>гл)\.\s*(?P<left>\d+)\s*[–—-]\s*(?P<right>\d+)\b",
    re.IGNORECASE | re.UNICODE,
)
ABBREVIATED_HEADING_PATTERN = compile_scan(
    r"\b(?P<head>гл)\.\s*(?P<number>\d+)\b",
    re.IGNORECASE | re.UNICODE,
)
COMPOUND_ADJECTIVE_STEMS = (
    "комнатн",
    "тонн",
    "местн",
    "ступенчат",
    "этажн",
    "кратн",
    "дневн",
    "часов",
    "летн",
)
COMPOUND_ADJECTIVE_PATTERN = compile_scan(
    rf"(?<!\d)(?P<num>\d+)(?:\s*[-–—]?\s*(?P<suffix>и|х))?\s+(?P<adj>(?:{'|'.join(COMPOUND_ADJECTIVE_STEMS)})[а-яё]+)\b",
    re.IGNORECASE | re.UNICODE,
)
PERCENT_COMPOUND_ADJECTIVE_PATTERN = compile_scan(
    r"(?<!\d)(?P<num>\d+)\s*%\s*[-–—]?\s*(?P<suffix>н(?:ый|ая|ое|ые|ого|ой|ому|ым|ом|ую|ых|ыми))\b",
    re.IGNORECASE | re.UNICODE,
)


def _ordinal_words(num: int, case: str, gender: str | None) -> str:
    return render_ordinal(num, case=case, gender=gender)


def _pick_range_preposition(first_ordinal: str) -> str:
    return "со" if first_ordinal.startswith(("в", "ф", "с", "з", "ш", "ж")) else "с"


def _heading_parse(text: str, match_start: int, head: str):
    parsed = [candidate for candidate in parse_word(head.lower()) if "NOUN" in candidate.tag]
    if not parsed:
        return None
    inanimate = [candidate for candidate in parsed if "inan" in candidate.tag]
    candidates = inanimate if inanimate else parsed
    normalized_head = head.lower()
    if normalized_head not in AMBIGUOUS_HEADING_WORDS:
        nominative_singular = [
            candidate
            for candidate in candidates
            if ("sing" in candidate.tag and "nomn" in candidate.tag)
        ]
        if nominative_singular:
            return nominative_singular[0]
        return candidates[0]

    left_context = text[max(0, match_start - 40) : match_start]
    left_tokens = simple_tokenize(left_context)
    left_word = next(
        (token.lower() for token in reversed(left_tokens) if any(char.isalpha() for char in token)),
        "",
    )
    target_case = HEADING_CONTEXT_CASES.get(left_word)
    if target_case is None:
        return None

    for candidate in candidates:
        candidate_case = canonicalize_case(candidate.tag.case)
        if candidate_case == target_case and "sing" in candidate.tag:
            return candidate
    for candidate in candidates:
        candidate_case = canonicalize_case(candidate.tag.case)
        if candidate_case == target_case:
            return candidate
    return None


def normalize_heading_ranges(text: str) -> str:
    def render_range(head: str, noun_parse, left: int, right: int) -> str:
        gender = noun_parse.tag.gender if noun_parse and noun_parse.tag.gender else "masc"
        left_ordinal = _ordinal_words(left, "gent", gender)
        right_case = "accs" if gender == "femn" else "nomn"
        right_ordinal = _ordinal_words(right, right_case, gender)
        rendered_head = head
        if noun_parse:
            target_case = noun_parse.tag.case or "nomn"
            plural_head = noun_parse.inflect({target_case, "plur"})
            if plural_head:
                rendered_head = plural_head.word
                if head[:1].isupper():
                    rendered_head = rendered_head.capitalize()
        return (
            f"{rendered_head} {_pick_range_preposition(left_ordinal)} "
            f"{left_ordinal} по {right_ordinal}"
        )

    def repl(match: re.Match[str]) -> str:
        head = match.group("head")
        noun_parse = _heading_parse(text, match.start(), head)
        return render_range(head, noun_parse, int(match.group("left")), int(match.group("right")))

    def abbreviated_repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 40) : match.start()]
        left_tokens = simple_tokenize(left_context)
        left_word = next(
            (
                token.lower()
                for token in reversed(left_tokens)
                if any(char.isalpha() for char in token)
            ),
            "",
        )
        target_case = HEADING_CONTEXT_CASES.get(left_word, "nomn")
        noun_parse = next(
            (
                candidate
                for candidate in parse_word("глава")
                if "NOUN" in candidate.tag and "nomn" in candidate.tag and "inan" in candidate.tag
            ),
            None,
        )
        if noun_parse is None:
            return match.group(0)
        inflected_noun = noun_parse.inflect({target_case, "plur"})
        if inflected_noun is None:
            return match.group(0)
        left_ordinal = _ordinal_words(int(match.group("left")), "gent", "femn")
        right_ordinal = _ordinal_words(int(match.group("right")), "accs", "femn")
        return (
            f"{inflected_noun.word} {_pick_range_preposition(left_ordinal)} "
            f"{left_ordinal} по {right_ordinal}"
        )

    text = ABBREVIATED_HEADING_RANGE_PATTERN.sub(abbreviated_repl, text)
    return HEADING_RANGE_PATTERN.sub(repl, text)


def normalize_heading_numbers(text: str) -> str:
    def abbreviated_repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 40) : match.start()]
        left_tokens = simple_tokenize(left_context)
        left_word = next(
            (
                token.lower()
                for token in reversed(left_tokens)
                if any(char.isalpha() for char in token)
            ),
            "",
        )
        target_case = HEADING_CONTEXT_CASES.get(left_word, "nomn")
        noun_parse = next(
            (candidate for candidate in parse_word("глава") if "NOUN" in candidate.tag),
            None,
        )
        if noun_parse is None:
            return match.group(0)
        inflected_noun = noun_parse.inflect({target_case, "sing"})
        if inflected_noun is None:
            return match.group(0)
        ordinal = _ordinal_words(int(match.group("number")), target_case, "femn")
        return f"{inflected_noun.word} {ordinal}"

    def repl(match: re.Match[str]) -> str:
        head = match.group("head")
        noun_parse = _heading_parse(text, match.start(), head)
        if noun_parse is None:
            return match.group(0)
        gender = noun_parse.tag.gender or "masc"
        case = noun_parse.tag.case or "nomn"
        ordinal = _ordinal_words(int(match.group("number")), case, gender)
        return f"{head} {ordinal}"

    text = ABBREVIATED_HEADING_PATTERN.sub(abbreviated_repl, text)
    return HEADING_SINGLE_PATTERN.sub(repl, text)


def _compound_numeral_prefix(num_str: str) -> str:
    try:
        value = int(num_str)
    except ValueError:
        return num_str
    if value == 0:
        return "нуле"
    for scale, stem in (
        (1_000_000_000, "миллиардо"),
        (1_000_000, "миллионо"),
        (1_000, "тысяче"),
    ):
        if value >= scale:
            scale_count, remainder = divmod(value, scale)
            count_prefix = "" if scale_count == 1 else _compound_numeral_prefix(str(scale_count))
            remainder_prefix = "" if remainder == 0 else _compound_numeral_prefix(str(remainder))
            return f"{count_prefix}{stem}{remainder_prefix}"
    if value == 1:
        return "одно"
    if value == 2:
        return "двух"
    if value == 3:
        return "трёх"
    if value == 4:
        return "четырёх"
    words = inflect_numeral_string(num_str, "gent").split()
    if 90 < value < 100 and words[:1] == ["девяноста"]:
        words[0] = "девяносто"
    elif value == 100:
        return "сто"
    elif 100 < value < 200 and words[:1] == ["ста"]:
        words[0] = "сто"
    if value % 10 == 1 and value % 100 != 11 and words[-1:] == ["одного"]:
        words[-1] = "одно"
    return "".join(words)


def _join_compound_numeral(prefix: str, word: str) -> str:
    combined = f"{prefix}{word.lower()}"
    if word.isupper():
        return combined.upper()
    if word[:1].isupper():
        return combined.capitalize()
    return combined


def normalize_compound_numeric_adjectives(text: str) -> str:
    def numeral_can_govern_singular(value: int) -> bool:
        return value % 10 == 1 and value % 100 != 11

    def repl(match: re.Match[str]) -> str:
        adjective = match.group("adj")
        adjective_parses = [
            candidate for candidate in parse_word(adjective.lower()) if "ADJF" in candidate.tag
        ]
        if not adjective_parses:
            return match.group(0)
        value = int(match.group("num"))
        if numeral_can_govern_singular(value) or any(
            "plur" in candidate.tag for candidate in adjective_parses
        ):
            return match.group(0)
        prefix = _compound_numeral_prefix(match.group("num"))
        return _join_compound_numeral(prefix, adjective)

    def percent_repl(match: re.Match[str]) -> str:
        prefix = _compound_numeral_prefix(match.group("num"))
        suffix = match.group("suffix")
        word = f"процент{suffix.lower()}"
        if suffix.isupper():
            word = word.upper()
        elif suffix[:1].isupper():
            word = word.capitalize()
        return _join_compound_numeral(prefix, word)

    text = PERCENT_COMPOUND_ADJECTIVE_PATTERN.sub(percent_repl, text)
    return COMPOUND_ADJECTIVE_PATTERN.sub(repl, text)


def normalize_hyphenated_words(
    text: str, *, include_numeric_suffixes: bool = True
) -> str:
    if include_numeric_suffixes:
        text = normalize_numeric_suffixes(text)

    def repl(match: re.Match[str]) -> str:
        num_str = match.group(1)
        word = match.group(2)
        word_lower = word.lower()
        if is_numeric_suffix(word_lower):
            return match.group(0)
        word_kind = classify_numeric_hyphen_rhs(word)
        if word_kind == "unit":
            return match.group(0)
        try:
            int(num_str)
        except ValueError as exc:
            logger.debug("int() failed for %r: %s", num_str, exc)
            return match.group(0)
        ctx_left = text[max(0, match.start() - 60) : match.start()]
        ctx_right = text[match.end() : match.end() + 60]
        tokens_left = simple_tokenize(ctx_left)
        tokens_right = simple_tokenize(ctx_right)
        case = get_numeral_case(
            [*tokens_left, num_str, *tokens_right], len(tokens_left)
        )
        word_parses = parse_word(word_lower)
        is_adj_like = any("ADJF" in candidate.tag for candidate in word_parses) or (
            word_lower.endswith(
                (
                    "дневный",
                    "часовой",
                    "минутный",
                    "летний",
                    "этажный",
                    "тонный",
                    "процентный",
                    "кратный",
                    "кратного",
                    "кратном",
                    "кратных",
                )
            )
        )
        is_noun_like = any("NOUN" in candidate.tag for candidate in word_parses)
        if not is_adj_like and not is_noun_like:
            return match.group(0)
        target_case = "gent" if is_adj_like and case == "nomn" else case
        num_words = inflect_numeral_string(num_str, target_case)
        if is_adj_like:
            return _join_compound_numeral(_compound_numeral_prefix(num_str), word)
        return f"{num_words} {word}"

    return HYPHENATED_WORD_PATTERN.sub(repl, text)


def normalize_ordinals(text: str, *, capitalize_text_start: bool = False) -> str:
    return normalize_numeric_suffixes(
        text, capitalize_text_start=capitalize_text_start
    )
