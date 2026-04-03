from __future__ import annotations

import re

import num2words

from .._morph import get_morph
from ..ordinal_utils import (
    find_first_noun_right,
    find_left_name_anchor,
    normalize_ordinal_suffix_defaults,
    render_ordinal,
    render_ordinal_from_noun_parse,
    resolve_ordinal_plural,
    resolve_ordinal_suffix_case,
)
from ..text_context import simple_tokenize
from ._constants import HYPHENATED_WORD_PATTERN, ORDINAL_PATTERN
from ._helpers import get_numeral_case, inflect_numeral_string
from ._hyphen import CARDINAL_CASE_SUFFIXES, classify_numeric_hyphen_rhs
from ._num2words import resolve_num2words_case

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
}
SINGULAR_HEADING_WORDS_PATTERN = (
    r"глава|главы|главе|главу|главой|"
    r"часть|части|частью|"
    r"раздел|раздела|разделе|разделу|"
    r"том|тома|томе|томом|"
    r"книга|книги|книге|книгой|"
    r"квартал|квартала|квартале|кварталу|кварталом"
)
HEADING_RANGE_PATTERN = re.compile(
    rf"\b(?P<head>{HEADING_WORDS_PATTERN})\s+(?P<left>\d+)\s*[–—-]\s*(?P<right>\d+)\b",
    re.IGNORECASE | re.UNICODE,
)
HEADING_SINGLE_PATTERN = re.compile(
    rf"\b(?P<head>{SINGULAR_HEADING_WORDS_PATTERN})\s+(?P<number>\d+)\b",
    re.IGNORECASE | re.UNICODE,
)
MONTH_GENITIVE_WORDS = {
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
}
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
COMPOUND_ADJECTIVE_PATTERN = re.compile(
    rf"(?<!\d)(?P<num>\d+)(?:\s*[-–—]?\s*(?P<suffix>и|х))?\s+(?P<adj>(?:{'|'.join(COMPOUND_ADJECTIVE_STEMS)})[а-яё]*)\b",
    re.IGNORECASE | re.UNICODE,
)


def _ordinal_words(num: int, case: str, gender: str | None) -> str:
    return render_ordinal(num, case=case, gender=gender)


def _pick_range_preposition(first_ordinal: str) -> str:
    return "со" if first_ordinal.startswith(("в", "ф", "с", "з", "ш", "ж")) else "с"


def _heading_parse(text: str, match_start: int, head: str):
    parsed = [candidate for candidate in get_morph().parse(head.lower()) if "NOUN" in candidate.tag]
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
        (
            token.lower()
            for token in reversed(left_tokens)
            if any(char.isalpha() for char in token)
        ),
        "",
    )
    target_case = HEADING_CONTEXT_CASES.get(left_word)
    if target_case is None:
        return None

    for candidate in candidates:
        candidate_case = "loct" if "loc2" in candidate.tag else candidate.tag.case
        if candidate_case == target_case and "sing" in candidate.tag:
            return candidate
    for candidate in candidates:
        candidate_case = "loct" if "loc2" in candidate.tag else candidate.tag.case
        if candidate_case == target_case:
            return candidate
    return None


def normalize_heading_ranges(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        head = match.group("head")
        noun_parse = _heading_parse(text, match.start(), head)
        gender = noun_parse.tag.gender if noun_parse and noun_parse.tag.gender else "masc"
        left_ordinal = _ordinal_words(int(match.group("left")), "gent", gender)
        right_case = "accs" if gender == "femn" else "nomn"
        right_ordinal = _ordinal_words(int(match.group("right")), right_case, gender)
        return f"{head} {_pick_range_preposition(left_ordinal)} {left_ordinal} по {right_ordinal}"

    return HEADING_RANGE_PATTERN.sub(repl, text)


def normalize_heading_numbers(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        head = match.group("head")
        noun_parse = _heading_parse(text, match.start(), head)
        if noun_parse is None:
            return match.group(0)
        gender = noun_parse.tag.gender or "masc"
        case = noun_parse.tag.case or "nomn"
        ordinal = _ordinal_words(int(match.group("number")), case, gender)
        return f"{head} {ordinal}"

    return HEADING_SINGLE_PATTERN.sub(repl, text)


def normalize_compound_numeric_adjectives(text: str) -> str:
    def numeral_prefix(num_str: str) -> str:
        try:
            value = int(num_str)
        except ValueError:
            return num_str
        if value == 1:
            return "одно"
        if value == 2:
            return "двух"
        if value == 3:
            return "трёх"
        if value == 4:
            return "четырёх"
        return inflect_numeral_string(num_str, "gent").replace(" ", "")

    def repl(match: re.Match[str]) -> str:
        prefix = numeral_prefix(match.group("num"))
        adjective = match.group("adj")
        return f"{prefix}{adjective}"

    return COMPOUND_ADJECTIVE_PATTERN.sub(repl, text)


def normalize_hyphenated_words(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        morph = get_morph()
        num_str = match.group(1)
        word = match.group(2)
        word_lower = word.lower()
        word_kind = classify_numeric_hyphen_rhs(word)
        if word_kind == "unit":
            return match.group(0)
        if word_kind == "ordinal_suffix":
            return match.group(0)
        if word_lower == "у":
            return match.group(0)
        if (
            word_lower
            in {
                "ый",
                "ой",
                "й",
                "ого",
                "го",
                "ому",
                "ым",
                "ом",
                "му",
                "е",
                "х",
                "м",
                "ми",
            }
            and int(num_str) > 100
        ):
            return match.group(0)
        try:
            int(num_str)
        except Exception:
            return match.group(0)
        case_from_suffix = None
        if word_lower == "х":
            case_from_suffix = None
        elif word_lower in ("ти", "и"):
            case_from_suffix = "gent"
        elif word_lower in ("ми", "мя"):
            case_from_suffix = "ablt"
        ctx_left = text[max(0, match.start() - 60) : match.start()]
        ctx_right = text[match.end() : match.end() + 60]
        tokens_left = simple_tokenize(ctx_left)
        tokens_right = simple_tokenize(ctx_right)
        context_case = get_numeral_case(
            tokens_left + [num_str] + tokens_right, len(tokens_left)
        )
        if case_from_suffix:
            case = case_from_suffix
        elif word_lower == "х":
            case = context_case if context_case in ("gent", "loct") else "gent"
        else:
            case = context_case
        p_word = morph.parse(word_lower)[0]
        is_adj_like = "ADJF" in p_word.tag or word_lower.endswith(
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
        target_case = "gent" if is_adj_like and case == "nomn" else case
        num_words = inflect_numeral_string(num_str, target_case)
        if word_lower in CARDINAL_CASE_SUFFIXES:
            return num_words
        return (
            f"{num_words}{word}"
            if is_adj_like
            else (f"{num_words}" if len(word) <= 3 else f"{num_words} {word}")
        )

    return HYPHENATED_WORD_PATTERN.sub(repl, text)


def _render_cardinal_suffix_number(num: int, case: str) -> str | None:
    try:
        return num2words.num2words(
            num,
            lang="ru",
            case=resolve_num2words_case(case),
        )
    except Exception:
        return None


def normalize_ordinals(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        num_str = match.group(1)
        suffix = match.group(2).lower()
        try:
            num = int(num_str)
        except ValueError:
            return match.group(0)
        gender = "masc"
        is_cardinal_suffix = suffix in ("ти", "ми", "у")
        ctx_left = text[max(0, match.start() - 60) : match.start()]
        ctx_right = text[match.end() : match.end() + 60]
        tokens_left = simple_tokenize(ctx_left)
        tokens_right = simple_tokenize(ctx_right)
        case = get_numeral_case(
            tokens_left + [num_str] + tokens_right, len(tokens_left)
        )

        case, gender = resolve_ordinal_suffix_case(case, suffix, tokens_right, gender)
        plural = resolve_ordinal_plural(suffix, case, tokens_right)
        right_noun = find_first_noun_right(tokens_right, suffix)
        left_anchor = find_left_name_anchor(tokens_left)
        next_clean = tokens_right[0].strip(".,!?;:").lower() if tokens_right else ""

        if suffix == "у":
            target_case = "accs"
            target_gender = right_noun.tag.gender if right_noun and right_noun.tag.gender else "femn"
            return inflect_numeral_string(num_str, target_case, target_gender) + " "

        if right_noun is not None:
            if next_clean in MONTH_GENITIVE_WORDS and suffix in {"е", "ее", "ое"}:
                return render_ordinal(num, case="nomn", gender="neut") + " "
            singularize_plural = suffix in {"ее", "ое"}
            return (
                render_ordinal_from_noun_parse(
                    num,
                    right_noun,
                    singularize_plural=singularize_plural,
                )
                + " "
            )

        if left_anchor is not None and not is_cardinal_suffix:
            return render_ordinal_from_noun_parse(num, left_anchor) + " "

        default_case, default_gender, default_plural = normalize_ordinal_suffix_defaults(
            case,
            suffix,
        )
        generation_case = default_case
        gender = default_gender or gender
        plural = plural or default_plural
        if (
            generation_case == "accs"
            and not plural
            and gender in {"masc", "neut"}
            and right_noun is not None
            and "inan" in right_noun.tag
        ):
            generation_case = "nomn"

        if is_cardinal_suffix:
            cardinal = _render_cardinal_suffix_number(num, generation_case)
            if cardinal is None:
                return match.group(0)
            return cardinal + " "
        return (
            render_ordinal(
                num,
                case=generation_case,
                gender=gender,
                plural=plural,
                inanimate=right_noun is not None and "inan" in right_noun.tag,
            )
            + " "
        )

    return ORDINAL_PATTERN.sub(repl, text)
