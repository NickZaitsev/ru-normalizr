from __future__ import annotations

import functools
from collections.abc import Iterable, Sequence
from typing import Any, Protocol, cast

import pymorphy3


class MorphParse(Protocol):
    """Typed surface used from pymorphy3 parse results."""

    word: str
    normal_form: str
    tag: Any
    score: float
    lexeme: Sequence[MorphParse]

    def inflect(
        self, grammemes: set[str] | frozenset[str]
    ) -> MorphParse | None: ...


@functools.lru_cache(maxsize=1)
def get_morph() -> pymorphy3.MorphAnalyzer:
    return pymorphy3.MorphAnalyzer()


@functools.lru_cache(maxsize=65536)
def _parse_word_lower(word: str) -> tuple[MorphParse, ...]:
    return cast(tuple[MorphParse, ...], tuple(get_morph().parse(word)))


def parse_word(word: str) -> tuple[MorphParse, ...]:
    """Parse a word once using a lowercase cache key.

    pymorphy3 lowercases internally, so preserving case in the cache only
    duplicates equivalent entries.  ``е`` and ``ё`` remain distinct.
    """
    return _parse_word_lower(word.lower())


@functools.lru_cache(maxsize=4096)
def _canonicalize_grammemes_cached(grammemes: frozenset[str]) -> frozenset[str]:
    return frozenset(get_morph().TagClass.fix_rare_cases(set(grammemes)))


def canonicalize_grammemes(grammemes: Iterable[str]) -> frozenset[str]:
    """Convert pymorphy's rare cases through its authoritative tag policy."""
    key = grammemes if isinstance(grammemes, frozenset) else frozenset(grammemes)
    return _canonicalize_grammemes_cached(key)


@functools.lru_cache(maxsize=32)
def canonicalize_case(case: str | None, default: str = "nomn") -> str:
    """Return the primary pymorphy case for a possibly rare-case value."""
    if case is None:
        return default
    canonical = canonicalize_grammemes({case})
    return next(iter(canonical), default)


def select_parse(
    word_or_parses: str | Sequence[MorphParse],
    *,
    pos: str | Iterable[str] | None = None,
    normal_forms: Iterable[str] | None = None,
    required_grammemes: Iterable[str] = (),
    forbidden_grammemes: Iterable[str] = (),
    preferred_grammemes: Iterable[str] = (),
    gender: str | None = None,
    number: str | None = None,
    case: str | None = None,
) -> MorphParse | None:
    """Select a compatible parse, using upstream score order as final tie-breaker."""
    parses = parse_word(word_or_parses) if isinstance(word_or_parses, str) else word_or_parses
    allowed_pos = (
        None
        if pos is None
        else ({pos} if isinstance(pos, str) else frozenset(pos))
    )
    allowed_normal_forms = (
        None if normal_forms is None else frozenset(value.lower() for value in normal_forms)
    )
    required = canonicalize_grammemes(required_grammemes)
    forbidden = canonicalize_grammemes(forbidden_grammemes)
    preferred = canonicalize_grammemes(preferred_grammemes)
    target_case = canonicalize_case(case) if case is not None else None
    best: MorphParse | None = None
    best_preference_count = -1
    for candidate in parses:
        tag = candidate.tag
        candidate_grammemes = canonicalize_grammemes(tag.grammemes)
        if allowed_pos is not None and tag.POS not in allowed_pos:
            continue
        if (
            allowed_normal_forms is not None
            and candidate.normal_form.lower() not in allowed_normal_forms
        ):
            continue
        if not required.issubset(candidate_grammemes):
            continue
        if forbidden.intersection(candidate_grammemes):
            continue
        if gender is not None and tag.gender != gender:
            continue
        if number is not None and tag.number != number:
            continue
        if target_case is not None and canonicalize_case(tag.case) != target_case:
            continue
        preference_count = len(preferred.intersection(candidate_grammemes))
        if preference_count > best_preference_count:
            best = candidate
            best_preference_count = preference_count
    return best


@functools.lru_cache(maxsize=16384)
def word_is_known(word: str) -> bool:
    """Whether the dictionary holds ``word`` itself, without guessing."""
    return bool(get_morph().word_is_known(word.lower()))


def first_parse(word: str) -> MorphParse | None:
    """Return the first pymorphy parse for ``word``, or ``None`` if there is none.

    In practice pymorphy3 returns at least one parse for any input, so call
    sites have historically indexed ``parse_word(word)[0]`` directly. Routing
    that access through here keeps the undocumented "always non-empty" invariant
    in one guarded place: if a future pymorphy release returns no parses for some
    token, callers get ``None`` from a single chokepoint instead of an
    ``IndexError`` raised from ~30 scattered sites.
    """
    parses = parse_word(word)
    if not parses:
        return None
    return parses[0]


def first_parse_required(word: str) -> MorphParse:
    """Return the first parse and enforce pymorphy's non-empty result invariant.

    Raises instead of asserting: под ``python -O`` assert исчезает, и вместо
    внятной ошибки вызывающий код получил бы ``None`` в аннотации ``MorphParse``
    и падение где-то дальше по стеку.
    """
    parsed = first_parse(word)
    if parsed is None:
        raise RuntimeError(f"pymorphy3 returned no parses for {word!r}")
    return parsed
