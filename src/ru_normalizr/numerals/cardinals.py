from __future__ import annotations

import logging
import re

import num2words

from .._morph import first_parse_required, parse_word, select_parse
from ..preprocess_utils import NEGATIVE_NUMBER_PLACEHOLDER
from ..text_context import PUNCT_STRIP, normalize_context_token, simple_tokenize
from ..text_scan import first_non_whitespace_index
from ._constants import (
    DIGIT_PATTERN,
    NUMERIC_UNIT_RANGE_PATTERN,
    POST_NUMERAL_ABBREVIATION_PATTERNS,
    PREP_CASE,
    TIME_WORDS,
    UNITS_DATA,
    resolve_unit_form,
    resolve_unit_info,
)
from ._helpers import (
    _build_numeral_token_context,
    build_number_token,
    detokenize,
    get_numeral_case,
    get_target_tags_for_number,
    inflect_numeral_string,
    inflect_unit_lemma,
    noun_number_form,
    parse_integer_token,
    paucal_accusative_case,
    should_consume_abbreviation_dot,
    should_keep_tokenized_decimal_unit_dot,
)
from .unit_expressions import match_unit_tokens
from .unit_rendering import render_unit_expression

logger = logging.getLogger(__name__)

_MULTIPLIER_LEMMAS = frozenset({"тысяча", "миллион", "миллиард", "триллион"})
_CURRENCY_SYMBOL_UNITS = frozenset(
    {
        "$",
        "€",
        "₽",
        "£",
        "¥",
        "₴",
        "₸",
        "₺",
        "₹",
        "¢",
        "₪",
        "₩",
        "₫",
        "₱",
        "₦",
    }
)


def _resolve_range_unit_info(unit_raw: str):
    unit_lower = unit_raw.lower().strip(".")
    direct = resolve_unit_info(unit_raw)
    if direct is not None:
        return direct

    parts = [part for part in unit_lower.split() if part]
    if len(parts) < 2:
        return None

    noun_parse = next(
        (
            candidate
            for candidate in parse_word(parts[-1])
            if "NOUN" in candidate.tag
        ),
        None,
    )
    if noun_parse is None:
        return None

    if len(parts) == 2:
        head_parse = next(
            (
                candidate
                for candidate in parse_word(parts[0])
                if candidate.tag.POS in {"ADJF", "PRTF"}
            ),
            None,
        )
        if head_parse is None:
            return None
        lemma = f"{head_parse.normal_form} {noun_parse.normal_form}"
    else:
        first_parse = next(
            (
                candidate
                for candidate in parse_word(parts[0])
                if candidate.tag.POS in {"ADJF", "PRTF"}
            ),
            None,
        )
        second_parse = next(
            (
                candidate
                for candidate in parse_word(parts[1])
                if candidate.tag.POS in {"ADJF", "PRTF"}
            ),
            None,
        )
        if first_parse is None or second_parse is None:
            return None
        lemma = (
            f"{first_parse.normal_form} {second_parse.normal_form}"
            f" {noun_parse.normal_form}"
        )

    for info in UNITS_DATA.values():
        if info.lemma == lemma:
            return info
    return None


def normalize_cardinal_numerals(text: str) -> str:
    tokens = simple_tokenize(text)
    token_context = _build_numeral_token_context(tokens)
    result_tokens: list[str] = []

    def is_word_token(token: str) -> bool:
        return bool(re.fullmatch(r"[^\W\d_]+", token, re.UNICODE))

    def is_ambiguous_preposition_token(token: str) -> bool:
        clean = token.lower().strip(PUNCT_STRIP)
        return bool(clean) and " " not in clean and clean in PREP_CASE

    def inanimate_cardinal_case(value: int, case: str) -> str:
        if case != "accs":
            return case
        final_group_needs_accusative = value % 10 == 1 and value % 100 != 11
        thousands = (value // 1000) % 1000
        thousands_need_accusative = thousands % 10 == 1 and thousands % 100 != 11
        return "accs" if final_group_needs_accusative or thousands_need_accusative else "nomn"

    def should_skip_unit_candidate(start_index: int, token_span: int, unit_raw: str) -> bool:
        chunk = tokens[start_index : start_index + token_span]
        if (
            token_span == 1
            and unit_raw == unit_raw.strip(PUNCT_STRIP)
            and is_ambiguous_preposition_token(unit_raw)
            and start_index + token_span < len(tokens)
        ):
            next_token = tokens[start_index + token_span].strip(PUNCT_STRIP)
            if next_token:
                return True
        return (
            token_span > 1
            and all(is_word_token(token) for token in chunk)
            and any(is_ambiguous_preposition_token(token) for token in chunk[1:])
        )

    def extract_unit_candidate(start_index: int) -> tuple[str, str, int] | None:
        match = match_unit_tokens(tokens, start_index)
        if match is None or should_skip_unit_candidate(
            start_index, match.consumed_tokens, match.source
        ):
            return None
        return match.alias.casefold().strip("."), match.source, match.consumed_tokens

    def is_redundant_unit_token(token_index: int, expected_lemma: str) -> bool:
        if token_index >= len(tokens):
            return False
        token_lower = tokens[token_index].lower().strip(PUNCT_STRIP)
        if not token_lower:
            return False
        parsed = parse_word(token_lower)
        if not parsed:
            return False
        candidate = parsed[0]
        return "NOUN" in candidate.tag and candidate.normal_form == expected_lemma

    i = 0
    while i < len(tokens):
        token = tokens[i]
        first_char = token[:1]
        is_numeric_candidate = first_char.isnumeric() or first_char == NEGATIVE_NUMBER_PLACEHOLDER
        if not is_numeric_candidate and first_char in PUNCT_STRIP:
            stripped_candidate = token.strip(PUNCT_STRIP)
            is_numeric_candidate = bool(stripped_candidate) and (
                stripped_candidate[0].isnumeric()
                or stripped_candidate.startswith(NEGATIVE_NUMBER_PLACEHOLDER)
            )
        if not is_numeric_candidate:
            result_tokens.append(token)
            i += 1
            continue
        parsed_num = parse_integer_token(token)
        if parsed_num is None:
            result_tokens.append(token)
            i += 1
            continue

        is_negative, clean_token = parsed_num
        val = int(clean_token)
        case = get_numeral_case(tokens, i, _context=token_context)
        inflected_num = inflect_numeral_string(clean_token, case)
        num_words = build_number_token(token, clean_token, inflected_num, is_negative)

        if i + 2 < len(tokens):
            adj_token = tokens[i + 1]
            noun_token = tokens[i + 2]
            clean_adj = adj_token.lower().strip(PUNCT_STRIP)
            clean_noun = noun_token.lower().strip(PUNCT_STRIP)
            p_adj = select_parse(clean_adj, pos={"ADJF", "PRTF"})
            p_noun = select_parse(clean_noun, pos="NOUN")
            if (
                p_adj is not None
                and p_noun is not None
                and resolve_unit_info(adj_token) is None
            ):
                gender = p_noun.tag.gender
                is_anim = "anim" in p_noun.tag
                target_num_case = paucal_accusative_case(val, case, animate=is_anim)
                num_words = build_number_token(
                    token,
                    clean_token,
                    inflect_numeral_string(
                        clean_token, target_num_case, gender, is_anim
                    ),
                    is_negative,
                )
                result_tokens.extend([num_words, adj_token, noun_token])
                i += 3
                continue

        if i + 1 < len(tokens):
            noun_token = tokens[i + 1]
            next_token_lower = noun_token.lower().strip(PUNCT_STRIP)
            unit_candidate = extract_unit_candidate(i + 1)
            unit_token_span = 1
            unit_raw = noun_token
            if next_token_lower == "°" and i + 2 < len(tokens):
                degree_suffix = tokens[i + 2].lower().strip(PUNCT_STRIP)
                if degree_suffix in {"c", "k", "f", "с", "к", "ф"}:
                    next_token_lower = f"°{degree_suffix}"
                    noun_token = f"{noun_token}{tokens[i + 2]}"
                    unit_raw = noun_token
                    unit_token_span = 2
            elif unit_candidate:
                next_token_lower, unit_raw, unit_token_span = unit_candidate
            if should_skip_unit_candidate(i + 1, unit_token_span, unit_raw):
                unit_info = None
            else:
                unit_info = resolve_unit_info(unit_raw)
                if unit_info is None and unit_token_span == 1:
                    resolved_form = resolve_unit_form(unit_raw)
                    if resolved_form is not None and (
                        resolved_form.morphology.paradigm
                        or resolved_form.morphology.indeclinable
                    ):
                        unit_info = resolved_form
            if unit_info:
                if (
                    1000 <= val <= 2100
                    and i > 0
                    and normalize_context_token(tokens[i - 1]) == "в"
                ):
                    case = "accs"
                if (
                    unit_info.morphology.indeclinable
                    and next_token_lower.strip(".") == unit_info.lemma
                ):
                    case = get_numeral_case(
                        tokens,
                        i,
                        _context=token_context,
                        _visible_length=i + 1,
                    )
                preserve_unit_dot = (
                    unit_raw.endswith(".")
                    and not should_consume_abbreviation_dot(
                        tokens, i + unit_token_span
                    )
                )
                lemma = unit_info.lemma
                u_gender = unit_info.gender
                u_category = unit_info.category
                u_suffix = unit_info.suffix
                if (
                    u_category == "money"
                    and next_token_lower in _CURRENCY_SYMBOL_UNITS
                    and i + 2 < len(tokens)
                ):
                    multiplier_token = tokens[i + 2]
                    multiplier_lower = multiplier_token.lower().strip(PUNCT_STRIP)
                    p_multiplier = first_parse_required(multiplier_lower)
                    if (
                        "NOUN" in p_multiplier.tag
                        and p_multiplier.normal_form in _MULTIPLIER_LEMMAS
                    ):
                        target_num_case = inanimate_cardinal_case(val, case)
                        multiplier_gender = p_multiplier.tag.gender or "masc"
                        num_words = build_number_token(
                            token,
                            clean_token,
                            inflect_numeral_string(
                                clean_token, target_num_case, multiplier_gender, False
                            ),
                            is_negative,
                        )
                        result_tokens.extend(
                            [
                                num_words,
                                multiplier_token,
                                inflect_unit_lemma(unit_info, {"gent", "plur"}),
                            ]
                        )
                        i += 4 if is_redundant_unit_token(i + 3, lemma) else 3
                        continue

                target_num_case = inanimate_cardinal_case(val, case)
                num_words = build_number_token(
                    token,
                    clean_token,
                    inflect_numeral_string(
                        clean_token, target_num_case, u_gender, False
                    ),
                    is_negative,
                )
                if lemma == "человек" and case in {"nomn", "accs"}:
                    unit_form = noun_number_form(val)
                    inflected_unit = "человека" if unit_form == "few" else "человек"
                else:
                    inflected_unit = render_unit_expression(
                        unit_info,
                        get_target_tags_for_number(val, case, u_gender),
                    )
                full_unit = (
                    inflected_unit + (f" {u_suffix}" if u_suffix else "")
                    if lemma == "человек" and case in {"nomn", "accs"}
                    else inflected_unit
                )
                match_unit = (
                    re.search(re.escape(next_token_lower), noun_token, re.IGNORECASE)
                    if unit_token_span == 1
                    else None
                )
                if match_unit:
                    full_unit = (
                        noun_token[: match_unit.start()]
                        + full_unit
                        + noun_token[match_unit.end() :]
                    )
                if preserve_unit_dot and should_keep_tokenized_decimal_unit_dot(
                    tokens,
                    i + 1 + unit_token_span,
                ):
                    full_unit += "."
                result_tokens.extend([num_words, full_unit])
                step = 1 + unit_token_span
                if (
                    unit_token_span == 1
                    and next_token_lower.startswith("°")
                    and len(next_token_lower) == 2
                ):
                    step = 3
                if i + step < len(tokens) and should_consume_abbreviation_dot(tokens, i + step):
                    step += 1
                if is_redundant_unit_token(i + step, lemma):
                    step += 1
                if lemma in _MULTIPLIER_LEMMAS and i + 2 < len(tokens):
                    next_next_token = tokens[i + 2]
                    nn_unit_info = resolve_unit_info(next_next_token)
                    if nn_unit_info:
                        nn_inflected = render_unit_expression(
                            nn_unit_info, {"gent", "plur"}
                        )
                        result_tokens.append(nn_inflected)
                        i += step + 1
                        continue
                i += step
                continue

            p_noun = select_parse(next_token_lower, pos="NOUN")
            if p_noun is not None:
                gender = TIME_WORDS.get(next_token_lower, p_noun.tag.gender)
                is_anim = "anim" in p_noun.tag
                target_num_case = paucal_accusative_case(val, case, animate=is_anim)
                num_words = build_number_token(
                    token,
                    clean_token,
                    inflect_numeral_string(
                        clean_token, target_num_case, gender, is_anim
                    ),
                    is_negative,
                )
                result_tokens.extend([num_words, noun_token])
                i += 2
                continue

        result_tokens.append(num_words)
        i += 1
    return detokenize(result_tokens)


def normalize_numeric_unit_ranges(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        left = match.group("left")
        right = match.group("right")
        unit_raw = match.group("unit")
        unit_info = _resolve_range_unit_info(unit_raw)
        if not unit_info:
            return match.group(0)
        context = text[max(0, match.start() - 40) : match.start()]
        tokens_left = simple_tokenize(context)
        case = get_numeral_case([*tokens_left, left], len(tokens_left))
        u_gender = unit_info.gender
        u_suffix = unit_info.suffix

        def numeral_for_range(value_text: str) -> str:
            value = int(value_text)
            target_case = paucal_accusative_case(value, case, animate=False)
            return inflect_numeral_string(value_text, target_case, u_gender, False)

        right_value = int(right)
        unit_words = inflect_unit_lemma(
            unit_info, get_target_tags_for_number(right_value, case, u_gender)
        )
        if u_suffix:
            unit_words += f" {u_suffix}"
        return f"{numeral_for_range(left)} — {numeral_for_range(right)} {unit_words}"

    return NUMERIC_UNIT_RANGE_PATTERN.sub(repl, text)


def normalize_remaining_post_numeral_abbreviations(text: str) -> str:
    def preserve_sentence_boundary(
        match: re.Match[str], replacement: str, source_text: str
    ) -> str:
        next_index, _ = first_non_whitespace_index(source_text, match.end())
        if next_index >= len(source_text):
            return f"{replacement}."
        next_char = source_text[next_index]
        if next_char in "\n.!?…":
            return f"{replacement}."
        return replacement

    for pattern, replacement in POST_NUMERAL_ABBREVIATION_PATTERNS:
        text = pattern.sub(
            lambda match, repl=replacement, src=text: preserve_sentence_boundary(
                match, repl, src
            ),
            text,
        )
    return text


def normalize_all_digits_everywhere(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        try:
            return num2words.num2words(int(match.group(0)), lang="ru")
        except Exception as exc:
            logger.debug("num2words failed for %r: %s", match.group(0), exc)
            return match.group(0)

    return DIGIT_PATTERN.sub(repl, text)
