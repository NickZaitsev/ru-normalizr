from __future__ import annotations

import re

import num2words

from .._morph import get_morph
from ..text_context import simple_tokenize
from ._constants import HYPHENATED_WORD_PATTERN, ORDINAL_PATTERN
from ._helpers import get_numeral_case, inflect_numeral_string
from ._hyphen import CARDINAL_CASE_SUFFIXES, classify_numeric_hyphen_rhs

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
    r"главы|главе|главу|главой|"
    r"части|частью|"
    r"раздела|разделе|разделу|"
    r"тома|томе|томом|"
    r"книги|книге|книгой|"
    r"квартала|квартале|кварталу|кварталом"
)
HEADING_RANGE_PATTERN = re.compile(
    rf"\b(?P<head>{HEADING_WORDS_PATTERN})\s+(?P<left>\d+)\s*[–—-]\s*(?P<right>\d+)\b",
    re.IGNORECASE | re.UNICODE,
)
HEADING_SINGLE_PATTERN = re.compile(
    rf"\b(?P<head>{SINGULAR_HEADING_WORDS_PATTERN})\s+(?P<number>\d+)\b",
    re.IGNORECASE | re.UNICODE,
)


def _ordinal_words(num: int, case: str, gender: str | None) -> str:
    case_map = {
        "nomn": "nominative",
        "gent": "genitive",
        "datv": "dative",
        "accs": "accusative",
        "ablt": "instrumental",
        "loct": "prepositional",
    }
    gender_map = {"masc": "m", "femn": "f", "neut": "n"}
    kwargs: dict[str, str] = {"to": "ordinal", "case": case_map.get(case, "nominative")}
    if gender in gender_map:
        kwargs["gender"] = gender_map[gender]
    try:
        return num2words.num2words(num, lang="ru", **kwargs)
    except Exception:
        return num2words.num2words(num, lang="ru", to="ordinal")


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


def normalize_ordinals(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        morph = get_morph()
        num_str = match.group(1)
        suffix = match.group(2).lower()
        try:
            num = int(num_str)
        except ValueError:
            return match.group(0)
        gender = "masc"
        is_cardinal_suffix = suffix in ("ти", "ми")
        ctx_left = text[max(0, match.start() - 60) : match.start()]
        ctx_right = text[match.end() : match.end() + 60]
        tokens_left = simple_tokenize(ctx_left)
        tokens_right = simple_tokenize(ctx_right)
        case = get_numeral_case(
            tokens_left + [num_str] + tokens_right, len(tokens_left)
        )
        if suffix in ("я", "яя"):
            gender = "femn"
        elif suffix in ("е", "ее"):
            gender = "neut"
        elif suffix == "й" and tokens_right:
            p_next = morph.parse(tokens_right[0].strip(".,!?;:"))[0]
            if "femn" in p_next.tag:
                gender = "femn"
                if case == "nomn":
                    case = "gent"
        case_from_suffix = None
        if suffix == "го":
            case_from_suffix = "gent"
        elif suffix == "му":
            case_from_suffix = "datv"
        elif suffix == "й" and case == "nomn" and tokens_right:
            p_next = morph.parse(tokens_right[0].strip(".,!?;:"))[0]
            if "femn" in p_next.tag:
                gender = "femn"
                case_from_suffix = "gent"
        if suffix == "м":
            if tokens_right:
                p_next = morph.parse(tokens_right[0].strip(".,!?;:"))[0]
                case_from_suffix = "loct" if "sing" in p_next.tag else "datv"
            else:
                case_from_suffix = "loct"
        case = case_from_suffix or case
        plural = suffix in ("х", "ми", "е", "м") and not (
            suffix == "м" and case == "loct"
        )
        cases_map = {
            "nomn": "nominative",
            "gent": "genitive",
            "datv": "dative",
            "accs": "accusative",
            "ablt": "instrumental",
            "loct": "prepositional",
        }
        gender_map = {"masc": "m", "femn": "f", "neut": "n"}
        if case in cases_map:
            try:
                kwargs = {"case": cases_map[case]}
                if not is_cardinal_suffix:
                    kwargs["to"] = "ordinal"
                if plural:
                    kwargs["plural"] = True
                elif gender in gender_map and not is_cardinal_suffix:
                    kwargs["gender"] = gender_map[gender]
                return num2words.num2words(num, lang="ru", **kwargs) + " "
            except Exception:
                pass
        try:
            ordinal = num2words.num2words(
                num, lang="ru", to="cardinal" if is_cardinal_suffix else "ordinal"
            )
        except Exception:
            return match.group(0)
        words = ordinal.split()
        if not words:
            return ordinal
        parsed = morph.parse(words[-1])
        if parsed:
            p = parsed[0]
            target_tags = {case}
            if plural:
                target_tags.add("plur")
            elif gender:
                target_tags.add(gender)
            inflected = p.inflect(target_tags)
            if inflected:
                words[-1] = inflected.word
        return " ".join(words) + " "

    return ORDINAL_PATTERN.sub(repl, text)
