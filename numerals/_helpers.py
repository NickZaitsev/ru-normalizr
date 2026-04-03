from __future__ import annotations

import re
from typing import Any

import num2words

from .._morph import get_morph
from ..preprocess_utils import (
    NEGATIVE_NUMBER_PLACEHOLDER,
    PARAGRAPH_BREAK_PLACEHOLDER,
    normalize_ascii_quote_pairs,
)
from ..text_context import PUNCT_STRIP, normalize_context_token
from ._constants import ENTITY_DEFAULT_CASE, ENTITY_KEYWORDS, PREP_CASE, TIME_WORDS, VERB_CASE
from ._num2words import CARDINAL_GENDER_TO_NUM2WORDS, resolve_num2words_case

SENTENCE_PUNCTUATION_PATTERN = re.compile(r"\s+([.,!?;:])")
POINT_NUMBER_SPACING_PATTERN = re.compile(r"(?<=\.) (?=\d)")
POINT_WORD_PATTERN = re.compile(r"(точка [а-яё]+)\. (?=[а-яё])", flags=re.IGNORECASE)
REPEATED_PUNCTUATION_PATTERN = re.compile(r"([,!?;:])\1+")
DOUBLE_DOT_PATTERN = re.compile(r"(?<!\.)\.\.(?!\.)")
COMMA_DOT_PATTERN = re.compile(r",\.")
DOT_COMMA_PATTERN = re.compile(r"\.,")
OPEN_BRACKET_SPACING_PATTERN = re.compile(r"([\(\[\{])\s+")
CLOSE_BRACKET_SPACING_PATTERN = re.compile(r"\s+([\)\]\}])")
WORD_RANGE_HYPHEN_PATTERN = re.compile(r"(?<=[A-Za-zА-Яа-яЁё]) - (?=[A-Za-zА-Яа-яЁё])")


def is_integer_token(token: str) -> bool:
    clean_token = token.strip(PUNCT_STRIP)
    if clean_token.startswith(NEGATIVE_NUMBER_PLACEHOLDER):
        clean_token = clean_token[len(NEGATIVE_NUMBER_PLACEHOLDER) :]
    return clean_token.isdigit()


def parse_integer_token(token: str) -> tuple[bool, str] | None:
    clean_token = token.strip(PUNCT_STRIP)
    is_negative = clean_token.startswith(NEGATIVE_NUMBER_PLACEHOLDER)
    if is_negative:
        clean_token = clean_token[len(NEGATIVE_NUMBER_PLACEHOLDER) :]
    if not clean_token.isdigit():
        return None
    return is_negative, clean_token


def build_number_token(
    token: str, clean_token: str, replacement: str, is_negative: bool
) -> str:
    source = (
        f"{NEGATIVE_NUMBER_PLACEHOLDER}{clean_token}" if is_negative else clean_token
    )
    result = token.replace(source, replacement, 1)
    if is_negative:
        return f"минус {result}"
    return result


def apply_genitive_plural_heuristic(word: str, pos: str | None) -> str:
    if pos not in {"ADJF", "PRTF"}:
        return word
    lower_word = word.lower()
    if lower_word.endswith("ые"):
        return word[:-2] + ("Ых" if word.isupper() else "ых")
    if lower_word.endswith("ие"):
        return word[:-2] + ("Их" if word.isupper() else "их")
    if lower_word.endswith("ый") or lower_word.endswith("ой"):
        return word[:-2] + ("Ого" if word.isupper() else "ого")
    if lower_word.endswith("ий") or lower_word.endswith("ее"):
        return word[:-2] + ("Его" if word.isupper() else "его")
    if lower_word.endswith("ая"):
        return word[:-2] + ("Ой" if word.isupper() else "ой")
    if lower_word.endswith("яя"):
        return word[:-2] + ("Ей" if word.isupper() else "ей")
    return word


def safe_inflect(
    parsed_word: Any,
    target_tags: set[str],
    fallback_word: str | None = None,
    pos_filter: set[str] | None = None,
) -> str:
    if fallback_word is None:
        fallback_word = parsed_word.word
    try:
        inflected = parsed_word.inflect(target_tags)
        if inflected:
            return inflected.word
    except Exception:
        pass
    pos = parsed_word.tag.POS
    if (
        (pos_filter is None or pos in pos_filter)
        and "gent" in target_tags
        and "plur" in target_tags
        and pos in {"ADJF", "PRTF"}
    ):
        heuristic_result = apply_genitive_plural_heuristic(parsed_word.word, pos)
        if heuristic_result != parsed_word.word:
            return heuristic_result
    return fallback_word


def inflect_unit_lemma(lemma: str, target_tags: set[str]) -> str:
    morph = get_morph()

    def pick_preferred_parse(word: str) -> Any | None:
        parsed = morph.parse(word)
        if not parsed:
            return None
        for candidate in parsed:
            if "NOUN" in candidate.tag:
                return candidate
        return parsed[0]

    if " " not in lemma:
        parsed = pick_preferred_parse(lemma)
        if not parsed:
            return lemma
        return safe_inflect(parsed, target_tags, fallback_word=lemma)

    parts = lemma.split()
    if len(parts) != 2:
        return lemma

    adj_text, noun_text = parts
    adj_parsed = pick_preferred_parse(adj_text)
    noun_parsed = pick_preferred_parse(noun_text)
    if not adj_parsed or not noun_parsed:
        return lemma

    noun_form = safe_inflect(noun_parsed, target_tags, fallback_word=noun_text)
    adj_tags = {
        tag
        for tag in target_tags
        if tag in {"nomn", "gent", "datv", "accs", "ablt", "loct", "sing", "plur"}
    }
    if adj_tags == {"gent", "sing"}:
        noun_gender = noun_parsed.tag.gender
        adj_tags = {"plur", "nomn"} if noun_gender == "femn" else {"gent", "plur"}
    elif "plur" not in adj_tags:
        noun_gender = noun_parsed.tag.gender
        if noun_gender:
            adj_tags.add(noun_gender)
    adj_form = safe_inflect(
        adj_parsed,
        adj_tags,
        fallback_word=adj_text,
        pos_filter={"ADJF", "PRTF"},
    )
    return f"{adj_form} {noun_form}"


def is_case_reliable_noun(parsed_word: Any) -> bool:
    return "NOUN" in parsed_word.tag and "Fixd" not in parsed_word.tag


def noun_number_form(n: int) -> str:
    if n == 0:
        return "many"
    last_two = n % 100
    last_digit = n % 10
    if last_two in {11, 12, 13, 14}:
        return "many"
    if last_digit == 1:
        return "one"
    if last_digit in {2, 3, 4}:
        return "few"
    return "many"


def should_consume_abbreviation_dot(tokens: list[str], dot_index: int) -> bool:
    if dot_index >= len(tokens) or tokens[dot_index] != ".":
        return False
    if dot_index + 1 >= len(tokens):
        return False
    next_token = tokens[dot_index + 1]
    if "\n" in next_token or PARAGRAPH_BREAK_PLACEHOLDER in next_token:
        return False
    if next_token in {",", ";", ":", ")", "]", "}", "»", '"', "”"}:
        return True
    stripped_next = next_token.strip(PUNCT_STRIP)
    if not stripped_next:
        return False
    first_char = stripped_next[:1]
    return first_char.islower() or first_char.isdigit()


def should_keep_decimal_unit_dot(rest: str) -> bool:
    stripped_rest = rest.lstrip()
    if not stripped_rest:
        return True
    if "\n" in rest[: len(rest) - len(stripped_rest)]:
        return True
    next_char = stripped_rest[:1]
    if next_char in ".!?…":
        return True
    return not (next_char.islower() or next_char.isdigit())


def inflect_numeral_string(num_str: str, case: str, gender: str | None = None) -> str:
    try:
        value = int(num_str)
    except ValueError:
        return num_str
    num2words_case = resolve_num2words_case(case, default="")
    if num2words_case:
        try:
            kwargs: dict[str, Any] = {"case": num2words_case}
            if gender == "plur":
                kwargs["plural"] = True
            elif gender in CARDINAL_GENDER_TO_NUM2WORDS:
                kwargs["gender"] = CARDINAL_GENDER_TO_NUM2WORDS[gender]
            return num2words.num2words(value, lang="ru", **kwargs)
        except Exception:
            pass
    try:
        words = num2words.num2words(value, lang="ru").split()
    except Exception:
        return num_str
    if case == "nomn" and gender is None:
        return " ".join(words)
    morph = get_morph()
    magnitudes = {
        "тысяча": "femn",
        "миллион": "masc",
        "миллиард": "masc",
        "триллион": "masc",
        "биллион": "masc",
    }

    def get_magnitude_gender(word_str: str) -> str | None:
        return magnitudes.get(morph.parse(word_str)[0].normal_form)

    inflected_words: list[str] = []
    for index, word in enumerate(words):
        parsed = morph.parse(word)
        p = parsed[0] if parsed else None
        if not p:
            inflected_words.append(word)
            continue
        current_gender = gender
        is_magnitude_self = get_magnitude_gender(word) is not None
        if not is_magnitude_self and index + 1 < len(words):
            mag_gender = get_magnitude_gender(words[index + 1])
            if mag_gender:
                current_gender = mag_gender
        if is_magnitude_self:
            current_gender = None
            if case == "nomn":
                inflected_words.append(word)
                continue
            if case == "accs" and word.lower() != "тысяча":
                inflected_words.append(word)
                continue
        tags = {case}
        if current_gender:
            tags.add(current_gender)
        inflected = p.inflect(tags)
        if inflected:
            inflected_words.append(inflected.word)
        else:
            if current_gender:
                inflected_case = p.inflect({case})
                if inflected_case:
                    inflected_words.append(inflected_case.word)
                    continue
            inflected_words.append(word)
    return " ".join(inflected_words)


def get_target_tags_for_number(
    num: int, case: str, noun_gender: str | None = None
) -> set[str]:
    del noun_gender
    form = noun_number_form(num)
    if case == "nomn":
        return (
            {"nomn", "sing"}
            if form == "one"
            else {"gent", "sing"} if form == "few" else {"gent", "plur"}
        )
    if case == "accs":
        return (
            {"accs", "sing"}
            if form == "one"
            else {"gent", "sing"} if form == "few" else {"gent", "plur"}
        )
    return {case, "sing"} if form == "one" else {case, "plur"}


def _get_preposition_before_number(tokens: list[str], idx: int) -> tuple[str, str] | None:
    max_prep_len = min(3, idx)
    for prep_len in range(max_prep_len, 1, -1):
        start = idx - prep_len
        prep_tokens = [normalize_context_token(token) for token in tokens[start:idx]]
        if not all(prep_tokens):
            continue
        phrase = " ".join(prep_tokens)
        if phrase in PREP_CASE:
            return phrase, PREP_CASE[phrase]
    for i in range(idx - 1, max(-1, idx - 3), -1):
        word_left = normalize_context_token(tokens[i])
        if word_left == "чем":
            break
        if word_left in PREP_CASE:
            return word_left, PREP_CASE[word_left]
    return None


def get_numeral_case(tokens: list[str], idx: int) -> str:
    morph = get_morph()
    is_range_start = idx < len(tokens) - 1 and tokens[idx + 1] in {"-", "–", "—"}

    def unit_hint(number_index: int) -> str | None:
        if number_index + 1 >= len(tokens):
            return None
        hint = normalize_context_token(tokens[number_index + 1])
        if hint == "°" and number_index + 2 < len(tokens):
            return hint + normalize_context_token(tokens[number_index + 2])
        return hint or None

    if idx > 1 and tokens[idx - 1] == "и":
        current_hint = unit_hint(idx)
        for back in range(idx - 2, max(-1, idx - 6), -1):
            if any(char in tokens[back] for char in ".!?;:"):
                break
            if is_integer_token(tokens[back]) and unit_hint(back) == current_hint:
                return get_numeral_case(tokens, back)
    if idx > 1 and tokens[idx - 1] in {"-", "–", "—"} and is_integer_token(tokens[idx - 2]):
        return get_numeral_case(tokens, idx - 2)

    if is_range_start and idx > 0:
        prev_token = tokens[idx - 1].strip(".,!?;:")
        if prev_token:
            p_prev = morph.parse(prev_token)[0]
            prev_case = "loct" if "loc2" in p_prev.tag else p_prev.tag.case
            if prev_case:
                if is_case_reliable_noun(p_prev):
                    if idx > 1:
                        prev_prev = normalize_context_token(tokens[idx - 2])
                        if prev_prev in {"в", "во", "о", "об", "при"}:
                            return "loct"
                        if prev_prev in PREP_CASE:
                            return PREP_CASE[prev_prev]
                    return prev_case
                if p_prev.tag.POS in {"ADJF", "PRTF"}:
                    return prev_case

    prep_match = _get_preposition_before_number(tokens, idx)
    if prep_match is not None:
        word_left, prep_case = prep_match
        if word_left in {"с", "со"}:
            for k in range(idx + 1, min(len(tokens), idx + 5)):
                if tokens[k].lower() in {"до", "по"}:
                    return "gent"
        if word_left in {"в", "на"}:
            for j in range(idx + 1, min(len(tokens), idx + 6)):
                if any(char in tokens[j] for char in ".!?;:,"):
                    break
                p = morph.parse(tokens[j])[0]
                if is_case_reliable_noun(p):
                    if p.tag.case == "loct" or "loc2" in p.tag:
                        return "loct"
                    is_loc = p.inflect({"loct"})
                    is_acc = p.inflect({"accs"})
                    word_curr = tokens[j].lower()
                    if is_loc and is_loc.word == word_curr:
                        return "loct"
                    if is_acc and is_acc.word == word_curr:
                        return "accs"
                if "VERB" in p.tag or "INFN" in p.tag:
                    break
            for j in range(idx + 1, min(len(tokens), idx + 4)):
                p = morph.parse(tokens[j])[0]
                word_norm = p.normal_form
                if word_norm in set(TIME_WORDS) | {
                    "январь",
                    "февраль",
                    "март",
                    "апрель",
                    "май",
                    "июнь",
                    "июль",
                    "август",
                    "сентябрь",
                    "октябрь",
                    "ноябрь",
                    "декабрь",
                }:
                    if is_integer_token(tokens[idx]):
                        parsed_num = parse_integer_token(tokens[idx])
                        if parsed_num is None:
                            return "loct"
                        _, unsigned = parsed_num
                        val = int(unsigned)
                        return "loct" if 1000 <= val <= 2100 else "accs"
                    return "loct"
            return "accs"
        if word_left == "по":
            if is_integer_token(tokens[idx]):
                parsed_num = parse_integer_token(tokens[idx])
                if parsed_num is None:
                    return "datv"
                _, unsigned = parsed_num
                val = int(unsigned)
                if val % 10 == 1 and val % 100 != 11:
                    return "datv"
                return "accs"
            return "datv"
        return prep_case

    blocked_by_noun = False
    for i in range(idx - 1, max(-1, idx - 3), -1):
        p = morph.parse(tokens[i])[0]
        if p.tag.POS == "NOUN":
            blocked_by_noun = True
            break

    for i in range(max(0, idx - 2), idx):
        p = morph.parse(tokens[i])[0]
        if blocked_by_noun and p.tag.POS in {"ADJF", "PRTF"}:
            continue
        if p.tag.POS in {"ADJF", "PRTF"} and p.tag.case:
            return p.tag.case

    for i in range(idx - 1, max(-1, idx - 5), -1):
        word_left = tokens[i].lower().strip(".,!?;:")
        p_verb = morph.parse(word_left)[0]
        if p_verb.normal_form in VERB_CASE:
            return VERB_CASE[p_verb.normal_form]
        if any(char in tokens[i] for char in ".!?"):
            break

    if idx < len(tokens) - 1:
        word_right = tokens[idx + 1].lower().strip(".,!?;:")
        if word_right:
            p_right = morph.parse(word_right)[0]
            noun_case = p_right.tag.case
            if not (
                is_case_reliable_noun(p_right)
                and (noun_case in {"gent", "datv", "ablt", "loct"} or "loc2" in p_right.tag)
            ):
                for entity_type, keywords in ENTITY_KEYWORDS.items():
                    if p_right.normal_form in keywords or word_right in keywords:
                        return ENTITY_DEFAULT_CASE[entity_type]

    if idx < len(tokens) - 1:
        word_right = tokens[idx + 1].lower().strip(".,!?;:")
        if word_right:
            p_right = morph.parse(word_right)[0]
            if is_case_reliable_noun(p_right):
                noun_case = p_right.tag.case
                if noun_case in {"datv", "ablt", "loct"} or "loc2" in p_right.tag:
                    return "loct" if noun_case == "loct" or "loc2" in p_right.tag else noun_case

    if idx > 0:
        right_boundary = idx + 1 >= len(tokens) or any(
            char in tokens[idx + 1] for char in ",.;:!?…"
        )
        if right_boundary:
            for back in range(idx - 1, max(-1, idx - 4), -1):
                left_token = normalize_context_token(tokens[back])
                if not left_token or left_token in {"уже", "теперь"}:
                    continue
                p_left = morph.parse(left_token)[0]
                if p_left.tag.case == "datv" and p_left.tag.POS in {"NPRO", "NOUN"}:
                    return "datv"
                break

    if idx == 0 or any(char in tokens[idx - 1] for char in ".!?"):
        return "nomn"
    return "nomn"


def detokenize(tokens: list[str]) -> str:
    parts: list[str] = []
    previous_was_newline = True
    for token in tokens:
        if not token:
            continue
        if "\n" in token or PARAGRAPH_BREAK_PLACEHOLDER in token:
            parts.append(token)
            previous_was_newline = True
            continue
        if parts and not previous_was_newline:
            parts.append(" ")
        parts.append(token)
        previous_was_newline = False
    text = "".join(parts)
    text = SENTENCE_PUNCTUATION_PATTERN.sub(r"\1", text)
    text = POINT_NUMBER_SPACING_PATTERN.sub("", text)
    text = POINT_WORD_PATTERN.sub(r"\1.", text)
    text = REPEATED_PUNCTUATION_PATTERN.sub(r"\1", text)
    text = DOUBLE_DOT_PATTERN.sub(".", text)
    text = COMMA_DOT_PATTERN.sub(".", text)
    text = DOT_COMMA_PATTERN.sub(".", text)
    text = OPEN_BRACKET_SPACING_PATTERN.sub(r"\1", text)
    text = CLOSE_BRACKET_SPACING_PATTERN.sub(r"\1", text)
    text = WORD_RANGE_HYPHEN_PATTERN.sub(" — ", text)
    return normalize_ascii_quote_pairs(text)
