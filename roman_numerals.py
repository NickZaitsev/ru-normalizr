from __future__ import annotations

import re

import roman

from .constants import KNOWN_ABBREVIATIONS
from .options import NormalizeOptions

_ROMAN_ABBREVIATION_EXCEPTIONS = frozenset(
    abbr for abbr in KNOWN_ABBREVIATIONS if re.fullmatch(r"[A-Z-]+", abbr)
)


def convert_roman_words(text: str) -> str:
    words = {
        "в.": ("в.", "-й"),
        "век": ("век", "-й"),
        "века": ("века", "-го"),
        "веку": ("веку", "-му"),
        "веке": ("веке", "-м"),
        "веком": ("веком", "-м"),
        "веками": ("веками", "-ми"),
        "веках": ("веках", "-х"),
        "столетие": ("столетие", "-е"),
        "столетия": ("столетия", "-го"),
        "столетию": ("столетию", "-му"),
        "столетии": ("столетии", "-м"),
        "столетием": ("столетием", "-м"),
        "столетиях": ("столетиях", "-х"),
        "глава": ("глава", "-я"),
        "главы": ("главы", "-й"),
        "главе": ("главе", "-й"),
        "главу": ("главу", "-ю"),
        "главой": ("главой", "-й"),
        "главами": ("главами", "-ми"),
        "главах": ("главах", "-х"),
        "раздел": ("раздел", "-й"),
        "раздела": ("раздела", "-го"),
        "разделе": ("разделе", "-м"),
        "разделу": ("разделу", "-му"),
        "часть": ("часть", "-я"),
        "части": ("части", "-й"),
        "частью": ("частью", "-й"),
        "том": ("том", "-й"),
        "тома": ("тома", "-го"),
        "томе": ("томе", "-м"),
        "томом": ("томом", "-м"),
        "книга": ("книга", "-я"),
        "книги": ("книги", "-й"),
        "книге": ("книге", "-й"),
        "книгой": ("книгой", "-й"),
        "квартал": ("квартал", "-й"),
        "квартала": ("квартала", "-го"),
        "кварталу": ("кварталу", "-му"),
        "квартале": ("квартале", "-м"),
        "кварталом": ("кварталом", "-м"),
        "кв.": ("квартал", "-й"),
        "кв": ("квартал", "-й"),
        "в ": ("в ", ""),
    }
    suffixes_regex = "|".join(map(re.escape, words.keys()))
    pattern = rf"\b([IVXLCDM]+)\s*({suffixes_regex})(?!\w)"

    def repl(match: re.Match[str]) -> str:
        try:
            number = roman.fromRoman(match.group(1).upper())
        except roman.InvalidRomanNumeralError:
            return match.group(0)
        target_word, ending = words[match.group(2).lower()]
        return f"{number}{ending} {target_word}"

    return re.sub(pattern, repl, text)


def convert_roman_names(text: str) -> str:
    pattern = r"\b([А-ЯЁ][а-яё]+)\s+(II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV)\b"

    def repl(match: re.Match[str]) -> str:
        try:
            return f"{match.group(1)} {roman.fromRoman(match.group(2))}"
        except roman.InvalidRomanNumeralError:
            return match.group(0)

    return re.sub(pattern, repl, text)


def convert_heading_roman_numerals(text: str) -> str:
    heading_words = (
        "глава",
        "главы",
        "часть",
        "части",
        "раздел",
        "раздела",
        "разделе",
        "том",
        "тома",
        "томе",
        "книга",
        "книги",
        "книге",
    )
    pattern = rf"\b({'|'.join(map(re.escape, heading_words))})\s+([IVXLCDM]+)\b"

    def repl(match: re.Match[str]) -> str:
        if match.group(2) != match.group(2).upper():
            return match.group(0)
        try:
            return f"{match.group(1)} {roman.fromRoman(match.group(2).upper())}"
        except roman.InvalidRomanNumeralError:
            return match.group(0)

    return re.sub(pattern, repl, text, flags=re.IGNORECASE)


def convert_other_roman_numerals(text: str) -> str:
    pattern = r"\b([IVXLCDM]{2,})\b"

    def repl(match: re.Match[str]) -> str:
        token = match.group(1).upper()
        if token in _ROMAN_ABBREVIATION_EXCEPTIONS:
            return match.group(0)
        try:
            return str(roman.fromRoman(token))
        except roman.InvalidRomanNumeralError:
            return match.group(0)

    return re.sub(pattern, repl, text)


def normalize_cyrillic_roman(text: str) -> str:
    cyrillic_to_latin = {
        "Х": "X",
        "х": "X",
        "С": "C",
        "с": "C",
        "І": "I",
        "l": "I",
        "і": "I",
        "М": "M",
        "м": "M",
    }
    pattern = re.compile(r"\b([IVXLCDMХхСсІіМм]{2,})\b")

    def repl(match: re.Match[str]) -> str:
        word = match.group(1)
        if word == word.lower():
            return word
        if not any(char in "ХхСсІіМм" for char in word):
            return word
        latin_word = "".join(cyrillic_to_latin.get(char, char) for char in word).upper()
        try:
            roman.fromRoman(latin_word)
            return latin_word
        except roman.InvalidRomanNumeralError:
            return word

    return pattern.sub(repl, text)


def normalize_roman(text: str, options: NormalizeOptions | None = None) -> str:
    active = options or NormalizeOptions()
    if not active.enable_roman_normalization:
        return text
    text = normalize_cyrillic_roman(text)
    text = convert_roman_words(text)
    text = convert_roman_names(text)
    text = convert_heading_roman_numerals(text)
    text = convert_other_roman_numerals(text)
    return text
