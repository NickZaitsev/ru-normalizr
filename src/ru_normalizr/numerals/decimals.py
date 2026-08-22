from __future__ import annotations

import logging
import re
from functools import lru_cache

import num2words

from .._log_once import warn_once
from .._morph import first_parse_required, parse_word
from ..preprocess_utils import NEGATIVE_NUMBER_PLACEHOLDER
from ..text_context import PUNCT_STRIP, simple_tokenize
from ..text_scan import compile_scan, first_non_whitespace_index
from ._constants import (
    CURRENCY_MINOR_UNITS,
    PREP_CASE,
    UNIT_TOKEN_FRAGMENT,
    resolve_unit_form,
    resolve_unit_info,
)
from ._helpers import (
    get_numeral_case,
    get_target_tags_for_number,
    inanimate_cardinal_case,
    inflect_numeral_string,
    noun_number_form,
    safe_inflect,
    should_keep_decimal_unit_dot_at,
)
from .unit_registry import UnitDescriptor
from .unit_rendering import render_unit_expression

# A bare "-" only reads as a unary minus when nothing word-like precedes it;
# otherwise it is a hyphen joining the number to the previous token ("GLM-5.2").
#
# "range_sep" is the hyphen of a numeric range whose right side is a decimal
# ("10-5.2", "1.5-2.5"). It has to be matched here rather than left behind,
# because a hyphen glued to a rendered numeral is no longer recognisable as a
# range separator: normalize_hyphenated_words treats "10-пять целых…" like
# "10-этажный" and replaces the hyphen with a space. Re-emitting it spaced lets
# detokenize turn it into an em dash, exactly as it already does for "10-20".
DECIMAL_PATTERN = compile_scan(
    rf"(?:(?<=\d)(?P<range_sep>-))?(?<!\d)(?P<num>(?:(?<![^\W_])-|{re.escape(NEGATIVE_NUMBER_PLACEHOLDER)})?\d+[.,]\d+)(?:\s*(?P<unit>{UNIT_TOKEN_FRAGMENT})(?P<unit_dot>\.)?)?(?:\s+(?P<unit2>{UNIT_TOKEN_FRAGMENT})(?P<unit2_dot>\.)?)?(?!\d)"
)

logger = logging.getLogger(__name__)

_MULTIPLIER_LEMMAS = frozenset({"тысяча", "миллион", "миллиард", "триллион"})

# Beyond two digits the fractional part is no longer a subunit count: "1,005 ₽"
# is a thousandth of a rouble, not five kopecks, so it keeps the fraction
# reading.
_MONEY_MINOR_DIGITS = 2


def render_counted_money(
    descriptor: UnitDescriptor, value: int, case: str
) -> str:
    """Render "<numeral> <currency>" with both parts agreeing with the numeral."""
    numeral = inflect_numeral_string(
        str(value), inanimate_cardinal_case(value, case), descriptor.gender, False
    )
    noun = render_unit_expression(
        descriptor,
        get_target_tags_for_number(value, case, descriptor.gender),
        paucal=noun_number_form(value) == "few",
    )
    return f"{numeral} {noun}"


def render_money_amount(
    unit_info: UnitDescriptor, int_part_s: str, frac_part_s: str, case: str
) -> str | None:
    """Read a decimal money amount as major and minor units, or decline to.

    Returns ``None`` whenever the amount is not a currency with a spoken subunit
    or the fractional part cannot be one, leaving the caller's plain
    decimal-fraction reading in place.
    """
    if unit_info.category != "money":
        return None
    minor_info = CURRENCY_MINOR_UNITS.get(unit_info.lemma)
    if minor_info is None or len(frac_part_s) > _MONEY_MINOR_DIGITS:
        return None
    # "100,5 ₽" is fifty kopecks, not five: the fractional part is positional.
    minor_value = int(frac_part_s.ljust(_MONEY_MINOR_DIGITS, "0"))
    major = render_counted_money(unit_info, int(int_part_s), case)
    if minor_value == 0:
        # "100,00 ₽" is plain "сто рублей" — nobody voices "ноль копеек".
        return major
    return f"{major} {render_counted_money(minor_info, minor_value, case)}"


def _render_half_multiplier(
    unit_info: UnitDescriptor, int_val: int, int_part_s: str, case: str
) -> str | None:
    """«N,5 тысяч» — «N с половиной тысяч», «1,5 млн» — «полтора миллиона».

    Возвращает ``None``, когда конструкция не читается «с половиной»
    (например, целая часть оканчивается на 1: «21,5 тысячи» остаётся
    десятичной дробью).
    """
    gender = "femn" if unit_info.lemma == "тысяча" else "masc"
    if int_val == 1:
        if case in {"nomn", "accs"}:
            numeral = "полторы" if gender == "femn" else "полтора"
            noun = render_unit_expression(unit_info, {"gent", "sing"})
        else:
            numeral = "полутора"
            noun = render_unit_expression(unit_info, {case, "plur"})
        return f"{numeral} {noun}"
    if int_val % 10 == 1 and int_val % 100 != 11:
        return None
    # Винительный совпадает с именительным у всего, что не оканчивается на 1:
    # «собрали два с половиной триллиона», а не «двух». Спрашивать у морфологии
    # accs здесь опасно ровно так же, как в целом числительном рядом.
    numeral = inflect_numeral_string(
        int_part_s, inanimate_cardinal_case(int_val, case), gender, False
    )
    if not numeral:
        return None
    noun = render_unit_expression(
        unit_info,
        get_target_tags_for_number(int_val, case, gender),
        paucal=noun_number_form(int_val) == "few",
    )
    return f"{numeral} с половиной {noun}"


@lru_cache(maxsize=32)
def _fraction_order_base(digits: int) -> str:
    try:
        return num2words.num2words(10**digits, lang="ru", to="ordinal")
    except Exception as exc:
        warn_once(
            logger,
            f"num2words-order:{digits}",
            "num2words failed for 10**%d ordinal: %s",
            digits,
            exc,
        )
        return {
            1: "десятая",
            2: "сотая",
            3: "тысячная",
            4: "десятитысячная",
            5: "стотысячная",
            6: "миллионная",
        }.get(digits, "десятитысячная")


def normalize_decimals(text: str) -> str:
    def inflect_fraction_numerator(num_str: str, case: str) -> str:
        try:
            value = int(num_str)
        except ValueError:
            return num_str
        # Числитель дроби считает неодушевлённые доли, поэтому одушевлённый
        # винительный («трёх десятых») здесь появиться не может.
        case = inanimate_cardinal_case(value, case)
        words = inflect_numeral_string(num_str, case)
        if value == 0:
            return words
        last_word = words.split()[-1]
        parsed_last = parse_word(last_word)
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
        base = _fraction_order_base(digits)
        parsed = parse_word(base)
        if not parsed:
            return base
        tags = (
            {case, "femn", "sing"}
            if frac_val % 10 == 1 and frac_val % 100 != 11
            else ({"gent", "plur"} if case in ["nomn", "accs"] else {case, "plur"})
        )
        return safe_inflect(parsed[0], tags, fallback_word=base)

    def is_ambiguous_preposition_token(token: str) -> bool:
        clean = token.lower().strip(PUNCT_STRIP)
        return bool(clean) and " " not in clean and clean in PREP_CASE

    def should_skip_unit_candidate(unit_raw: str, source_text: str, start: int) -> bool:
        if not is_ambiguous_preposition_token(unit_raw):
            return False
        next_index, _ = first_non_whitespace_index(source_text, start)
        if next_index >= len(source_text):
            return False
        next_char = source_text[next_index]
        return bool(re.match(r"[^\W_]", next_char, re.UNICODE))

    def should_skip_combined_unit_candidate(unit_parts: list[str]) -> bool:
        cleaned_parts = [part.strip(PUNCT_STRIP) for part in unit_parts]
        return any(
            cleaned and is_ambiguous_preposition_token(cleaned)
            for cleaned in cleaned_parts[1:]
        )

    def repl(match: re.Match[str]) -> str:
        s = match.group("num").replace(",", ".")
        unit_raw = match.group("unit")
        unit2_raw = match.group("unit2")
        start_pos = match.start()
        context = text[max(0, start_pos - 40) : start_pos]
        tokens_left = simple_tokenize(context)
        context_tokens = [*tokens_left, s]
        # Include the written unit in the bounded context.  This lets the
        # numeral-case resolver distinguish a governed decimal quantity
        # ("на частоте 3,2 ГГц") from a bare predicate after a dative noun
        # ("Директору 45").
        if unit_raw:
            context_tokens.append(unit_raw)
        case = get_numeral_case(context_tokens, len(tokens_left))
        is_negative = s.startswith("-") or s.startswith(NEGATIVE_NUMBER_PLACEHOLDER)
        abs_s = s.lstrip(f"-{NEGATIVE_NUMBER_PLACEHOLDER}")
        parts = abs_s.split(".")
        if len(parts) != 2:
            return match.group(0)
        int_part_s, frac_part_s = parts
        int_val = int(int_part_s)
        frac_val = int(frac_part_s)
        digits = len(frac_part_s)
        render_case = case
        if int_val == 0:
            # The zero in a decimal quantity is conventionally invariant in
            # Russian speech: "при дозе ноль целых пять десятых миллилитра".
            render_case = "nomn"
        # Десятичное количество всегда неодушевлённое: «две целых», не «двух».
        int_words = inflect_numeral_string(
            int_part_s, inanimate_cardinal_case(int_val, render_case), gender="femn"
        )
        p_cel = first_parse_required("целая")
        tags_cel = (
            {render_case, "femn", "sing"}
            if int_val % 10 == 1 and int_val % 100 != 11
            else (
                {"gent", "plur"}
                if render_case in ["nomn", "accs"]
                else {render_case, "plur"}
            )
        )
        cel_words = safe_inflect(p_cel, tags_cel)
        frac_words = inflect_fraction_numerator(frac_part_s, render_case)
        order_words = render_fraction_order_words(digits, frac_val, render_case)
        result = f"{int_words} {cel_words} {frac_words} {order_words}"
        if unit_raw:
            unit_dot = match.group("unit_dot")
            unit2_dot = match.group("unit2_dot")
            unit_info = None
            unit_consumes_second_token = False
            if unit2_raw and not should_skip_combined_unit_candidate([unit_raw, unit2_raw]):
                combined_candidates = []
                if unit_dot:
                    combined_candidates.append(f"{unit_raw}.{unit2_raw}")
                combined_candidates.append(f"{unit_raw}{unit2_raw}")
                for candidate_raw in combined_candidates:
                    unit_info = resolve_unit_info(candidate_raw)
                    if unit_info:
                        unit_consumes_second_token = True
                        break
            unit_tail_start = match.end("unit")
            if unit_info is None and not should_skip_unit_candidate(
                unit_raw, text, unit_tail_start
            ):
                unit_info = resolve_unit_info(unit_raw)
                if unit_info is None:
                    resolved_form = resolve_unit_form(unit_raw)
                    if resolved_form is not None and (
                        resolved_form.morphology.paradigm
                        or resolved_form.morphology.indeclinable
                        or resolved_form.category == "money"
                    ):
                        unit_info = resolved_form
            unit2_processed = False

            def trailing_unit_dot() -> str:
                # The pattern happily takes the first word of the next sentence
                # as "unit2", so an abbreviation dot that ends a sentence sits in
                # the middle of the match and the tail check below never sees it.
                # Without this the two sentences merge: "Цена 3,50 руб. Доставка
                # бесплатна." -> "...пятьдесят копеек Доставка бесплатна."
                if not unit_dot or not unit2_raw:
                    return ""
                keep = should_keep_decimal_unit_dot_at(text, match.start("unit2"))
                return "." if keep else ""

            if unit_info:
                lemma = unit_info.lemma
                half_words = (
                    _render_half_multiplier(
                        unit_info, int_val, int_part_s, render_case
                    )
                    if lemma in _MULTIPLIER_LEMMAS
                    and frac_part_s == "5"
                    and int_val
                    and not is_negative
                    else None
                )
                if half_words is not None:
                    # «11,5 тысяч» — «одиннадцать с половиной тысяч», слово
                    # величины уже согласовано внутри.
                    result = half_words
                else:
                    money_words = (
                        None
                        if unit_consumes_second_token
                        else render_money_amount(
                            unit_info, int_part_s, frac_part_s, case
                        )
                    )
                    if money_words is not None:
                        result = money_words
                    else:
                        result += " " + render_unit_expression(
                            unit_info, {"gent", "sing"}
                        )
                if unit_consumes_second_token:
                    unit2_processed = True
                elif unit2_raw:
                    unit2_info = resolve_unit_info(unit2_raw)
                    if lemma in _MULTIPLIER_LEMMAS and unit2_info:
                        lemma2 = unit2_info.lemma
                        if lemma2 == "человек":
                            result += " человек"
                        else:
                            result += " " + render_unit_expression(
                                unit2_info, {"gent", "plur"}
                            )
                        unit2_processed = True
                if unit2_raw and not unit2_processed:
                    result += trailing_unit_dot() + " " + unit2_raw
            else:
                result += " " + unit_raw
                if unit2_raw:
                    result += trailing_unit_dot() + " " + unit2_raw
            if (
                unit2_dot
                and unit2_raw
                and should_keep_decimal_unit_dot_at(text, match.end())
            ) or (
                unit_dot
                and not unit2_raw
                and should_keep_decimal_unit_dot_at(text, match.end())
            ):
                result += "."
        if is_negative:
            result = "минус " + result
        if match.group("range_sep"):
            # Spaced, not glued: detokenize converts " - " between two words
            # into an em dash, which is how integer ranges already render.
            result = " - " + result
        return result

    return DECIMAL_PATTERN.sub(repl, text)
