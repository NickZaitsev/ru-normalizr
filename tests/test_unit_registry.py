import pytest

from ru_normalizr.numerals._constants import (
    CASE_SENSITIVE_UNITS_DATA,
    UNIT_REGISTRY,
    UNITS_DATA,
    resolve_unit_info,
)
from ru_normalizr.numerals.unit_data import PREFIXABLE_UNITS
from ru_normalizr.numerals.unit_registry import UnitDescriptor, UnitRegistry


def _descriptor(lemma: str) -> UnitDescriptor:
    return UnitDescriptor(lemma, "masc", "measure")


def _semantic_target(descriptor: UnitDescriptor) -> tuple[str, str, str | None]:
    return descriptor.lemma, descriptor.category, descriptor.suffix


@pytest.mark.parametrize(
    ("alias", "expected"),
    [*UNITS_DATA.items(), *CASE_SENSITIVE_UNITS_DATA.items()],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_every_declared_alias_remains_reachable(
    alias: str, expected: UnitDescriptor
) -> None:
    resolved = UNIT_REGISTRY.resolve(alias)
    assert resolved is not None
    assert _semantic_target(resolved) == _semantic_target(expected)


@pytest.mark.parametrize(
    ("token", "lemma"),
    [
        ("мПа", "миллипаскаль"),
        ("МПа", "мегапаскаль"),
        ("мН", "миллиньютон"),
        ("МН", "меганьютон"),
        ("мГц", "миллигерц"),
        ("МГц", "мегагерц"),
        ("мкм", "микрометр"),
        ("µm", "микрометр"),
        ("μm", "микрометр"),
        ("um", "микрометр"),
        ("КГ", "килограмм"),
        ("мМ", "миллиметр"),
        ("ММ", "миллиметр"),
    ],
)
def test_generated_exact_symbols_resolve(token: str, lemma: str) -> None:
    descriptor = resolve_unit_info(token)
    assert descriptor is not None
    assert descriptor.lemma == lemma


@pytest.mark.parametrize("token", ["М", "мкМ", "нМ"])
def test_molarity_shorthand_is_never_guessed(token: str) -> None:
    descriptor = resolve_unit_info(token)
    assert descriptor is None or "моль" not in descriptor.lemma


def test_fully_written_molar_concentration_is_supported() -> None:
    descriptor = resolve_unit_info("нмоль/л")
    assert descriptor is not None
    assert (descriptor.lemma, descriptor.suffix) == ("наномоль", "на литр")


def test_single_letter_case_repair_is_rejected_but_canonical_symbol_is_exact() -> None:
    assert UNIT_REGISTRY.resolve("М") is None
    assert UNIT_REGISTRY.resolve("м").lemma == "метр"
    assert UNIT_REGISTRY.resolve("Ф").lemma == "фарад"


def test_ambiguous_fold_group_requires_an_exact_alias() -> None:
    registry = UnitRegistry(
        {"mb": _descriptor("мегабайт")},
        {"Mb": _descriptor("мегабит"), "MB": _descriptor("мегабайт")},
    )
    assert registry.resolve("Mb").lemma == "мегабит"
    assert registry.resolve("MB").lemma == "мегабайт"
    assert registry.resolve("mB") is None


@pytest.mark.parametrize(
    ("token", "lemma"),
    [
        ("kbps", "килобит"),
        ("kBps", "килобайт"),
        ("Mbps", "мегабит"),
        ("MBps", "мегабайт"),
        ("Mb/s", "мегабит"),
        ("MB/s", "мегабайт"),
        ("Gb/s", "гигабит"),
        ("GB/s", "гигабайт"),
    ],
)
def test_bit_and_byte_rate_case_is_semantic(token: str, lemma: str) -> None:
    descriptor = resolve_unit_info(token)
    assert descriptor is not None
    assert descriptor.lemma == lemma


def test_casefold_collision_in_repairable_aliases_is_rejected() -> None:
    with pytest.raises(ValueError, match="collide after casefold"):
        UnitRegistry({"µa": _descriptor("ампер"), "μa": _descriptor("метр")}, {})


def test_exact_alias_cannot_shadow_another_declared_target() -> None:
    with pytest.raises(ValueError, match="unreachable"):
        UnitRegistry({"kb": _descriptor("килобайт")}, {"kb": _descriptor("килобит")})


def test_prefix_generation_is_bounded_and_kilogram_is_not_prefixable() -> None:
    ids = {unit.id for unit in PREFIXABLE_UNITS}
    assert "gram" in ids
    assert "kilogram" not in ids
    assert resolve_unit_info("ккг") is None
