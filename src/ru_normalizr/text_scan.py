from __future__ import annotations

import re
import weakref
from collections.abc import Iterator, Sequence
from typing import TypeAlias

try:  # Python 3.11+ moved the regex parser out of the deprecated top-level module.
    from re import _parser as _re_parser  # type: ignore[attr-defined, unused-ignore]
except ImportError:  # pragma: no cover - Python 3.10 keeps it at the top level.
    import sre_parse as _re_parser

#: Every live guarded pattern, for the equivalence test. Weak so that patterns
#: compiled inside a function body do not accumulate.
_GUARDED_PATTERNS: weakref.WeakSet[GuardedPattern] = weakref.WeakSet()


#: The last casefolded document, so that the case-insensitive guards of one pass
#: fold it once instead of once each. Compared by identity, which makes a stale
#: entry impossible; :func:`clear_fold_cache` drops the reference afterwards.
_FOLD_CACHE: tuple[str, str] | None = None


def _casefolded(text: str) -> str:
    global _FOLD_CACHE
    cached = _FOLD_CACHE
    if cached is not None and cached[0] is text:
        return cached[1]
    folded = text.casefold()
    _FOLD_CACHE = (text, folded)
    return folded


def clear_fold_cache() -> None:
    """Drop the cached casefolded document so it is not kept alive after a run."""

    global _FOLD_CACHE
    _FOLD_CACHE = None


class GuardedPattern:
    """A compiled pattern that skips its scan when no required literal is present.

    A rare full-text pass costs milliseconds on a book-sized string even when it
    cannot match: the engine still walks every position. A literal check walks
    the string in C and rejects the whole document in microseconds.

    Every guard must be **necessary** for the pattern to match, otherwise the
    skip changes the result. `tests/test_performance_guards.py` checks that by
    normalizing a corpus sample twice, with guards live and with guards
    disabled, and comparing the output.
    """

    __slots__ = ("__weakref__", "_ignorecase", "_literals", "pattern")

    def __init__(self, pattern: re.Pattern[str], *guards: str) -> None:
        if not guards:
            raise ValueError("a guarded pattern needs at least one guard")
        self.pattern = pattern
        self._ignorecase = bool(pattern.flags & re.IGNORECASE)
        # ``str.__contains__`` searches in C and beats a compiled literal pattern
        # by an order of magnitude; a case-insensitive regex is slower still.
        self._literals = tuple(
            guard.casefold() if self._ignorecase else guard for guard in guards
        )
        _GUARDED_PATTERNS.add(self)

    def may_match(self, text: str) -> bool:
        """Check whether any guard occurs in ``text``."""

        haystack = _casefolded(text) if self._ignorecase else text
        return any(literal in haystack for literal in self._literals)

    def sub(self, repl, text: str, count: int = 0) -> str:
        if not self.may_match(text):
            return text
        return self.pattern.sub(repl, text, count)

    def subn(self, repl, text: str, count: int = 0) -> tuple[str, int]:
        if not self.may_match(text):
            return text, 0
        return self.pattern.subn(repl, text, count)

    def search(self, text: str, *args: int) -> re.Match[str] | None:
        if not self.may_match(text):
            return None
        return self.pattern.search(text, *args)

    def match(self, text: str, *args: int) -> re.Match[str] | None:
        if not self.may_match(text):
            return None
        return self.pattern.match(text, *args)

    def findall(self, text: str, *args: int) -> list:
        if not self.may_match(text):
            return []
        return self.pattern.findall(text, *args)

    def finditer(self, text: str, *args: int) -> Iterator[re.Match[str]]:
        if not self.may_match(text):
            return iter(())
        return self.pattern.finditer(text, *args)

    def split(self, text: str, maxsplit: int = 0) -> list:
        if not self.may_match(text):
            return [text]
        return self.pattern.split(text, maxsplit)

    def __getattr__(self, item: str):
        return getattr(self.pattern, item)


#: Even a one-character guard pays off: a literal scan walks a book in
#: microseconds while a regex pass over it costs milliseconds.
_MIN_GUARD_LENGTH = 1

#: Each alternative costs one substring scan, so a wide alternation stops
#: being a cheap prefilter.
_MAX_GUARD_ALTERNATIVES = 16

_REPEAT_OPCODES = frozenset({"MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"})


def _class_alternatives(items) -> tuple[str, ...]:
    r"""Return the characters of a character class, or nothing if it is not plain.

    A negated class, a range or a category (``\d``, ``\w``) matches characters
    that cannot be enumerated cheaply, so such a class yields no guard.
    """

    characters: list[str] = []
    for opcode, argument in items:
        if str(opcode) != "LITERAL":
            return ()
        characters.append(chr(argument))
    if not characters or len(characters) > _MAX_GUARD_ALTERNATIVES:
        return ()
    return tuple(characters)


def _branch_alternatives(branches) -> tuple[str, ...]:
    """Return literals covering every branch, so one of them must be present."""

    alternatives: list[str] = []
    for branch in branches:
        best = _best_group(_candidate_groups(branch))
        if not best:
            return ()
        alternatives.extend(best)
        if len(alternatives) > _MAX_GUARD_ALTERNATIVES:
            return ()
    return tuple(dict.fromkeys(alternatives))


def _candidate_groups(parsed) -> list[tuple[str, ...]]:
    """Collect groups of literals such that a match must contain one per group.

    Only unavoidable constructs are inspected: a literal run, a plain character
    class, an alternation whose every branch yields literals, a group, and a
    repetition with a positive minimum. Optional parts and look-arounds yield
    nothing and break the current run, so every literal returned really is a
    substring of any match.
    """

    groups: list[tuple[str, ...]] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            groups.append(("".join(current),))
            current.clear()

    for opcode, argument in parsed:
        name = str(opcode)
        if name == "LITERAL":
            current.append(chr(argument))
            continue
        flush()
        if name == "IN":
            alternatives = _class_alternatives(argument)
            if alternatives:
                groups.append(alternatives)
        elif name == "BRANCH":
            alternatives = _branch_alternatives(argument[1])
            if alternatives:
                groups.append(alternatives)
        elif name == "SUBPATTERN":
            # A group that changes flags mid-pattern is not worth reasoning about.
            if not argument[1] and not argument[2]:
                groups.extend(_candidate_groups(argument[3]))
        elif name == "ATOMIC_GROUP":
            groups.extend(_candidate_groups(argument))
        elif name in _REPEAT_OPCODES and argument[0] >= 1:
            groups.extend(_candidate_groups(argument[2]))
    flush()
    return groups


def _group_score(group: tuple[str, ...]) -> tuple[int, int]:
    """Rank a guard group: long literals first, few alternatives second."""

    return min(len(alternative) for alternative in group), -len(group)


def _best_group(groups: list[tuple[str, ...]]) -> tuple[str, ...]:
    usable = [
        group
        for group in groups
        if group
        and len(group) <= _MAX_GUARD_ALTERNATIVES
        and min(len(alternative) for alternative in group) >= _MIN_GUARD_LENGTH
    ]
    if not usable:
        return ()
    return max(usable, key=_group_score)


def required_guards(pattern: str, flags: int = 0) -> tuple[str, ...]:
    """Return literals of which every match of ``pattern`` contains at least one."""

    try:
        parsed = _re_parser.parse(pattern, flags)
    except re.error:  # pragma: no cover - the pattern is compiled elsewhere anyway
        return ()
    return _best_group(_candidate_groups(parsed))


def compile_scan(pattern: str, flags: int = 0) -> ScanPattern:
    """Compile ``pattern``, guarding it by literals it cannot match without.

    Falls back to a plain compiled pattern when nothing is mandatory, so the call
    is always safe to use in place of :func:`re.compile`.
    """

    compiled = re.compile(pattern, flags)
    guards = required_guards(pattern, flags)
    if not guards:
        return compiled
    return GuardedPattern(compiled, *guards)


#: Either kind of pattern a scanning module works with.
ScanPattern: TypeAlias = "re.Pattern[str] | GuardedPattern"


def guarded_patterns() -> Sequence[GuardedPattern]:
    """Return every guarded pattern created so far."""
    return tuple(_GUARDED_PATTERNS)


def first_non_whitespace_index(text: str, start: int) -> tuple[int, bool]:
    """Return the first non-whitespace position and whether a newline was seen.

    This is the positional equivalent of ``text[start:].lstrip()``. Keeping
    the original string and advancing an index avoids copying the entire
    remaining document from every regular-expression callback.
    """

    index = start
    saw_newline = False
    while index < len(text) and text[index].isspace():
        saw_newline = saw_newline or text[index] == "\n"
        index += 1
    return index, saw_newline
