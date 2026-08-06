from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class UnitMorphology:
    expected_normal_form: str | None = None
    animacy: str | None = "inan"
    indeclinable: bool = False
    preferred_grammemes: frozenset[str] = frozenset()
    forbidden_grammemes: frozenset[str] = frozenset()
    morphology_seed: str | None = None
    paradigm: tuple[tuple[str, str, str], ...] = ()
    plural_only: bool = False
    byte_family: bool = False

    def form(self, case: str, number: str) -> str | None:
        return next(
            (
                word
                for form_case, form_number, word in self.paradigm
                if form_case == case and form_number == number
            ),
            None,
        )


@dataclass(frozen=True)
class UnitDescriptor:
    lemma: str
    gender: str
    category: str
    suffix: str | None = None
    morphology: UnitMorphology = UnitMorphology()

    def __iter__(self) -> Iterator[str]:
        yield self.lemma
        yield self.gender
        yield self.category
        if self.suffix is not None:
            yield self.suffix

    def __getitem__(self, index: int) -> str:
        return tuple(self)[index]


@dataclass(frozen=True)
class UnitAlias:
    text: str
    kind: Literal["word", "symbol"] = "symbol"
    allow_case_repair: bool = True


@dataclass(frozen=True)
class PrefixDefinition:
    id: str
    spoken: str
    exponent: int
    latin: str | None = None
    cyrillic: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnitDefinition:
    id: str
    descriptor: UnitDescriptor
    aliases: tuple[UnitAlias, ...]


@dataclass(frozen=True)
class UnitMatch:
    descriptor: UnitDescriptor
    source: str
    alias: str
    consumed_tokens: int = 1
    expression: object | None = None


def _semantic_key(descriptor: UnitDescriptor) -> tuple[object, ...]:
    return (
        descriptor.lemma,
        descriptor.gender,
        descriptor.category,
        descriptor.suffix,
    )


def _strip_supported_terminal_dot(token: str) -> str:
    # Until punctuation ownership moves into UnitMatch, preserve the legacy
    # behaviour for sentence ellipses as well as a single abbreviation dot.
    return token.rstrip(".")


class UnitRegistry:
    """Validated unit lookup with ambiguity-aware case repair.

    Legacy folded aliases remain useful for words and damaged typography, but
    a folded lookup is accepted only when every spelling in that fold group has
    the same semantic target. Exact aliases always win.
    """

    def __init__(
        self,
        folded_aliases: Mapping[str, UnitDescriptor],
        exact_aliases: Mapping[str, UnitDescriptor],
    ) -> None:
        self._folded = dict(folded_aliases)
        self._exact = dict(exact_aliases)
        self._validate_aliases()

        folded_index: dict[str, UnitDescriptor] = {}
        for alias, descriptor in self._folded.items():
            folded_key = _strip_supported_terminal_dot(alias).casefold()
            previous = folded_index.get(folded_key)
            if previous is not None and _semantic_key(previous) != _semantic_key(descriptor):
                raise ValueError(f"Case-repairable unit aliases collide after casefold: {alias!r}")
            folded_index[folded_key] = descriptor
        self._folded_index = folded_index

        groups: dict[str, set[tuple[object, ...]]] = defaultdict(set)
        for alias, descriptor in (*self._folded.items(), *self._exact.items()):
            groups[_strip_supported_terminal_dot(alias).casefold()].add(_semantic_key(descriptor))
        self._folded_semantics = {
            alias: frozenset(semantics) for alias, semantics in groups.items()
        }

    def _validate_aliases(self) -> None:
        if any(not alias.strip() for alias in self._folded):
            raise ValueError("Case-repairable unit alias cannot be empty")
        for alias, descriptor in self._exact.items():
            if not alias.strip():
                raise ValueError("Exact unit alias cannot be empty")
            if not descriptor.lemma or not descriptor.category:
                raise ValueError(f"Incomplete unit descriptor for {alias!r}")
        for alias in self._folded.keys() & self._exact.keys():
            if _semantic_key(self._folded[alias]) != _semantic_key(
                self._exact[alias]
            ):
                raise ValueError(
                    f"Folded unit alias {alias!r} is unreachable because an exact "
                    "alias with another semantic target shadows it"
                )

    @staticmethod
    def _is_single_letter_symbol(token: str) -> bool:
        return len(token) == 1 and token.isalpha()

    def resolve(self, token: str) -> UnitDescriptor | None:
        original = token.strip()
        if not original:
            return None

        exact = self._exact.get(original)
        if exact is not None:
            return exact

        cleaned = _strip_supported_terminal_dot(original)
        if cleaned != original:
            exact = self._exact.get(cleaned)
            if exact is not None:
                return exact

        # A spelling declared in the legacy folded table is canonical, not a
        # case-repair attempt. This matters for dotted aliases such as "в.",
        # whose dotless fold group also contains the exact volt symbol "В".
        declared = self._folded.get(original)
        if declared is None and cleaned != original:
            declared = self._folded.get(cleaned)
        if declared is not None:
            return declared

        folded_key = cleaned.casefold()
        descriptor = self._folded_index.get(folded_key)
        if descriptor is None:
            return None

        # The canonical lowercase single-letter alias itself remains valid, but
        # uppercase damage is too ambiguous to repair (notably "М").
        if self._is_single_letter_symbol(cleaned) and cleaned != folded_key:
            return None

        semantics = self._folded_semantics.get(folded_key, frozenset())
        if len(semantics) != 1:
            return None
        return descriptor

    def is_unit_token(self, token: str) -> bool:
        return self.resolve(token) is not None

    def is_exact_symbol(self, token: str) -> bool:
        return _strip_supported_terminal_dot(token.strip()) in self._exact

    def is_non_year_unit(self, token: str) -> bool:
        return self.resolve(token) is not None

    def entity_category(self, token: str) -> str | None:
        descriptor = self.resolve(token)
        return descriptor.category if descriptor is not None else None

    def folded_groups(self) -> Mapping[str, frozenset[tuple[object, ...]]]:
        return self._folded_semantics
