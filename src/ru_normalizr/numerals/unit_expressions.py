from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from ._constants import UNIT_REGISTRY
from .unit_registry import UnitMatch

MAX_UNIT_TOKENS = 4
_SEPARATOR_SPACING = re.compile(r"\s*([/·])\s*")


@dataclass(frozen=True)
class UnitExpression:
    kind: Literal["atomic", "power", "division", "product"]
    source: str


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
