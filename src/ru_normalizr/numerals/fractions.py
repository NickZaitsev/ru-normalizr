from __future__ import annotations

import logging
import re

import num2words

from .._log_once import warn_once
from .._morph import canonicalize_case, first_parse_required, select_parse
from ..text_context import simple_tokenize
from ..text_scan import compile_scan
from ._constants import (
    FRACTION_PATTERN,
    UNIT_TOKEN_FRAGMENT,
    resolve_unit_form,
    resolve_unit_info,
)
from ._helpers import get_numeral_case, inflect_numeral_string, safe_inflect
from .unit_rendering import render_unit_expression

logger = logging.getLogger(__name__)

GENITIVE_FRACTION_CONTEXT_PATTERN = compile_scan(r"\b(с|со|от|до|из|без|у)\s+$")
DATIVE_FRACTION_CONTEXT_PATTERN = compile_scan(r"\b(к|по)\s+$")
ACCUSATIVE_FRACTION_CONTEXT_PATTERN = compile_scan(r"\b(в|на|через)\s+$")
PREPOSITIONAL_FRACTION_CONTEXT_PATTERN = compile_scan(r"\b(о|об|при)\s+$")
FRACTION_UNIT_PATTERN = compile_scan(
    rf"(?<![\d,])(?P<num>\d+)/(?P<denom>\d+)(?P<space>\s+)"
    rf"(?P<unit>{UNIT_TOKEN_FRAGMENT})(?!\w)"
)
FRACTION_COMPOUND_UNIT_PATTERN = compile_scan(
    r"(?<![\d,])(?P<num>\d+)/(?P<denom>\d+)(?P<space>\s+)"
    r"(?P<unit>ч\.\s*л\.)(?!\w)",
    re.IGNORECASE,
)
PRESSURE_RATIO_PATTERN = compile_scan(
    r"(?<!\w)(?:(?P<prep>с|со|до)\s+)?"
    r"(?P<left>\d{2,3})\s*/\s*(?P<right>\d{2,3})",
    re.IGNORECASE,
)


def normalize_fractions(text: str) -> str:
    def pressure_ratio_repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 80) : match.start()]
        if not re.search(r"\bдавлен\w*", left_context, re.IGNORECASE):
            return match.group(0)
        prep = match.group("prep")
        rendered_prep = "со" if prep and prep.casefold() == "с" else prep
        prefix = f"{rendered_prep} " if rendered_prep else ""
        return f"{prefix}{match.group('left')} на {match.group('right')}"

    text = PRESSURE_RATIO_PATTERN.sub(pressure_ratio_repl, text)

    def fraction_case(start: int) -> str:
        context = text[max(0, start - 10) : start].lower()
        case = "nomn"
        if GENITIVE_FRACTION_CONTEXT_PATTERN.search(context):
            case = "gent"
        elif DATIVE_FRACTION_CONTEXT_PATTERN.search(context):
            case = "datv"
        elif ACCUSATIVE_FRACTION_CONTEXT_PATTERN.search(context):
            case = "accs"
        elif PREPOSITIONAL_FRACTION_CONTEXT_PATTERN.search(context):
            case = "loct"
        else:
            context_tokens = simple_tokenize(text[max(0, start - 40) : start] + " 0")
            if context_tokens:
                governed_case = get_numeral_case(
                    context_tokens, len(context_tokens) - 1
                )
                if governed_case != "nomn":
                    case = governed_case
        return canonicalize_case(case)

    def render_fraction(num: int, denom: int, case: str) -> str | None:
        numerator_gender = (
            "femn"
            if num % 10 in {1, 2} and num % 100 not in {11, 12}
            else None
        )
        num_text = inflect_numeral_string(
            str(num), case, numerator_gender, animate=False
        )
        if not num_text:
            return None
        if numerator_gender is not None:
            words = num_text.split()
            selected = select_parse(
                words[-1], pos={"NUMR", "ADJF"}, preferred_grammemes={"Anum"}
            )
            if selected is not None:
                target_tags = {case, numerator_gender}
                if num % 10 == 1:
                    target_tags.add("sing")
                words[-1] = safe_inflect(
                    selected,
                    target_tags,
                    fallback_word=words[-1],
                )
                num_text = " ".join(words)
        try:
            denom_text = num2words.num2words(denom, lang="ru", to="ordinal")
        except Exception as exc:
            warn_once(
                logger,
                f"num2words-denominator:{denom}",
                "num2words failed for denominator %r: %s",
                denom,
                exc,
            )
            return None
        words = denom_text.split()
        if len(words) > 1:
            first_denominator_word = first_parse_required(words[0])
            if first_denominator_word.tag.POS == "NUMR":
                inflected_first = first_denominator_word.inflect({"gent"})
                if inflected_first is not None:
                    words[0] = inflected_first.word
        is_sing_1 = num % 10 == 1 and num % 100 != 11
        if denom == 3 and case in {"nomn", "accs"}:
            # In the nominative/accusative Russian uses the noun fraction
            # "треть": "две трети". Oblique cases retain the adjectival
            # paradigm already used by the public fraction contract.
            return f"{num_text} {'треть' if is_sing_1 else 'трети'}"
        p = first_parse_required(words[-1])
        magnitude_numerator = num >= 1000 and num % 1000 == 0
        inflected = p.inflect(
            {case, "femn", "sing"}
            if is_sing_1
            else (
                {"gent", "plur"}
                if case in ["nomn", "accs"] or magnitude_numerator
                else {case, "plur"}
            )
        )
        if inflected:
            words[-1] = inflected.word
        return f"{num_text} {' '.join(words)}"

    def with_unit_repl(match: re.Match[str]) -> str:
        unit_raw = match.group("unit")
        unit_info = resolve_unit_info(unit_raw) or resolve_unit_form(unit_raw)
        if unit_info is None:
            return match.group(0)
        rendered_fraction = render_fraction(
            int(match.group("num")),
            int(match.group("denom")),
            fraction_case(match.start()),
        )
        if rendered_fraction is None:
            return match.group(0)
        return (
            f"{rendered_fraction} "
            f"{render_unit_expression(unit_info, {'gent', 'sing', unit_info.gender})}"
        )

    def with_compound_unit_repl(match: re.Match[str]) -> str:
        unit_raw = match.group("unit").replace(" ", "")
        unit_info = resolve_unit_info(unit_raw)
        if unit_info is None:
            return match.group(0)
        rendered_fraction = render_fraction(
            int(match.group("num")),
            int(match.group("denom")),
            fraction_case(match.start()),
        )
        if rendered_fraction is None:
            return match.group(0)
        return (
            f"{rendered_fraction} "
            f"{render_unit_expression(unit_info, {'gent', 'sing', unit_info.gender})}"
        )

    normalized = FRACTION_COMPOUND_UNIT_PATTERN.sub(
        with_compound_unit_repl, text
    )
    normalized = FRACTION_UNIT_PATTERN.sub(with_unit_repl, normalized)

    def repl(match: re.Match[str]) -> str:
        rendered = render_fraction(
            int(match.group(1)), int(match.group(2)), fraction_case(match.start())
        )
        return rendered if rendered is not None else match.group(0)

    return FRACTION_PATTERN.sub(repl, normalized)
