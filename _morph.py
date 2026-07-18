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
