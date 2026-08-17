from __future__ import annotations

from ._helpers import inflect_unit_lemma
from .unit_registry import UnitDescriptor, UnitMatch


def render_unit_expression(
    unit: UnitDescriptor | UnitMatch,
    target_tags: set[str],
    *,
    paucal: bool = False,
) -> str:
    """Render an atomic or registered bounded expression through one contract.

    ``paucal`` is forwarded to :func:`inflect_unit_lemma`: it tells a two-word
    unit that a numeral ending in 2–4 counts it.
    """
    descriptor = unit.descriptor if isinstance(unit, UnitMatch) else unit
    rendered = inflect_unit_lemma(descriptor, target_tags, paucal=paucal)
    if descriptor.suffix:
        rendered += f" {descriptor.suffix}"
    return rendered
