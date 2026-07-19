from __future__ import annotations

import functools
from typing import Any

import pymorphy3


@functools.lru_cache(maxsize=1)
def get_morph() -> pymorphy3.MorphAnalyzer:
    return pymorphy3.MorphAnalyzer()


@functools.lru_cache(maxsize=65536)
def parse_word(word: str) -> tuple[Any, ...]:
    """Parse a word once and expose an immutable cached result."""
    return tuple(get_morph().parse(word))


def first_parse(word: str) -> Any | None:
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
