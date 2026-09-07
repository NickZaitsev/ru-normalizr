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
    r"(?<!\w)(?P<prep>под|с|со|к|ко|по|у|из|от|до)\s+№\s*(?=\d)",
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


#: Библиографическая цепочка «Т. IX. С. 381—382.»: том с номером снимает
#: двусмысленность заглавной «С.» (инициал против страницы). Одиночная
#: заглавная «С.» без тома по-прежнему считается инициалом.
VOLUME_PAGE_REFERENCE_PATTERN = compile_scan(
    rf"\bТ\.\s*(?P<volume>[IVXLCDM]+|\d+)\.\s*[Сс]\.\s*"
    rf"(?P<left>{_PAGE_NUMBER_PATTERN})"
    rf"(?:\s*[–—-]\s*(?P<right>{_PAGE_NUMBER_PATTERN}))?"
    r"(?![A-Za-zА-ЯЁа-яё])"
)


def _replace_volume_page_reference(match: re.Match[str]) -> str:
    volume_number = _page_number(match.group("volume"))
    left_number = _page_number(match.group("left"))
    if volume_number is None or left_number is None:
        return match.group(0)
    volume_word = render_ordinal(
        volume_number, case="nomn", gender="masc", inanimate=True
    )
    left_word = num2words.num2words(left_number, lang="ru")
    if match.group("right") is None:
        return f"Том {volume_word}. Страница {left_word}"
    right_number = _page_number(match.group("right"))
    if right_number is None:
        return match.group(0)
    right_word = num2words.num2words(right_number, lang="ru")
    return f"Том {volume_word}. Страницы {left_word} — {right_word}"


#: Падеж ссылочного существительного по предлогу слева. Управление у ссылки
#: обычное, а номер остаётся меткой и падежа не получает.
REFERENCE_PREPOSITION_CASES = {
    "согласно": "datv",
    "по": "datv",
    "к": "datv",
    "ко": "datv",
    "в": "loct",
    "во": "loct",
    "о": "loct",
    "об": "loct",
    "из": "gent",
    "с": "gent",
    "со": "gent",
    "до": "gent",
    "от": "gent",
}
REFERENCE_PREPOSITION_PATTERN = re.compile(
    r"(?:^|\s)(?P<word>"
    + "|".join(sorted(REFERENCE_PREPOSITION_CASES, key=len, reverse=True))
    + r")\s*$",
    re.IGNORECASE,
)


def reference_case_from_left(text: str, start: int) -> str:
    """Падеж ссылочного существительного по предлогу непосредственно слева."""
    match = REFERENCE_PREPOSITION_PATTERN.search(left_context(text, start, 32))
    if match is None:
        return "nomn"
    return REFERENCE_PREPOSITION_CASES[match.group("word").casefold()]


#: Формы ссылочных существительных по падежу. Список закрыт: маркер сокращения
#: раскрывается только там, где его значение однозначно.
_CLAUSE_REFERENCE_FORMS = {
    "пункт": {
        "nomn": "пункт",
        "gent": "пункта",
        "datv": "пункту",
        "loct": "пункте",
    },
    "подпункт": {
        "nomn": "подпункт",
        "gent": "подпункта",
        "datv": "подпункту",
        "loct": "подпункте",
    },
}
_CLAUSE_REFERENCE_MARKERS = {"п": "пункт", "подп": "подпункт", "пп": "подпункт"}

#: Пункт с составным номером: «п. 1.2.34». Маркер ссылки слева задаёт класс
#: записи раньше, чем `dates_time` увидит в «1.2.34» дату, а числительные —
#: десятичную дробь. Составной номер обязателен: одиночное «п. 2» остаётся
#: прежнему владельцу, и эта правка его поведения не меняет.
CLAUSE_REFERENCE_PATTERN = compile_scan(
    r"(?<!\w)(?P<marker>подп|пп|п)\.\s*(?P<number>\d+(?:\.\d+)+)(?!\w)",
    re.IGNORECASE,
)


def normalize_clause_references(text: str) -> str:
    """«Согласно п. 1.2.34 договора» — «Согласно пункту один точка два точка…».

    Ссылочное существительное согласуется с управлением слева, а номер остаётся
    меткой: он читается по частям через «точка», как уже читаются номера статей
    и параграфов.
    """

    def repl(match: re.Match[str]) -> str:
        number = _render_dotted_number(match.group("number"))
        if number is None:
            return match.group(0)
        lemma = _CLAUSE_REFERENCE_MARKERS[match.group("marker").casefold()]
        case = reference_case_from_left(text, match.start())
        noun = _CLAUSE_REFERENCE_FORMS[lemma][case]
        context = left_context(text, match.start(), 24)
        if not context.strip() or context.rstrip().endswith((".", "!", "?", "…")):
            noun = noun.capitalize()
        return f"{noun} {number}"

    return CLAUSE_REFERENCE_PATTERN.sub(repl, text)


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

# Номер параграфа читается и без точки: «§ 3» — такая же ссылка, как «§ 3.1»,
# и знак сам по себе для синтеза бесполезен.
SECTION_REFERENCE_PATTERN = compile_scan(
    r"(?<!\w)§\s*(?P<first>\d+(?:\.\d+)*)(?!\d)"
    r"(?:\s+и\s+§\s*(?P<second>\d+(?:\.\d+)*)(?!\d))?"
)

ISBN_PATTERN = compile_scan(
    r"(?<!\w)(?P<prefix>ISBN)\s+(?P<groups>\d+(?:[-–—]\d+){3,4})(?!\w)",
    re.IGNORECASE,
)


def normalize_page_references(text: str) -> str:
    text = VOLUME_PAGE_REFERENCE_PATTERN.sub(_replace_volume_page_reference, text)

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
            # «Смотри страницы…» — винительный от глагола, «на страницах…» —
            # предложный от предлога: диапазон подчиняется тому же управлению,
            # что и одиночный номер страницы ниже.
            noun = "страницы" if directive in {"см", "смотри"} else "страницах"
            return f"{noun} с {left} по {right}"
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
        point_case = reference_case_from_left(text, match.start())
        point_word = _CLAUSE_REFERENCE_FORMS["пункт"][point_case]
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
        # Предлог «в» ставит существительное в предложный падеж, а число
        # параграфов задаёт его число: «в параграфе три», «в параграфах три и
        # четыре». Знак пишут и с заглавной строки, поэтому регистр «В» тоже
        # управляет.
        if re.search(r"\bв\s*$", context, re.IGNORECASE):
            noun = "параграфах" if second else "параграфе"
        else:
            noun = "параграф"
        if not context.strip() or context.rstrip().endswith((".", "!", "?", "…")):
            noun = noun.capitalize()
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
