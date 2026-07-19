from __future__ import annotations

import logging
import re

import num2words

from .._morph import first_parse
from ._constants import FRACTION_PATTERN

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
        try:
            num_text = num2words.num2words(num, lang="ru")
        except Exception as exc:
            logger.debug("num2words failed for numerator %r: %s", num, exc)
            return match.group(0)
        if case != "nomn":
            num_text = " ".join(
                (p.inflect({case}).word if p.inflect({case}) else part)
                for part in num_text.split()
                for p in [first_parse(part)]
            )
        last_num_word = num_text.split()[-1]
        p_last = first_parse(last_num_word)
        if num % 10 == 1 and num % 100 != 11:
            inf = p_last.inflect({case, "femn", "sing"})
            if inf:
                arr = num_text.split()
                arr[-1] = inf.word
                num_text = " ".join(arr)
        elif num % 10 == 2 and num % 100 != 12 and case in ["nomn", "accs"]:
            inf = p_last.inflect({case, "femn"})
            if inf:
                arr = num_text.split()
                arr[-1] = inf.word
                num_text = " ".join(arr)
        try:
            denom_text = num2words.num2words(denom, lang="ru", to="ordinal")
        except Exception as exc:
            logger.debug("num2words failed for denominator %r: %s", denom, exc)
            return match.group(0)
        words = denom_text.split()
        p = first_parse(words[-1])
        is_sing_1 = num % 10 == 1 and num % 100 != 11
        inflected = p.inflect(
            {case, "femn", "sing"}
            if is_sing_1
            else ({"gent", "plur"} if case in ["nomn", "accs"] else {case, "plur"})
        )
        if inflected:
            words[-1] = inflected.word
        return f"{num_text} {' '.join(words)}"

    return FRACTION_PATTERN.sub(repl, text)
