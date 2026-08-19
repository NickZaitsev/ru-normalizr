from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from .._morph import select_parse
from ..text_scan import compile_scan
from ._constants import UNIT_REGISTRY
from .unit_registry import UnitMatch

MAX_UNIT_TOKENS = 4
_SEPARATOR_SPACING = compile_scan(r"\s*([/·])\s*")

#: «кв.»/«куб.» после числа перед полным словом-существительным — сокращённое
#: прилагательное площади или объёма, а не киловольты: «15 000 кв. миль» —
#: «15 000 квадратных миль». Сокращённые единицы («кв. км») раскрывает реестр
#: составных алиасов, сюда попадают только полные слова.
SQUARE_UNIT_ATTRIBUTE_PATTERN = compile_scan(
    r"(?<=\d)(?P<space>\s+)(?P<abbr>кв|куб)\.\s*(?P<noun>[а-яё]{3,})(?!\w)"
)
_SQUARE_UNIT_ADJECTIVES = {"кв": "квадратный", "куб": "кубический"}


def normalize_square_unit_attributes(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        noun = match.group("noun")
        parsed = select_parse(noun, pos="NOUN")
        if parsed is None or "inan" not in parsed.tag:
            return match.group(0)
        case = parsed.tag.case
        number = parsed.tag.number
        if case is None or number is None:
            return match.group(0)
        adjective = select_parse(
            _SQUARE_UNIT_ADJECTIVES[match.group("abbr").casefold()], pos="ADJF"
        )
        if adjective is None:
            return match.group(0)
        tags = {case, number}
        if number == "sing":
            if parsed.tag.gender is None:
                return match.group(0)
            tags.add(parsed.tag.gender)
        inflected = adjective.inflect(frozenset(tags))
        if inflected is None:
            return match.group(0)
        return f"{match.group('space')}{inflected.word} {noun}"

    if "кв" not in text and "куб" not in text:
        return text
    return SQUARE_UNIT_ATTRIBUTE_PATTERN.sub(repl, text)


@dataclass(frozen=True)
class UnitExpression:
    kind: Literal["atomic", "power", "division", "product"]
    source: str


@lru_cache(maxsize=16384)
def resolve_unit_expression(raw: str) -> UnitMatch | None:
    normalized = _SEPARATOR_SPACING.sub(r"\1", raw.strip())
    descriptor = UNIT_REGISTRY.resolve(normalized)
    if descriptor is None:
        return None
    if "/" in normalized:
        kind = "division"
    elif "·" in normalized:
        kind = "product"
    elif normalized.endswith(("²", "³", "^2", "^3")):
        kind = "power"
    else:
        kind = "atomic"
    return UnitMatch(
        descriptor=descriptor,
        source=raw,
        alias=normalized,
        expression=UnitExpression(kind, normalized),
    )


def match_unit_tokens(tokens: Sequence[str], start: int) -> UnitMatch | None:
    best: UnitMatch | None = None
    max_end = min(len(tokens), start + MAX_UNIT_TOKENS)
    for end in range(start + 1, max_end + 1):
        chunk = tokens[start:end]
        if any("\n" in token for token in chunk):
            break
        candidate = "".join(chunk)
        match = resolve_unit_expression(candidate)
        if match is not None:
            best = UnitMatch(
                descriptor=match.descriptor,
                source=candidate,
                alias=match.alias,
                consumed_tokens=end - start,
                expression=match.expression,
            )
    return best
