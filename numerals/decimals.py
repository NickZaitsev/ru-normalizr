from __future__ import annotations

import re

import num2words

from .._morph import get_morph
from ..preprocess_utils import NEGATIVE_NUMBER_PLACEHOLDER
from ..text_context import simple_tokenize
from ._constants import PREP_CASE, UNIT_TOKEN_FRAGMENT, UNITS_DATA
from ._helpers import (
    get_numeral_case,
    inflect_numeral_string,
    inflect_unit_lemma,
    safe_inflect,
    should_keep_decimal_unit_dot,
)

DECIMAL_PATTERN = re.compile(
    rf"(?<!\d)(?P<num>(?:-|{re.escape(NEGATIVE_NUMBER_PLACEHOLDER)})?\d+[.,]\d+)(?:\s*(?P<unit>{UNIT_TOKEN_FRAGMENT})(?P<unit_dot>\.)?)?(?:\s+(?P<unit2>{UNIT_TOKEN_FRAGMENT})(?P<unit2_dot>\.)?)?(?!\d)"
)


def normalize_decimals(text: str) -> str:
    morph = get_morph()

    def inflect_fraction_numerator(num_str: str, case: str) -> str:
        try:
            value = int(num_str)
        except ValueError:
            return num_str
        words = inflect_numeral_string(num_str, case)
        if value == 0:
            return words
        last_word = words.split()[-1]
        parsed_last = morph.parse(last_word)
        if not parsed_last:
            return words
        target_tags = None
        if value % 10 == 1 and value % 100 != 11:
            target_tags = {case, "femn", "sing"}
        elif value % 10 == 2 and value % 100 != 12 and case in {"nomn", "accs"}:
            target_tags = {case, "femn"}
        if not target_tags:
            return words
        inflected = parsed_last[0].inflect(target_tags)
        if not inflected:
            return words
        parts = words.split()
        parts[-1] = inflected.word
        return " ".join(parts)

    def render_fraction_order_words(digits: int, frac_val: int, case: str) -> str:
        if digits <= 0:
            return ""
        try:
            base = num2words.num2words(10**digits, lang="ru", to="ordinal")
        except Exception:
            base = {
                1: "десятая",
                2: "сотая",
                3: "тысячная",
                4: "десятитысячная",
                5: "стотысячная",
                6: "миллионная",
            }.get(digits, "десятитысячная")
        parsed = morph.parse(base)
        if not parsed:
            return base
        tags = (
            {case, "femn", "sing"}
            if frac_val % 10 == 1 and frac_val % 100 != 11
            else ({"gent", "plur"} if case in ["nomn", "accs"] else {case, "plur"})
        )
        return safe_inflect(parsed[0], tags, fallback_word=base)

    def is_ambiguous_preposition_token(token: str) -> bool:
        clean = token.lower().strip('.,:;!"«»()[]{}')
        return bool(clean) and " " not in clean and clean in PREP_CASE

    def should_skip_unit_candidate(unit_raw: str, rest: str) -> bool:
        if not is_ambiguous_preposition_token(unit_raw):
            return False
        stripped_rest = rest.lstrip()
        if not stripped_rest:
            return False
        next_char = stripped_rest[:1]
        return bool(re.match(r"[^\W_]", next_char, re.UNICODE))

    def should_skip_combined_unit_candidate(unit_parts: list[str]) -> bool:
        cleaned_parts = [part.strip('.,:;!"«»()[]{}') for part in unit_parts]
        return any(
            cleaned and is_ambiguous_preposition_token(cleaned)
            for cleaned in cleaned_parts[1:]
        )

    def repl(match: re.Match[str]) -> str:
        s = match.group("num").replace(",", ".")
        unit_raw = match.group("unit")
        start_pos = match.start()
        context = text[max(0, start_pos - 40) : start_pos]
        tokens_left = simple_tokenize(context)
        case = get_numeral_case(tokens_left + [s], len(tokens_left))
        is_negative = s.startswith("-") or s.startswith(NEGATIVE_NUMBER_PLACEHOLDER)
        abs_s = s.lstrip(f"-{NEGATIVE_NUMBER_PLACEHOLDER}")
        parts = abs_s.split(".")
        if len(parts) != 2:
            return match.group(0)
        int_part_s, frac_part_s = parts
        int_val = int(int_part_s)
        frac_val = int(frac_part_s)
        digits = len(frac_part_s)
        int_words = inflect_numeral_string(int_part_s, case, gender="femn")
        p_cel = morph.parse("целая")[0]
        tags_cel = (
            {case, "femn", "sing"}
            if int_val % 10 == 1 and int_val % 100 != 11
            else ({"gent", "plur"} if case in ["nomn", "accs"] else {case, "plur"})
        )
        cel_words = safe_inflect(p_cel, tags_cel)
        frac_words = inflect_fraction_numerator(frac_part_s, case)
        order_words = render_fraction_order_words(digits, frac_val, case)
        result = f"{int_words} {cel_words} {frac_words} {order_words}"
        if unit_raw:
            unit_dot = match.group("unit_dot")
            unit2_raw = match.group("unit2")
            unit2_dot = match.group("unit2_dot")
            unit_info = None
            unit_consumes_second_token = False
            if unit2_raw and not should_skip_combined_unit_candidate([unit_raw, unit2_raw]):
                combined_candidates = []
                if unit_dot:
                    combined_candidates.append(f"{unit_raw}.{unit2_raw}")
                combined_candidates.append(f"{unit_raw}{unit2_raw}")
                for candidate_raw in combined_candidates:
                    candidate_key = candidate_raw.lower().strip(".")
                    unit_info = UNITS_DATA.get(candidate_key)
                    if unit_info:
                        unit_consumes_second_token = True
                        break
            if unit_info is None:
                unit_lower = unit_raw.lower().strip(".")
                if not should_skip_unit_candidate(unit_raw, text[match.end("unit") :]):
                    unit_info = UNITS_DATA.get(unit_lower)
            unit2_processed = False
            if unit_info:
                lemma, _, _, *u_suffix = unit_info
                result += " " + inflect_unit_lemma(lemma, {"gent", "sing"})
                if u_suffix:
                    result += " " + u_suffix[0]
                if unit_consumes_second_token:
                    unit2_processed = True
                elif unit2_raw:
                    unit2_lower = unit2_raw.lower().strip(".")
                    unit2_info = UNITS_DATA.get(unit2_lower)
                    multipliers = {"тысяча", "миллион", "миллиард", "триллион"}
                    if lemma in multipliers and unit2_info:
                        lemma2, _, _, *suffix2 = unit2_info
                        result += " " + inflect_unit_lemma(lemma2, {"gent", "plur"})
                        if suffix2:
                            result += " " + suffix2[0]
                        unit2_processed = True
                if unit2_raw and not unit2_processed:
                    result += " " + unit2_raw
            else:
                result += " " + unit_raw
                if unit2_raw:
                    result += " " + unit2_raw
            if (
                unit2_dot
                and unit2_raw
                and should_keep_decimal_unit_dot(text[match.end() :])
            ):
                result += "."
            elif (
                unit_dot
                and not unit2_raw
                and should_keep_decimal_unit_dot(text[match.end() :])
            ):
                result += "."
        if is_negative:
            result = "минус " + result
        return result

    return DECIMAL_PATTERN.sub(repl, text)
