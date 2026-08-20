"""Реестр служебных символов-заменителей и их восстановление.

Пайплайн прячет фрагменты, которые нельзя отдавать нормализующим правилам —
URL, пути Windows, структурированные числовые токены, буквенно-цифровые коды —
за символы из области private use. Раньше каждый клиент считал кодовые точки
сам: `run_numerals` выдавал `chr(0xF0000 + i)` без верхней границы,
`protect_windows_paths` держал `(0xF1000, 0xF1FFD)`, а `protect_urls` объявлял
своими сразу обе плоскости PUA целиком. После 4096 защищённых числовых токенов
номера заходили в диапазон путей, и восстановление подставляло путь на месте
числа. Здесь диапазоны объявлены один раз и не пересекаются по построению —
это проверяется тестом.

Второе назначение модуля — восстановление за один проход. Клиенты
восстанавливали заменители циклом `str.replace` по одному, то есть делали по
полному проходу документа на каждый спрятанный фрагмент: на книге с сотнями
чисел это сотни проходов ради результата, который даёт один `re.sub`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlaceholderRange:
    """Непересекающийся поддиапазон private use, закреплённый за одним клиентом."""

    name: str
    start: int
    end: int
    """Последняя кодовая точка диапазона включительно."""

    @property
    def capacity(self) -> int:
        return self.end - self.start + 1

    def __contains__(self, char: str) -> bool:
        return len(char) == 1 and self.start <= ord(char) <= self.end


#: Постоянные метки препроцессинга: по одному символу на смысл, не выдаются
#: по требованию. `0xE002` пропущен — так исторически сложилась нумерация, и
#: менять её незачем.
PREPROCESS_SENTINELS = PlaceholderRange("preprocess-sentinels", 0xE000, 0xE0FF)

LETTER_HYPHEN_PLACEHOLDER = chr(0xE000)
NEGATIVE_NUMBER_PLACEHOLDER = chr(0xE001)
UNIT_SLASH_PLACEHOLDER = chr(0xE003)
BINARY_PLUS_PLACEHOLDER = chr(0xE004)
BINARY_MINUS_PLACEHOLDER = chr(0xE005)
BINARY_POWER_PLACEHOLDER = chr(0xE006)

#: Буквенно-цифровые коды («A4», «Ту-154»), спрятанные на время расклейки
#: числительных. Остальная часть BMP PUA до `0xF8FD`.
GLUED_CODES = PlaceholderRange("glued-codes", 0xE100, 0xF8FD)

#: Структурированные числовые токены — самый многочисленный клиент, поэтому
#: ему отдана вся плоскость 15.
NUMERAL_TOKENS = PlaceholderRange("numeral-tokens", 0xF0000, 0xFFFFD)

#: Пути Windows и URL: их в тексте единицы, плоскости 16 хватает с запасом.
WINDOWS_PATHS = PlaceholderRange("windows-paths", 0x100000, 0x1007FF)
URLS = PlaceholderRange("urls", 0x100800, 0x100FFF)

RESERVED_RANGES: tuple[PlaceholderRange, ...] = (
    PREPROCESS_SENTINELS,
    GLUED_CODES,
    NUMERAL_TOKENS,
    WINDOWS_PATHS,
    URLS,
)

#: Один класс символов на все зарезервированные диапазоны: по нему идёт
#: единственная проверка входа на занятость.
RESERVED_PATTERN = re.compile(
    "[" + "".join(f"\\U{r.start:08X}-\\U{r.end:08X}" for r in RESERVED_RANGES) + "]"
)


def reserved_characters_in(text: str) -> set[str]:
    """Найти во входе символы служебных диапазонов — один проход по тексту.

    Такие символы во входе законны (private use, пайплайн о них ничего не
    утверждает), но выдавать их как заменители нельзя: восстановление подставило
    бы спрятанный фрагмент и на месте исходного символа тоже.
    """
    if RESERVED_PATTERN.search(text) is None:
        return set()
    occupied = set(RESERVED_PATTERN.findall(text))
    logger.debug("Input already contains %d reserved private-use character(s)", len(occupied))
    return occupied


class PlaceholderAllocator:
    """Выдаёт заменители из одного диапазона и восстанавливает их за один проход.

    Объект живёт один прогон нормализации: два прогона не должны делить
    состояние, иначе заменитель одного восстановится фрагментом другого.
    """

    __slots__ = ("_next", "_occupied", "_originals", "_pattern", "_range", "_text")

    def __init__(self, reserved: PlaceholderRange, text: str = "") -> None:
        self._range = reserved
        self._originals: dict[str, str] = {}
        self._next = reserved.start
        self._pattern = re.compile(f"[\\U{reserved.start:08X}-\\U{reserved.end:08X}]")
        self._text = text
        self._occupied: frozenset[str] | None = None

    def __len__(self) -> int:
        return len(self._originals)

    @property
    def exhausted(self) -> bool:
        return self._next > self._range.end

    def allocate(self, original: str) -> str | None:
        """Занять заменитель под `original`; `None`, если диапазон исчерпан.

        Исчерпание — не ошибка: вызывающий код оставляет фрагмент как есть и
        теряет защиту для него, но не падает на документе-выбросе.
        """
        if self._occupied is None:
            # Проверка занятости — один проход по тексту, и только если из
            # диапазона вообще что-то выдаётся. Большинство документов не
            # содержит ни URL, ни путей, ни структурированных чисел, и платить
            # за скан на них незачем.
            self._occupied = frozenset(self._pattern.findall(self._text))
            self._text = ""
        while not self.exhausted:
            placeholder = chr(self._next)
            self._next += 1
            if placeholder in self._occupied:
                continue
            self._originals[placeholder] = original
            return placeholder
        logger.debug("Placeholder range %s is exhausted", self._range.name)
        return None

    def restore(self, text: str) -> str:
        """Вернуть спрятанные фрагменты на место — один проход по тексту."""
        if not self._originals:
            return text
        originals = self._originals
        restored, replaced = self._pattern.subn(
            # Незнакомый символ из диапазона оставляем как есть: удалить его
            # значит молча потерять кусок текста, а восстановить нечем.
            lambda match: originals.get(match.group(0), match.group(0)),
            text,
        )
        if replaced != len(originals):
            logger.error(
                "%s: restored %d of %d placeholder(s); a stage dropped the rest",
                self._range.name,
                replaced,
                len(originals),
            )
        return restored
