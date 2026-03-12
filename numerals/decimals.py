from __future__ import annotations

import re

from .._morph import get_morph
from ..preprocess_utils import NEGATIVE_NUMBER_PLACEHOLDER
from ._constants import UNITS_DATA
from ._helpers import (
    get_numeral_case,
    inflect_numeral_string,
    safe_inflect,
    should_keep_decimal_unit_dot,
    simple_tokenize,
)

DECIMAL_PATTERN = re.compile(
    rf"(?<!\d)(?P<num>(?:-|{re.escape(NEGATIVE_NUMBER_PLACEHOLDER)})?\d+[.,]\d+)(?:\s*(?P<unit>[а-яА-ЯёЁa-zA-Z%°$€₽Ω]+)(?P<unit_dot>\.)?)?(?:\s+(?P<unit2>[а-яА-ЯёЁa-zA-Z%°$€₽Ω]+)(?P<unit2_dot>\.)?)?(?!\d)"
)


def normalize_decimals(text: str) -> str:
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
        order_names = {
            1: "десятая",
            2: "сотая",
            3: "тысячная",
            4: "десятитысячная",
            5: "стотысячная",
            6: "миллионная",
        }
        order_name_base = order_names.get(digits, "десятитысячная")
        morph = get_morph()
        int_words = inflect_numeral_string(int_part_s, case, gender="femn")
        p_cel = morph.parse("целая")[0]
        tags_cel = (
            {case, "femn", "sing"}
            if int_val % 10 == 1 and int_val % 100 != 11
            else ({"gent", "plur"} if case in ["nomn", "accs"] else {case, "plur"})
        )
        cel_words = safe_inflect(p_cel, tags_cel)
        frac_words = inflect_numeral_string(frac_part_s, case, gender="femn")
        p_order = morph.parse(order_name_base)[0]
        tags_order = (
            {case, "femn", "sing"}
            if frac_val % 10 == 1 and frac_val % 100 != 11
            else ({"gent", "plur"} if case in ["nomn", "accs"] else {case, "plur"})
        )
        order_words = safe_inflect(p_order, tags_order)
        result = f"{int_words} {cel_words} {frac_words} {order_words}"
        if unit_raw:
            unit_dot = match.group("unit_dot")
            unit_lower = unit_raw.lower().strip(".")
            unit_info = UNITS_DATA.get(unit_lower)
            unit2_raw = match.group("unit2")
            unit2_dot = match.group("unit2_dot")
            unit2_processed = False
            if unit_info:
                lemma, _, _, *u_suffix = unit_info
                p_unit = morph.parse(lemma)[0]
                result += " " + safe_inflect(p_unit, {"gent", "sing"})
                if u_suffix:
                    result += " " + u_suffix[0]
                if unit2_raw:
                    unit2_lower = unit2_raw.lower().strip(".")
                    unit2_info = UNITS_DATA.get(unit2_lower)
                    multipliers = {"тысяча", "миллион", "миллиард", "триллион"}
                    if lemma in multipliers and unit2_info:
                        lemma2, _, _, *suffix2 = unit2_info
                        p_unit2 = morph.parse(lemma2)[0]
                        result += " " + safe_inflect(p_unit2, {"gent", "plur"})
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
