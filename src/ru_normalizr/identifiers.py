"""Идентификаторы: номера домов и машин, телефоны, склейка числа со словом.

Это правила препроцесса, у которых общий предмет — короткий код, в котором
цифры и буквы стоят рядом. Раньше они жили методами `PipelineNormalizer`, где
были неотличимы от порядка стадий; здесь они обычные функции, а пайплайн только
выстраивает их в очередь.
"""

from __future__ import annotations

import re

from ._morph import first_parse_required, parse_word
from .constants import LetterVowelMode, resolve_letter_name
from .numerals._constants import is_unit_token, resolve_unit_info
from .numerals._helpers import LABEL_NOUN_LEMMAS
from .numerals.numeric_suffixes import NUMERIC_SUFFIXES
from .placeholders import GLUED_CODES, PlaceholderAllocator
from .preprocess_utils import left_context
from .text_scan import compile_scan

LEADING_LETTER_DIGIT_PATTERN = compile_scan(
    r"(?<!/)(?P<letters>[а-яА-ЯёЁa-zA-Z]+)(?P<number>\d+)"
)
PHONE_NUMBER_PATTERN = compile_scan(
    r"(?<!\w)(?P<country>\+?\d{1,3})\s*\(\s*(?P<area>\d{3})\s*\)\s*"
    r"(?P<first>\d{3})\s*-\s*(?P<second>\d{2})\s*-\s*(?P<third>\d{2})(?!\w)"
)
# A house or office letter suffix is written glued ("дом 7Б") or hyphenated
# ("дом 7-Б"). A single letter separated by a bare space is the next word, not
# a suffix — usually a preposition or conjunction ("строение 2 в цехе"), so the
# separator may never be whitespace alone.
IDENTIFIER_LETTER_SUFFIX_PATTERN = compile_scan(
    r"(?P<prefix>\b(?:номер|дом|корпус|квартира|строение|владение|"
    r"помещение|офис|этаж|подъезд|комната|палата|литера|место|выход)\s+)"
    r"(?P<number>\d+)(?:\s*[-–—]\s*)?(?P<letter>[A-Za-zА-Яа-яЁё])(?!\w)",
    re.IGNORECASE,
)
VEHICLE_PLATE_PATTERN = compile_scan(
    r"(?P<prefix>\b(?:номер(?:ом|а|у|е)?|госномер|государственный\s+номер)\s+)"
    r"(?P<leading>[A-Za-zА-Яа-яЁё])\s*(?P<number>\d{3})\s*"
    r"(?P<series>[A-Za-zА-Яа-яЁё]{2})\s*(?P<region>\d{2,3})(?!\w)",
    re.IGNORECASE,
)
GLUED_NUMBER_WORD_PATTERN = compile_scan(r"(\d+)([а-яА-ЯёЁa-zA-Z+]{1,})")

GLUED_PREPOSITIONS = {
    "до",
    "по",
    "от",
    "из",
    "с",
    "со",
    "к",
    "ко",
    "в",
    "во",
    "на",
    "у",
    "о",
    "об",
    "обо",
    "при",
    "за",
    "под",
    "над",
    "без",
    "для",
    "ради",
    "через",
    "сквозь",
    "вдоль",
    "мимо",
    "кроме",
    "вместо",
    "против",
    "среди",
    "между",
    "перед",
    "пред",
    "близ",
    "около",
    "свыше",
}
GLUED_NUMERIC_SUFFIXES = NUMERIC_SUFFIXES
_GLUED_SUFFIX_ALTERNATION = "|".join(
    re.escape(suffix)
    for suffix in sorted(NUMERIC_SUFFIXES, key=lambda value: (-len(value), value))
)
EMBEDDED_NUMERIC_SUFFIX_CODE_PATTERN = compile_scan(
    rf"(?<=[а-яА-ЯёЁa-zA-Z])\d+-?(?:{_GLUED_SUFFIX_ALTERNATION})(?!\w)",
    re.IGNORECASE | re.UNICODE,
)
STRUCTURED_NUMERIC_SUFFIX_PATTERN = compile_scan(
    rf"(?:"
    rf"(?<!\w)[а-яА-ЯёЁa-zA-Z][а-яА-ЯёЁa-zA-Z\d_]*\d+"
    rf"-?(?:{_GLUED_SUFFIX_ALTERNATION})(?!\w)"
    rf"|(?<![\w.,-])\d+[.,]\d+-(?:{_GLUED_SUFFIX_ALTERNATION})(?!\w)"
    rf")",
    re.IGNORECASE | re.UNICODE,
)
PHONE_CONTEXT_PATTERN = re.compile(r"\b(?:номер|телефон|позвон\w*)\b", re.IGNORECASE)
#: Надстрочная цифра, приклеенная к слову, — типографский маркер сноски.
#: Подстрочных цифр здесь нет намеренно: сноску ими не набирают, зато ими
#: набирают химические индексы. Слово от трёх букв отсекает и степень после
#: односимвольной переменной, и квадратные единицы («м²», «км²»).
SUPERSCRIPT_FOOTNOTE_PATTERN = compile_scan(
    r"(?P<host>[а-яА-ЯёЁa-zA-Z]{3,})(?P<marker>[⁰¹²³⁴⁵⁶⁷⁸⁹]+)(?!\w)"
)


def classify_glued_numeric_rhs(word: str) -> str:
    """Чем разделить число и приклеенное к нему слово: дефисом, пробелом, никак."""
    word_lower = word.lower()
    if word == "k":
        return "thousand_suffix"
    if word_lower in GLUED_NUMERIC_SUFFIXES or word_lower in {"о", "а"}:
        return "hyphen"
    if is_unit_token(word) or word_lower in GLUED_PREPOSITIONS:
        return "space"

    parsed = first_parse_required(word_lower)
    if "ADJF" in parsed.tag:
        return "hyphen"
    if "NOUN" in parsed.tag:
        return "space"
    if "UNKN" in parsed.tag or word.isascii():
        # Морфология про этот хвост ничего не знает: это либо латиница
        # («100pcs»), либо шум распознавания. Дефис тут был бы утверждением
        # о связи, которого нет, и в латинском случае он доходил до вывода
        # («сто-писиз»), потому что латинские буквы читаются по названиям.
        return "space"
    # Остальные части речи (INFN, PRTF, VERB…) появляются здесь, когда цифра
    # подменила букву при наборе или распознавании: «3аклятые». Дефис даёт
    # «трёхаклятые» — одно слово вместо числа и обрубка, поэтому он остаётся.
    return "hyphen"


def normalize_identifier_letter_suffixes(
    text: str, *, letter_vowel_mode: LetterVowelMode = "single"
) -> str:
    def repl(match: re.Match[str]) -> str:
        letter = match.group("letter")
        vowel_mode = letter_vowel_mode if letter.isascii() else "single"
        letter_name = resolve_letter_name(letter, vowel_mode)
        if letter_name is None:
            return match.group(0)
        return f"{match.group('prefix')}{match.group('number')} {letter_name}"

    return IDENTIFIER_LETTER_SUFFIX_PATTERN.sub(repl, text)


def normalize_vehicle_registration_plates(
    text: str, *, letter_vowel_mode: LetterVowelMode = "single"
) -> str:
    def repl(match: re.Match[str]) -> str:
        leading = match.group("leading")
        vowel_mode = letter_vowel_mode if leading.isascii() else "single"
        letter_name = resolve_letter_name(leading, vowel_mode)
        if letter_name is None:
            return match.group(0)
        return (
            f"{match.group('prefix')}{letter_name} {match.group('number')} "
            f"{match.group('series')} {match.group('region')}"
        )

    return VEHICLE_PLATE_PATTERN.sub(repl, text)


def normalize_phone_numbers(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        # Семь цифр в скобках — это телефон только если о телефоне сказано
        # рядом. Иначе это, например, номер дела или ссылка на строку.
        if not PHONE_CONTEXT_PATTERN.search(left_context(text, match.start(), 48)):
            return match.group(0)
        parts = (
            match.group("country"),
            match.group("area"),
            match.group("first"),
            match.group("second"),
            match.group("third"),
        )
        return ", ".join(parts)

    return PHONE_NUMBER_PATTERN.sub(repl, text)


#: Слово, к которому мог приклеиться номер сноски: строчная кириллица без
#: смешения алфавитов и без заглавной буквы, достаточно длинное, чтобы не быть
#: предлогом или кодом. Границы нужны с двух сторон: без `\A` условию отвечала и
#: заглавная форма, потому что поиск начинался со второй буквы.
_FOOTNOTE_HOST_WORD_PATTERN = compile_scan(r"\A[а-яё]{3,}\Z")
#: Имя собственное с заглавной буквы. Сноску за ним не отвергаем: в книгах
#: корпуса она стоит именно так («Обдориею2», «Кольцом65»). Но и цифру за ним
#: не отбрасываем без положительного признака: «Формула1», «Ковид19»,
#: «Аполлон11» — номенклатурное имя, где число часть названия.
_CAPITALIZED_FOOTNOTE_HOST_PATTERN = compile_scan(r"\A[А-ЯЁ][а-яё]{2,}\Z")
#: Знаки, на которых кончается клауза. Имя с номером — член предложения, и за
#: ним идёт продолжение клаузы; маркер сноски стоит на её краю и своей
#: синтаксической роли не имеет. Это и различает два чтения при заглавном имени.
_FOOTNOTE_CLAUSE_EDGE_CHARS = frozenset(".,;:!?…")


def _standalone_letter_precedes(text: str, start: int) -> bool:
    """Слева через пробел стоит отдельная буква-метка, а не конец слова.

    «A 100K» — буквенно-цифровой код, в котором число принадлежит метке слева;
    «Заработал 100k» — обычное слово и суффикс тысяч. Раньше проверялся
    последний символ предыдущего токена, поэтому режим кода включало любое
    слово слева и «100k» читалось «сто-кей».
    """
    position = start
    while position > 0 and text[position - 1].isspace():
        position -= 1
    if position == start or position == 0:
        return False
    if not text[position - 1].isalpha():
        return False
    before = position - 2
    return before < 0 or not (text[before].isalnum() or text[before] in "-'’")


def _next_word_after(text: str, pos: int) -> str:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    start = pos
    while pos < len(text) and (text[pos].isalpha() or text[pos] in "-'’"):
        pos += 1
    return text[start:pos]


def _glued_digits_are_footnote(
    letters: str, number: str, text: str, end: int
) -> bool:
    """Приклеенные к слову цифры — номер сноски, который нужно опустить.

    Пропущенный пробел перед количеством («человек5 рублей») отличается от
    сноски правым контекстом: за количеством идёт считаемое существительное
    в родительном падеже или единица измерения — такие случаи по-прежнему
    расклеиваются пробелом.

    У слова с заглавной буквы одного положения цифры недостаточно: «Формула1» и
    «Обдориею2» устроены одинаково. Различает их роль числа в клаузе — имя с
    номером её продолжает, маркер сноски стоит на её краю, — поэтому за
    заглавным именем сноска признаётся только перед знаком конца клаузы.
    """
    if len(number) > 2 or number.startswith("0"):
        return False
    if end < len(text) and (text[end].isalnum() or text[end] in "-–—%°"):
        return False
    if _FOOTNOTE_HOST_WORD_PATTERN.search(letters) is None:
        if _CAPITALIZED_FOOTNOTE_HOST_PATTERN.search(letters) is None:
            return False
        if end < len(text) and text[end] not in _FOOTNOTE_CLAUSE_EDGE_CHARS:
            return False
    host_parses = parse_word(letters)
    if any(
        candidate.normal_form in LABEL_NOUN_LEMMAS for candidate in host_parses
    ):
        return False
    # Постпозитивное приблизительное количество стоит после родительного
    # падежа («часа 3», «человек 5») — такое склеивание расклеивается пробелом.
    if any(
        "NOUN" in candidate.tag and candidate.tag.case == "gent"
        for candidate in host_parses
    ):
        return False
    next_word = _next_word_after(text, end)
    if next_word:
        clean = next_word.strip("-'’").lower()
        if clean and (is_unit_token(clean) or resolve_unit_info(clean) is not None):
            return False
        if len(clean) >= 3 and any(
            "NOUN" in candidate.tag
            and candidate.tag.case == "gent"
            and "Abbr" not in candidate.tag
            for candidate in parse_word(clean)
        ):
            return False
    return True


def drop_superscript_footnote_markers(text: str) -> str:
    """Убрать надстрочный номер сноски, приклеенный к слову.

    Надстрочная запись однозначна: это маркер сноски, а не часть числа, —
    поэтому регистр слова здесь роли не играет, и «Государство¹» теряет маркер
    так же, как «пинежане⁸». Обычную цифру так решать нельзя: «Формула1» и
    «Ковид19» формально не отличаются от сноски, и там цифра сохраняется.

    Вызывается до перевода надстрочных цифр в обычные: после него признак
    надстрочности потерян и остаётся только неоднозначная запись.
    """

    def drop(match: re.Match[str]) -> str:
        host = match.group("host")
        if is_unit_token(host) or resolve_unit_info(host) is not None:
            # Единица с надстрочным показателем — степень, а не сноска.
            return match.group(0)
        return host

    return SUPERSCRIPT_FOOTNOTE_PATTERN.sub(drop, text)


def fix_glued_numbers(text: str) -> str:
    codes = PlaceholderAllocator(GLUED_CODES, text)

    def protect_code(match: re.Match[str]) -> str:
        placeholder = codes.allocate(match.group(0))
        return match.group(0) if placeholder is None else placeholder

    def fix_glued(match: re.Match[str]) -> str:
        num, word = match.group(1), match.group(2)
        start = match.start()
        previous_is_letter = start > 0 and text[start - 1].isalpha()
        previous_is_spaced_letter = _standalone_letter_precedes(text, start)
        embedded_in_alphanumeric_code = (
            previous_is_letter or previous_is_spaced_letter
        ) and len(word) == 1
        rhs_kind = (
            "hyphen"
            if embedded_in_alphanumeric_code
            else classify_glued_numeric_rhs(word)
        )
        if rhs_kind == "thousand_suffix":
            return f"{num} тыс"
        if rhs_kind == "space":
            return f"{num} {word}"
        return f"{num}-{word}"

    text = EMBEDDED_NUMERIC_SUFFIX_CODE_PATTERN.sub(protect_code, text)

    def split_leading_letter_number(match: re.Match[str]) -> str:
        token = match.group(0)
        if resolve_unit_info(token) is not None:
            return token
        letters, number = match.group("letters"), match.group("number")
        if _glued_digits_are_footnote(letters, number, text, match.end()):
            return letters
        return f"{letters} {number}"

    text = LEADING_LETTER_DIGIT_PATTERN.sub(split_leading_letter_number, text)
    # Одна замена может склеить новую пару («2х3х4»), поэтому проход повторяется
    # до неподвижной точки. Предел в пять итераций страхует от правила, которое
    # начнёт колебаться между двумя формами.
    previous = None
    iteration = 0
    while previous != text and iteration < 5:
        previous = text
        text = GLUED_NUMBER_WORD_PATTERN.sub(fix_glued, text)
        iteration += 1
    return codes.restore(text)
