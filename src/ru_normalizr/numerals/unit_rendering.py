from __future__ import annotations

from ._helpers import inflect_unit_lemma
from .unit_registry import UnitDescriptor, UnitMatch


def render_unit_expression(
    unit: UnitDescriptor | UnitMatch,
    target_tags: set[str],
) -> str:
    """Render an atomic or registered bounded expression through one contract."""
    descriptor = unit.descriptor if isinstance(unit, UnitMatch) else unit
    rendered = inflect_unit_lemma(descriptor, target_tags)
    if descriptor.suffix:
        rendered += f" {descriptor.suffix}"
    return rendered
