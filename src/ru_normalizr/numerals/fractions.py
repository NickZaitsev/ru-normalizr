from __future__ import annotations

import logging
import re

import num2words

from .._morph import canonicalize_case, first_parse_required, select_parse
from ._constants import FRACTION_PATTERN
from ._helpers import inflect_numeral_string, safe_inflect

logger = logging.getLogger(__name__)

GENITIVE_FRACTION_CONTEXT_PATTERN = re.compile(r"\b(с|со|от|до|из|без|у)\s+$")
DATIVE_FRACTION_CONTEXT_PATTERN = re.compile(r"\b(к|по)\s+$")
ACCUSATIVE_FRACTION_CONTEXT_PATTERN = re.compile(r"\b(в|на|через)\s+$")
PREPOSITIONAL_FRACTION_CONTEXT_PATTERN = re.compile(r"\b(о|об|при)\s+$")


def normalize_fractions(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        num = int(match.group(1))
        denom = int(match.group(2))
        context = text[max(0, match.start() - 10) : match.start()].lower()
        case = "nomn"
        if GENITIVE_FRACTION_CONTEXT_PATTERN.search(context):
            case = "gent"
        elif DATIVE_FRACTION_CONTEXT_PATTERN.search(context):
            case = "datv"
        elif ACCUSATIVE_FRACTION_CONTEXT_PATTERN.search(context):
            case = "accs"
        elif PREPOSITIONAL_FRACTION_CONTEXT_PATTERN.search(context):
            case = "loct"
        case = canonicalize_case(case)
        numerator_gender = (
            "femn"
            if num % 10 in {1, 2} and num % 100 not in {11, 12}
            else None
        )
        num_text = inflect_numeral_string(
            str(num), case, numerator_gender, animate=False
        )
        if not num_text:
            return match.group(0)
        if numerator_gender is not None:
            words = num_text.split()
            selected = select_parse(words[-1], pos={"NUMR", "ADJF"}, preferred_grammemes={"Anum"})
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
            logger.debug("num2words failed for denominator %r: %s", denom, exc)
            return match.group(0)
        words = denom_text.split()
        p = first_parse_required(words[-1])
        is_sing_1 = num % 10 == 1 and num % 100 != 11
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

    return FRACTION_PATTERN.sub(repl, text)
