"""Защита цифровых простыней от правил числительных.

Озвучить такое число нечем: `num2words` для русского заканчивается на
10**34 - 1, а с версии 3.11 сам `int()` отказывается разбирать строку длиннее
4300 цифр — это защита интерпретатора от квадратичного разбора. Правила же
берут значение десятками голых `int()`, поэтому OCR-мусор, склеенный
идентификатор или битая таблица роняли не своё правило, а весь прогон.

Прятать простыню целиком дешевле и честнее, чем чинить каждое правило
по отдельности: ни одно из них не увидит фрагмент, который всё равно не
умеет произнести, а на выходе цифры вернутся на своё место.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .placeholders import OVERLONG_NUMBERS, PlaceholderAllocator

#: Предел, до которого русские числительные вообще проговариваются:
#: `num2words(10**34, lang="ru")` уже падает с `KeyError`.
MAX_SPOKEN_DIGITS = 33

# `\d`, а не `[0-9]`: цифры чужой письменности правила тоже приводят к ASCII
# перед `int()`, так что простыня из них падала ровно так же.
_OVERLONG_DIGIT_RUN_PATTERN = re.compile(rf"\d{{{MAX_SPOKEN_DIGITS + 1},}}")


@dataclass
class ProtectedOverlongNumbers:
    """Текст со спрятанными простынями и средство вернуть их на место."""

    text: str
    allocator: PlaceholderAllocator | None = None

    def restore(self, text: str) -> str:
        if self.allocator is None:
            return text
        return self.allocator.restore(text)


def protect_overlong_numbers(text: str) -> ProtectedOverlongNumbers:
    """Спрятать цифровые пробеги, которые нечем произнести."""
    if not _OVERLONG_DIGIT_RUN_PATTERN.search(text):
        return ProtectedOverlongNumbers(text)
    allocator = PlaceholderAllocator(OVERLONG_NUMBERS, text)

    def repl(match: re.Match[str]) -> str:
        placeholder = allocator.allocate(match.group(0))
        return match.group(0) if placeholder is None else placeholder

    protected = _OVERLONG_DIGIT_RUN_PATTERN.sub(repl, text)
    if not len(allocator):
        return ProtectedOverlongNumbers(text)
    return ProtectedOverlongNumbers(protected, allocator)
