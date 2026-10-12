from __future__ import annotations

import logging
import re

import num2words
import roman

from .options import NormalizeOptions
from .ordinal_utils import render_ordinal
from .preprocess_utils import classify_bracketed_numeric_content
from .text_scan import compile_scan

logger = logging.getLogger(__name__)

LINE_NUMBERING_PATTERN = compile_scan(
    r"^([ \t]*)([IVXLCDM]+\.|[\d]+(?:\.[\d]+)*\.)(?!\d)([ \t]*)",
    re.IGNORECASE | re.MULTILINE,
)
#: Внутристрочный номер пункта перечисления: «: 1) …, 2) … и 3) …». Скобка
#: здесь — маркер списка, а не закрытие «(…)», поэтому перед номером стоит
#: только двоеточие/точка с запятой/запятая/союз «и» и пробел.
INLINE_LIST_MARKER_PATTERN = compile_scan(r"(?<=[:;,и][ \t])(\d{1,2})\)(?=\s)")
_LETTER_BEFORE_LEAD = re.compile(r"[0-9A-Za-zА-Яа-яЁёѢѣІіѲѳѴѵ-]")
BRACKETED_NUMBER_PATTERN = compile_scan(
    r"([(\[{])\s*([^()\[\]{}]+?)\*?\s*([)\]}])", re.IGNORECASE
)


def num_to_word(value: int) -> str:
    try:
        return num2words.num2words(value, lang="ru")
    except Exception as exc:
        logger.debug("num2words failed for %r: %s", value, exc)
        return str(value)


def roman_to_word(roman_str: str) -> str:
    try:
        return num_to_word(roman.fromRoman(roman_str.upper()))
    except roman.InvalidRomanNumeralError:
        return roman_str


def convert_numeric_sequence(sequence: str) -> str:
    clean_seq = sequence.rstrip(".")
    if re.match(r"^[IVXLCDM]+$", clean_seq, re.IGNORECASE):
        return roman_to_word(clean_seq)
    parts = [part for part in clean_seq.split(".") if part]
    words: list[str] = []
    for part in parts:
        try:
            words.append(num_to_word(int(part)))
        except ValueError:
            words.append(part)
    return " точка ".join(words)


#: Границы правдоподобного года хронологической записи. Ниже — номер пункта
#: («1000.» встречается в длинном перечне), выше — не год.
_CHRONOLOGY_YEAR_RANGE = range(1000, 2101)
#: Голый номер строки без подномеров: «1941.», но не «1.2.».
_BARE_LINE_MARKER_PATTERN = re.compile(r"\A(?P<value>\d+)\.\Z")


def _bare_line_marker_value(marker: str) -> int | None:
    match = _BARE_LINE_MARKER_PATTERN.match(marker)
    return int(match.group("value")) if match else None


def convert_line_numbering(text: str) -> str:
    """Прочитать номер в начале строки — номером перечня или годом хронологии.

    «1941. Началась война…» — хронологическая запись, и число в ней год, а не
    номер пункта. Отличается она не самим числом, а нумерацией всего текста:
    перечень нумеруют с начала, поэтому его номера доходят до единиц, а у
    хронологии таких номеров нет вовсе. Пока рядом есть голый номер ниже
    тысячи, нумерация доказана, и большие номера остаются номерами перечня.

    Правила «все четырёхзначные числа — годы» здесь нет: римские номера и
    составные «1.2.» в подсчёте не участвуют и класс записи не меняют. Перечень,
    целиком пронумерованный от тысячи и выше, без единого номера ниже
    неотличим от хронологии и читается годами — это принятая граница правила.

    Разбор идёт по одному проходу: решение о классе нужно всему тексту сразу,
    а второй `finditer` на книге — второй полнотекстовый проход впустую.
    """
    matches = list(LINE_NUMBERING_PATTERN.finditer(text))
    if not matches:
        return text
    values = [_bare_line_marker_value(match.group(2)) for match in matches]
    bare_values = [value for value in values if value is not None]
    chronology = bool(bare_values) and all(
        value in _CHRONOLOGY_YEAR_RANGE for value in bare_values
    )

    pieces: list[str] = []
    position = 0
    for match, value in zip(matches, values, strict=True):
        if chronology and value is not None:
            # Год-порядковое: «Тысяча девятьсот сорок первый.», а не
            # количественное «Одна тысяча девятьсот сорок один.».
            converted = render_ordinal(value, gender="masc", inanimate=True).capitalize()
        else:
            converted = convert_numeric_sequence(match.group(2)).capitalize()
        pieces.append(text[position : match.start()])
        pieces.append(f"{match.group(1)}{converted}.{match.group(3)}")
        position = match.end()
    pieces.append(text[position:])
    return "".join(pieces)


def convert_inline_list_markers(text: str) -> str:
    if ")" not in text:
        return text
    matches = list(INLINE_LIST_MARKER_PATTERN.finditer(text))
    if not matches:
        return text

    # Скобка после номера обязана быть маркером списка, а не закрытием
    # реальной «(…)» — отсекаем совпадения с незакрытой «(» слева.
    candidates: list[re.Match[str]] = []
    balance = 0
    scanned = 0
    for match in matches:
        balance += text.count("(", scanned, match.start())
        balance -= text.count(")", scanned, match.start())
        scanned = match.start()
        if balance <= 0:
            candidates.append(match)

    # Перечисление — это серия: «1)» после двоеточия и дальше номера по
    # порядку через запятую/точку с запятой. Одиночный номер не трогаем.
    runs: list[list[re.Match[str]]] = []
    current: list[re.Match[str]] = []
    expected = 1
    for match in candidates:
        value = int(match.group(1))
        lead = text[match.start() - 2]
        if lead == "и" and (
            match.start() >= 3 and _LETTER_BEFORE_LEAD.match(text, match.start() - 3)
        ):
            lead = "?"  # «и» — хвост слова («почти»), а не союз перед пунктом
        if current and value == expected and lead in {",", ";", "и"}:
            current.append(match)
            expected += 1
            continue
        if len(current) >= 2:
            runs.append(current)
        current = []
        expected = 1
        if value == 1 and lead in {":", ";"}:
            current = [match]
            expected = 2
    if len(current) >= 2:
        runs.append(current)
    if not runs:
        return text

    pieces: list[str] = []
    consumed = 0
    for match in (item for run in runs for item in run):
        pieces.append(text[consumed : match.start()])
        pieces.append(render_ordinal(int(match.group(1)), case="nomn", gender="neut"))
        pieces.append(")")
        consumed = match.end()
    pieces.append(text[consumed:])
    return "".join(pieces)


def convert_bracketed_numbers(
    text: str, options: NormalizeOptions | None = None
) -> str:
    active = options or NormalizeOptions()
    pairs = {"(": ")", "[": "]", "{": "}"}

    def repl(match: re.Match[str]) -> str:
        opener, sequence, closer = match.group(1), match.group(2), match.group(3)
        if pairs.get(opener) != closer:
            return match.group(0)

        stripped = sequence.strip()
        if re.match(r"^[IVXLCDM]+$", stripped, re.IGNORECASE):
            kind = "reference"
        else:
            kind = classify_bracketed_numeric_content(stripped)
        if kind != "reference":
            return match.group(0)

        should_remove = False
        if active.remove_links:
            should_remove = True
            try:
                if stripped.isdigit():
                    value = int(stripped)
                    min_val, max_val = active.remove_links_ignore_interval
                    if min_val <= value <= max_val:
                        should_remove = False
            except Exception as exc:
                logger.debug("remove_links interval check failed for %r: %s", stripped, exc)
        if should_remove:
            return ""
        return match.group(0)

    return BRACKETED_NUMBER_PATTERN.sub(repl, text)
