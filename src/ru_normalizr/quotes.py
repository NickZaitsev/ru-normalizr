"""Кавычки, гомоглифы и невидимая разметка — чистка формы, а не смысла.

Эти правила не меняют слов: они приводят к одному виду то, что типографика и
буферы обмена размножили в десяток начертаний. Отдельный модуль нужен потому, что
порядок внутри группы важен (сначала форма кавычки, потом её отбивка), а с
остальным препроцессом эти правила не связаны.
"""

from __future__ import annotations

import re

from ._morph import word_is_known
from .text_scan import compile_scan

SPACE_INSIDE_QUOTES_PATTERN = compile_scan(
    r'(^|[\s([{\-–—,;:])"\s+([^\n"]+?)\s+"(?=$|[\s)\]}\-–—,.;:!?])'
)
SPACE_AFTER_OPEN_QUOTE_PATTERN = compile_scan(
    r'(^|[\s([{\-–—,;:])"([ \t]+)(?=\S)'
)
SPACE_BEFORE_CLOSE_QUOTE_PATTERN = compile_scan(
    r'(?<=\S)([ \t]+)"(?=$|[\s)\]}\-–—,.;:!?])'
)
OPEN_SINGLE_QUOTE_PATTERN = compile_scan(
    r"(?P<prefix>^|[\s([{\-–—,;:])(?P<quote>[‘‚‛‹])(?=\S)"
)
CLOSE_SINGLE_QUOTE_PATTERN = compile_scan(
    r"(?<=\S)(?P<quote>[’›])(?=$|[\s)\]}\-–—,.;:!?])"
)

CYRILLIC_COMBINING_STRESS_PATTERN = compile_scan(
    r"([АЕЁИОУЫЭЮЯаеёиоуыэюя])([\u0300\u0301])"
)
ZERO_WIDTH_FORMATTING_PATTERN = compile_scan(r"[\u200B\u200C\u200D\u2060\uFEFF]")
_LETTERSPACED_LETTER = "\u0410-\u042F\u0430-\u044F\u0401\u0451\u0462\u0463\u0406\u0456\u0472\u0473\u0474\u0475"
LETTERSPACED_UNDERSCORE_PATTERN = compile_scan(
    rf"(?<![A-Za-z\d_{_LETTERSPACED_LETTER}])"
    rf"[{_LETTERSPACED_LETTER}](?:_[{_LETTERSPACED_LETTER}]){{2,}}"
    rf"(?![A-Za-z\d_{_LETTERSPACED_LETTER}])"
)

QUOTE_PAIR_REPLACEMENTS = (("``", '"'), ("''", '"'), ("‘‘", '"'), ("’’", '"'), ("´´", '"'))
QUOTE_SHAPE_PATTERN = compile_scan(
    r"``|''|‘‘|’’|´´|[«»“”„‟〝〞＂]|"
    r"(?<![A-Za-zА-Яа-яЁё])[‘‚‛‹]|[’›](?![A-Za-zА-Яа-яЁё])"
)
QUOTE_VARIANT_PATTERN = compile_scan(r"[«»“”„‟〝〞＂]")
QUOTE_CANDIDATES = frozenset('"\'`´«»‘’‚‛‹›“”„‟〝〞＂')


def _tighten_quote_spacing(text: str) -> str:
    """Убрать пробелы, отделяющие кавычку от того, что она обнимает."""
    text = SPACE_INSIDE_QUOTES_PATTERN.sub(r'\1"\2"', text)
    text = SPACE_AFTER_OPEN_QUOTE_PATTERN.sub(r'\1"', text)
    return SPACE_BEFORE_CLOSE_QUOTE_PATTERN.sub('"', text)


def normalize_ascii_quote_pairs(text: str) -> str:
    if QUOTE_CANDIDATES.isdisjoint(text):
        return text
    # Непрямых кавычек нет — приводить форму нечему, остаётся только отбивка.
    if QUOTE_SHAPE_PATTERN.search(text) is None:
        return _tighten_quote_spacing(text)
    for old, new in QUOTE_PAIR_REPLACEMENTS:
        text = text.replace(old, new)
    text = QUOTE_VARIANT_PATTERN.sub('"', text)
    text = OPEN_SINGLE_QUOTE_PATTERN.sub(r'\g<prefix>"', text)
    text = CLOSE_SINGLE_QUOTE_PATTERN.sub('"', text)
    return _tighten_quote_spacing(text)


#: Latin letters drawn with the same glyph as a Cyrillic one. Only these can be
#: a layout slip inside a Russian word; «l», «d» or «v» have no Cyrillic twin and
#: mark a genuinely Latin token.
_LATIN_TO_CYRILLIC_HOMOGLYPHS = str.maketrans(
    {
        "A": "А",
        "B": "В",
        "C": "С",
        "E": "Е",
        "H": "Н",
        "K": "К",
        "M": "М",
        "O": "О",
        "P": "Р",
        "T": "Т",
        "X": "Х",
        "Y": "У",
        "a": "а",
        "c": "с",
        "e": "е",
        "o": "о",
        "p": "р",
        "x": "х",
        "y": "у",
    }
)
_HOMOGLYPH_LATIN_LETTERS = frozenset("ABCEHKMOPTXYacepoxy")
_HOMOGLYPH_LATIN_PATTERN = compile_scan(f"[{''.join(sorted(_HOMOGLYPH_LATIN_LETTERS))}]")
#: A word that mixes both scripts. Both lookaheads are required so the C-level
#: scan rejects ordinary words without entering the Python callback: a full pass
#: over every word of a book-sized text is otherwise the most expensive step of
#: the preprocessing stage.
_WORD_CHARS = "A-Za-zА-Яа-яЁё+"
MIXED_SCRIPT_WORD_PATTERN = compile_scan(
    rf"(?<![{_WORD_CHARS}])"
    rf"(?=[{_WORD_CHARS}]*[ABCEHKMOPTXYacepoxy])"
    rf"(?=[{_WORD_CHARS}]*[А-Яа-яЁё])"
    rf"[{_WORD_CHARS}]{{2,}}"
)


def normalize_script_homoglyphs(text: str) -> str:
    """Repair a Latin homoglyph typed inside a Russian word.

    «Bсе» is «Все» with a Latin B — a typesetting defect, not a Latin token, and
    reading it as a letter name gave «бисе». The repair only applies when every
    Latin letter of the word has a Cyrillic twin and the substituted word is in
    the dictionary, so a genuinely mixed identifier is left alone.
    """
    if _HOMOGLYPH_LATIN_PATTERN.search(text) is None:
        return text

    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        latin = [char for char in word if char.isascii() and char.isalpha()]
        if not latin or any(char not in _HOMOGLYPH_LATIN_LETTERS for char in latin):
            return word
        if not any(not char.isascii() and char.isalpha() for char in word):
            return word
        candidate = word.translate(_LATIN_TO_CYRILLIC_HOMOGLYPHS)
        if not word_is_known(candidate.replace("+", "")):
            return word
        return candidate

    return MIXED_SCRIPT_WORD_PATTERN.sub(repl, text)


def normalize_cyrillic_combining_stress_marks(text: str) -> str:
    return CYRILLIC_COMBINING_STRESS_PATTERN.sub(r"+\1", text)


def remove_zero_width_formatting(text: str) -> str:
    return ZERO_WIDTH_FORMATTING_PATTERN.sub("", text)


def collapse_letterspaced_emphasis(text: str) -> str:
    """Собрать слово из разрядки подчёркиваниями («в_н_е» → «вне»).

    Разрядка — типографское выделение: каждая буква слова отбита
    подчёркиванием. Узор строго «одиночная кириллическая буква между
    подчёркиваниями» на весь токен, поэтому идентификаторы snake_case с
    многобуквенными сегментами («имя_файла») под правило не попадают.
    """
    if "_" not in text:
        return text
    return LETTERSPACED_UNDERSCORE_PATTERN.sub(
        lambda match: match.group(0).replace("_", ""), text
    )
