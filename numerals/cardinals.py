from __future__ import annotations

import re

import num2words

from .._morph import get_morph
from ._constants import (
    DIGIT_PATTERN,
    NUMERIC_UNIT_RANGE_PATTERN,
    POST_NUMERAL_ABBREVIATION_PATTERNS,
    TIME_WORDS,
    UNITS_DATA,
)
from ._helpers import (
    build_number_token,
    detokenize,
    get_numeral_case,
    get_target_tags_for_number,
    inflect_numeral_string,
    parse_integer_token,
    safe_inflect,
    should_consume_abbreviation_dot,
    simple_tokenize,
)


def normalize_cardinal_numerals(text: str) -> str:
    morph = get_morph()
    tokens = simple_tokenize(text)
    result_tokens: list[str] = []

    def is_redundant_unit_token(token_index: int, expected_lemma: str) -> bool:
        if token_index >= len(tokens):
            return False
        token_lower = tokens[token_index].lower().strip('.,:;!"«»()[]{}')
        if not token_lower:
            return False
        parsed = morph.parse(token_lower)
        if not parsed:
            return False
        candidate = parsed[0]
        return "NOUN" in candidate.tag and candidate.normal_form == expected_lemma

    i = 0
    while i < len(tokens):
        token = tokens[i]
        parsed_num = parse_integer_token(token)
        if parsed_num is None:
            result_tokens.append(token)
            i += 1
            continue

        is_negative, clean_token = parsed_num
        val = int(clean_token)
        case = get_numeral_case(tokens, i)
        inflected_num = inflect_numeral_string(clean_token, case)
        num_words = build_number_token(token, clean_token, inflected_num, is_negative)

        if i + 2 < len(tokens):
            adj_token = tokens[i + 1]
            noun_token = tokens[i + 2]
            clean_adj = adj_token.lower().strip('.,:;!"«»()[]{}')
            clean_noun = noun_token.lower().strip('.,:;!"«»()[]{}')
            p_adj = morph.parse(clean_adj)[0]
            p_noun = morph.parse(clean_noun)[0]
            if ("ADJF" in p_adj.tag or "PRTF" in p_adj.tag) and "NOUN" in p_noun.tag:
                gender = p_noun.tag.gender
                is_anim = "anim" in p_noun.tag
                target_num_case = case
                if case == "accs":
                    rem100 = val % 100
                    rem10 = val % 10
                    if rem10 in (2, 3, 4) and rem100 not in (12, 13, 14):
                        target_num_case = "gent" if is_anim else "nomn"
                num_words = build_number_token(
                    token,
                    clean_token,
                    inflect_numeral_string(clean_token, target_num_case, gender),
                    is_negative,
                )
                result_tokens.extend([num_words, adj_token, noun_token])
                i += 3
                continue

        if i + 1 < len(tokens):
            noun_token = tokens[i + 1]
            next_token_lower = noun_token.lower().strip('.,:;!"«»()[]{}')
            if next_token_lower == "°" and i + 2 < len(tokens):
                degree_suffix = tokens[i + 2].lower().strip('.,:;!"«»()[]{}')
                if degree_suffix in {"c", "k", "f"}:
                    next_token_lower = f"°{degree_suffix}"
                    noun_token = f"{noun_token}{tokens[i + 2]}"
            unit_info = UNITS_DATA.get(next_token_lower)
            if unit_info:
                lemma, u_gender, u_category, *u_suffix = unit_info
                p_unit = morph.parse(lemma)[0]
                multipliers = {"тысяча", "миллион", "миллиард", "триллион"}
                currency_symbol_units = {
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
                if (
                    u_category == "money"
                    and next_token_lower in currency_symbol_units
                    and i + 2 < len(tokens)
                ):
                    multiplier_token = tokens[i + 2]
                    multiplier_lower = multiplier_token.lower().strip('.,:;!"«»()[]{}')
                    p_multiplier = morph.parse(multiplier_lower)[0]
                    if (
                        "NOUN" in p_multiplier.tag
                        and p_multiplier.normal_form in multipliers
                    ):
                        target_num_case = case
                        if case == "accs":
                            rem100 = val % 100
                            rem10 = val % 10
                            if rem10 in (2, 3, 4) and rem100 not in (12, 13, 14):
                                target_num_case = "nomn"
                        multiplier_gender = p_multiplier.tag.gender or "masc"
                        num_words = build_number_token(
                            token,
                            clean_token,
                            inflect_numeral_string(
                                clean_token, target_num_case, multiplier_gender
                            ),
                            is_negative,
                        )
                        result_tokens.extend(
                            [
                                num_words,
                                multiplier_token,
                                safe_inflect(p_unit, {"gent", "plur"}),
                            ]
                        )
                        i += 4 if is_redundant_unit_token(i + 3, lemma) else 3
                        continue

                target_num_case = case
                if case == "accs":
                    rem100 = val % 100
                    rem10 = val % 10
                    if rem10 in (2, 3, 4) and rem100 not in (12, 13, 14):
                        target_num_case = "nomn"
                num_words = build_number_token(
                    token,
                    clean_token,
                    inflect_numeral_string(clean_token, target_num_case, u_gender),
                    is_negative,
                )
                inflected_unit = safe_inflect(
                    p_unit, get_target_tags_for_number(val, case, u_gender)
                )
                full_unit = inflected_unit + (f" {u_suffix[0]}" if u_suffix else "")
                match_unit = re.search(
                    re.escape(next_token_lower), noun_token, re.IGNORECASE
                )
                if match_unit:
                    full_unit = (
                        noun_token[: match_unit.start()]
                        + full_unit
                        + noun_token[match_unit.end() :]
                    )
                result_tokens.extend([num_words, full_unit])
                step = (
                    3 if next_token_lower.startswith("°") and len(next_token_lower) == 2 else 2
                )
                if i + step < len(tokens) and should_consume_abbreviation_dot(tokens, i + step):
                    step += 1
                if is_redundant_unit_token(i + step, lemma):
                    step += 1
                if lemma in multipliers and i + 2 < len(tokens):
                    next_next_token = tokens[i + 2]
                    nn_token_lower = next_next_token.lower().strip('.,:;!"«»()[]{}')
                    nn_unit_info = UNITS_DATA.get(nn_token_lower)
                    if nn_unit_info:
                        nn_lemma, _, _, *nn_suffix = nn_unit_info
                        p_nn = morph.parse(nn_lemma)[0]
                        nn_inflected = safe_inflect(p_nn, {"gent", "plur"})
                        if nn_suffix:
                            nn_inflected += f" {nn_suffix[0]}"
                        result_tokens.append(nn_inflected)
                        i += step + 1
                        continue
                i += step
                continue

            p_noun = morph.parse(next_token_lower)[0]
            if "NOUN" in p_noun.tag:
                gender = TIME_WORDS.get(next_token_lower, p_noun.tag.gender)
                is_anim = "anim" in p_noun.tag
                target_num_case = case
                if case == "accs":
                    rem100 = val % 100
                    rem10 = val % 10
                    if rem10 in (2, 3, 4) and rem100 not in (12, 13, 14):
                        target_num_case = "gent" if is_anim else "nomn"
                num_words = build_number_token(
                    token,
                    clean_token,
                    inflect_numeral_string(clean_token, target_num_case, gender),
                    is_negative,
                )
                result_tokens.extend([num_words, noun_token])
                i += 2
                continue

        result_tokens.append(num_words)
        i += 1
    return detokenize(result_tokens)


def normalize_numeric_unit_ranges(text: str) -> str:
    morph = get_morph()

    def repl(match: re.Match[str]) -> str:
        left = match.group("left")
        right = match.group("right")
        unit_raw = match.group("unit")
        unit_lower = unit_raw.lower().strip(".")
        unit_info = UNITS_DATA.get(unit_lower)
        if not unit_info:
            return match.group(0)
        context = text[max(0, match.start() - 40) : match.start()]
        tokens_left = simple_tokenize(context)
        case = get_numeral_case(tokens_left + [left], len(tokens_left))
        lemma, u_gender, _, *u_suffix = unit_info

        def numeral_for_range(value_text: str) -> str:
            value = int(value_text)
            target_case = case
            if case == "accs":
                rem100 = value % 100
                rem10 = value % 10
                if rem10 in (2, 3, 4) and rem100 not in (12, 13, 14):
                    target_case = "nomn"
            return inflect_numeral_string(value_text, target_case, u_gender)

        right_value = int(right)
        p_unit = morph.parse(lemma)[0]
        unit_words = safe_inflect(
            p_unit, get_target_tags_for_number(right_value, case, u_gender)
        )
        if u_suffix:
            unit_words += f" {u_suffix[0]}"
        return f"{numeral_for_range(left)} — {numeral_for_range(right)} {unit_words}"

    return NUMERIC_UNIT_RANGE_PATTERN.sub(repl, text)


def normalize_remaining_post_numeral_abbreviations(text: str) -> str:
    for pattern, replacement in POST_NUMERAL_ABBREVIATION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def normalize_all_digits_everywhere(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        try:
            return num2words.num2words(int(match.group(0)), lang="ru")
        except Exception:
            return match.group(0)

    return DIGIT_PATTERN.sub(repl, text)
