from __future__ import annotations

import re

from ..preprocess_utils import NEGATIVE_NUMBER_PLACEHOLDER
from ._constants import resolve_unit_info
from ._helpers import inflect_numeral_string

VERSION_SEPARATOR_WORD = "точка"

# A dotted numeric sequence is a version rather than a decimal fraction when
# either it carries more components than a fraction can have ("3.12.1"), or it
# is glued by a hyphen to a name ("GLM-5.2", "Ту-154.2"). Both signals are
# structural, so no list of product names is involved.
VERSION_PATTERN = re.compile(
    rf"(?<![\w.,{re.escape(NEGATIVE_NUMBER_PLACEHOLDER)}])"
    r"(?:(?P<name>[^\W\d_]\w*)-)?"
    r"(?P<version>\d+(?:\.\d+)+)"
    r"(?!\w)",
    re.UNICODE,
)
_TRAILING_UNIT_PATTERN = re.compile(r"\s*(?P<unit>[^\W\d_]+)\.?(?!\w)", re.UNICODE)


def _render_component(component: str) -> str:
    """Read one version component, keeping its leading zeros audible."""
    stripped = component.lstrip("0")
    words = ["ноль"] * (len(component) - len(stripped))
    if stripped:
        words.append(inflect_numeral_string(stripped, "nomn"))
    return " ".join(words)


def _is_followed_by_unit(text: str, start: int) -> bool:
    match = _TRAILING_UNIT_PATTERN.match(text, start)
    return bool(match) and resolve_unit_info(match.group("unit")) is not None


def normalize_versions(text: str) -> str:
    """Read version and model numbers component by component.

    Runs before :func:`normalize_decimals`, which would otherwise claim the
    first two components as a fraction and leave the rest as literal text.
    """

    def repl(match: re.Match[str]) -> str:
        name = match.group("name")
        components = match.group("version").split(".")
        # Two components are a fraction unless a name claims them, and even
        # then a following unit means it really is a measurement ("X-1.5 кг").
        if len(components) < 3 and (
            not name or _is_followed_by_unit(text, match.end())
        ):
            return match.group(0)
        spoken = f" {VERSION_SEPARATOR_WORD} ".join(
            _render_component(component) for component in components
        )
        return f"{name} {spoken}" if name else spoken

    return VERSION_PATTERN.sub(repl, text)
