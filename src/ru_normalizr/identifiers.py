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
#: смешения алфавитов, достаточно длинное, чтобы не быть предлогом или кодом.
_FOOTNOTE_HOST_WORD_PATTERN = compile_scan(r"[а-яё]{3,}\Z")


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
    """
    if len(number) > 2 or number.startswith("0"):
        return False
    if end < len(text) and (text[end].isalnum() or text[end] in "-–—%°"):
        return False
    if _FOOTNOTE_HOST_WORD_PATTERN.search(letters) is None:
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


def fix_glued_numbers(text: str) -> str:
    codes = PlaceholderAllocator(GLUED_CODES, text)

    def protect_code(match: re.Match[str]) -> str:
        placeholder = codes.allocate(match.group(0))
        return match.group(0) if placeholder is None else placeholder

    def fix_glued(match: re.Match[str]) -> str:
        num, word = match.group(1), match.group(2)
        start = match.start()
        previous_is_letter = start > 0 and text[start - 1].isalpha()
        previous_is_spaced_letter = (
            start > 1 and text[start - 1].isspace() and text[start - 2].isalpha()
        )
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
