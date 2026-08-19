"""Ссылки на страницы, статьи, параграфы, законы и ISBN.

У всех этих правил один предмет: сокращение плюс номер, которое надо прочесть
как ссылку и согласовать с предлогом слева («в § 8.32» -> «в параграфах…»).
Поэтому окно левого контекста здесь — часть правила, а не оптимизация.
"""

from __future__ import annotations

import re

import num2words
import roman

from .ordinal_utils import render_ordinal
from .preprocess_utils import left_context
from .text_scan import compile_scan

NUMBER_SIGN_PATTERN = compile_scan(r"(?<!\w)№\s*(?=\d)")
NUMBER_SIGN_WITH_PREPOSITION_PATTERN = compile_scan(
    r"(?P<prep>под|с|со|к|ко|по|у|из|от|до)\s+№\s*(?=\d)",
    re.IGNORECASE,
)
#: Предлог задаёт падеж раскрытого «№». Огласованные «со»/«ко» существуют только
#: перед скоплением согласных, а раскрытие даёт «номером»/«номеру», поэтому
#: грамматически верна базовая форма предлога.
NUMBER_SIGN_PREPOSITION_FORMS = {
    "под": "под номером ",
    "с": "с номером ",
    "со": "с номером ",
    "к": "к номеру ",
    "ко": "к номеру ",
    "по": "по номеру ",
    "у": "у номера ",
    "из": "из номера ",
    "от": "от номера ",
    "до": "до номера ",
}

#: Номер страницы бывает и римским («с. CVIII»): предисловия и вводные тома
#: нумеруются римскими цифрами. Одна буква не допускается — «С. М. Соловьёв»
#: не ссылка на тысячную страницу.
_PAGE_NUMBER_PATTERN = r"\d+|[IVXLCDM]{2,}"
PAGE_REFERENCE_PATTERN = compile_scan(
    rf"\b(?:стр\.|с\.)\s*(?:(?P<left>{_PAGE_NUMBER_PATTERN})\s*[–—-]\s*"
    rf"(?P<right>{_PAGE_NUMBER_PATTERN})|(?P<number>{_PAGE_NUMBER_PATTERN}))"
    r"(?![A-Za-zА-ЯЁа-яё])",
    re.IGNORECASE,
)


def _page_number(raw: str) -> int | None:
    if raw.isdecimal():
        return int(raw)
    try:
        return roman.fromRoman(raw.upper())
    except roman.InvalidRomanNumeralError:
        return None

LEGAL_COMPLEX_REFERENCE_PATTERN = compile_scan(
    r"(?<!\w)п\.\s*(?P<point>\d+)\s+ст\.\s*(?P<article>\d+)\s+"
    r"ФЗ\s+№\s*(?P<code>\d+)(?!\w)",
    re.IGNORECASE,
)

ADMINISTRATIVE_LAW_REFERENCE_PATTERN = compile_scan(
    r"(?<!\w)(?:(?P<prep>в|во|о|об|согласно)\s+)?ч\.\s*(?P<part>\d+)\s+ст\.\s*"
    r"(?P<article>\d+(?:\.\d+)?)\s+КоАП\s+РФ(?!\w)",
    re.IGNORECASE,
)

SECTION_REFERENCE_PATTERN = compile_scan(
    r"(?<!\w)§\s*(?P<first>\d+(?:\.\d+)+)"
    r"(?:\s+и\s+§\s*(?P<second>\d+(?:\.\d+)+))?"
)

ISBN_PATTERN = compile_scan(
    r"(?<!\w)(?P<prefix>ISBN)\s+(?P<groups>\d+(?:[-–—]\d+){3,4})(?!\w)",
    re.IGNORECASE,
)


def normalize_page_references(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        context = left_context(text, match.start(), 24)
        preceding = re.search(
            r"(?:^|\s)(?P<word>на|в|во|см\.|смотри)\s*$",
            context,
            re.IGNORECASE,
        )
        if preceding is None:
            # Без управляющего слова прочитать диапазон всё же можно:
            # «(с. 108—113)» — это «страницы сто восемь — сто тринадцать».
            # Заглавная «С.» без управления — с тем же успехом инициал
            # («Иванов С.»), поэтому раскрывается только строчное сокращение.
            if match.group("left") is None or not match.group(0)[0].islower():
                return match.group(0)
            left_number = _page_number(match.group("left"))
            right_number = _page_number(match.group("right"))
            if left_number is None or right_number is None:
                return match.group(0)
            left_word = num2words.num2words(left_number, lang="ru")
            right_word = num2words.num2words(right_number, lang="ru")
            return f"страницы {left_word} — {right_word}"
        directive = preceding.group("word").casefold().rstrip(".")
        if match.group("left") is not None:
            left_number = _page_number(match.group("left"))
            right_number = _page_number(match.group("right"))
            if left_number is None or right_number is None:
                return match.group(0)
            left = render_ordinal(
                left_number, case="gent", gender="femn", inanimate=True
            )
            right = render_ordinal(
                right_number, case="accs", gender="femn", inanimate=True
            )
            return f"страницах с {left} по {right}"
        number_value = _page_number(match.group("number"))
        if number_value is None:
            return match.group(0)
        case = "accs" if directive in {"см", "смотри"} else "loct"
        noun = "страницу" if case == "accs" else "странице"
        number = render_ordinal(
            number_value, case=case, gender="femn", inanimate=True
        )
        return f"{noun} {number}"

    return PAGE_REFERENCE_PATTERN.sub(repl, text)


def normalize_complex_legal_references(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        context = left_context(text, match.start(), 32)
        prep_match = re.search(
            r"(?:^|\s)(?P<word>согласно|в|во|о|об|по|к|ко|из|с|со|до|от)\s*$",
            context,
            re.IGNORECASE,
        )
        prep = prep_match.group("word").casefold() if prep_match else ""
        if prep in {"согласно", "по", "к", "ко"}:
            point_case = "datv"
            point_word = "пункту"
        elif prep in {"в", "во", "о", "об"}:
            point_case = "loct"
            point_word = "пункте"
        elif prep in {"из", "с", "со", "до", "от"}:
            point_case = "gent"
            point_word = "пункта"
        else:
            point_case = "nomn"
            point_word = "пункт"
        point = render_ordinal(
            int(match.group("point")),
            case=point_case,
            gender="masc",
            inanimate=True,
        )
        article = render_ordinal(
            int(match.group("article")),
            case="gent",
            gender="femn",
            inanimate=True,
        )
        return (
            f"{point_word} {point} статьи {article} федерального закона "
            f"номер {match.group('code')}"
        )

    return LEGAL_COMPLEX_REFERENCE_PATTERN.sub(repl, text)


def _render_dotted_number(raw: str) -> str | None:
    """«8.32» -> «восемь точка тридцать два»; None, если это не номер.

    Иерархические номера статей и параграфов читаются по частям через «точка», а
    не как дробь: «часть 8.32» — это тридцать вторая единица внутри восьмой.
    """
    words: list[str] = []
    for part in raw.split("."):
        try:
            words.append(num2words.num2words(int(part), lang="ru"))
        except (TypeError, ValueError):
            return None
    return " точка ".join(words)


def normalize_administrative_law_references(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        prep = match.group("prep")
        governed_part = prep is not None
        try:
            part = render_ordinal(
                int(match.group("part")),
                case="gent" if governed_part else "ablt",
                gender="femn",
                inanimate=True,
            )
        except (TypeError, ValueError):
            return match.group(0)
        article = _render_dotted_number(match.group("article"))
        if article is None:
            return match.group(0)
        part_word = "части" if governed_part else "частью"
        prefix = f"{prep} " if prep else ""
        return (
            f"{prefix}{part_word} {part} статьи {article} Кодекса Российской Федерации "
            "об административных правонарушениях"
        )

    return ADMINISTRATIVE_LAW_REFERENCE_PATTERN.sub(repl, text)


def normalize_section_references(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        first = _render_dotted_number(match.group("first"))
        second_raw = match.group("second")
        second = _render_dotted_number(second_raw) if second_raw else None
        if first is None or (second_raw is not None and second is None):
            return match.group(0)
        context = left_context(text, match.start(), 24)
        noun = "параграфах" if re.search(r"\bв\s*$", context) else "параграф"
        return f"{noun} {first}" + (f" и {second}" if second else "")

    return SECTION_REFERENCE_PATTERN.sub(repl, text)


def normalize_isbn_identifiers(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        groups = re.split(r"[-–—]", match.group("groups"))
        if len(groups) not in {4, 5}:
            return match.group(0)
        try:
            rendered = [num2words.num2words(int(group), lang="ru") for group in groups]
        except (TypeError, ValueError):
            return match.group(0)
        return f"{match.group('prefix')} {' — '.join(rendered)}"

    return ISBN_PATTERN.sub(repl, text)


def normalize_number_signs(text: str) -> str:
    def with_preposition(match: re.Match[str]) -> str:
        prep = match.group("prep")
        expansion = NUMBER_SIGN_PREPOSITION_FORMS[prep.casefold()]
        # «Со № 5» начинает предложение, а раскрытие съедает слово, которое
        # несло заглавную букву, поэтому регистр надо перенести.
        if prep[:1].isupper():
            return expansion[:1].upper() + expansion[1:]
        return expansion

    text = NUMBER_SIGN_WITH_PREPOSITION_PATTERN.sub(with_preposition, text)
    return NUMBER_SIGN_PATTERN.sub("номер ", text)
