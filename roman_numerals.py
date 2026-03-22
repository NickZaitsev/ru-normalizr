from __future__ import annotations

import re

import num2words
import roman

from ._morph import get_morph
from .constants import KNOWN_ABBREVIATIONS
from .numerals._helpers import get_numeral_case
from .numerals._hyphen import is_safe_numeric_hyphen_unit
from .options import NormalizeOptions
from .text_context import normalize_context_token, simple_tokenize

_ROMAN_ABBREVIATION_EXCEPTIONS = frozenset(
    {
        *(abbr for abbr in KNOWN_ABBREVIATIONS if re.fullmatch(r"[A-Z-]+", abbr)),
        "DC",
        "MD",
        "CV",
        "CI",
        "DI",
        "MC",
        "CM",
        "MM",
    }
)

_CENTURY_CASE_TO_ENDING = {
    "nomn": "-й",
    "accs": "-й",
    "gent": "-го",
    "datv": "-му",
    "ablt": "-м",
    "loct": "-м",
}

_REGNAL_CASE_CONTEXT = {
    "в": "loct",
    "во": "loct",
    "на": "loct",
    "о": "loct",
    "об": "loct",
    "обо": "loct",
    "при": "loct",
    "к": "datv",
    "ко": "datv",
    "по": "datv",
    "с": "gent",
    "со": "gent",
    "из": "gent",
    "от": "gent",
    "до": "gent",
    "у": "gent",
    "без": "gent",
    "для": "gent",
    "около": "gent",
    "после": "gent",
    "ради": "gent",
    "между": "ablt",
    "над": "ablt",
    "под": "ablt",
    "перед": "ablt",
    "пред": "ablt",
}
_REGNAL_CASE_TO_NUM2WORDS = {
    "nomn": "nominative",
    "gent": "genitive",
    "datv": "dative",
    "accs": "accusative",
    "ablt": "instrumental",
    "loct": "prepositional",
}
_REGNAL_GENDER_TO_NUM2WORDS = {"masc": "m", "femn": "f", "neut": "n"}
_CENTURY_WORD_TO_CASE = {
    "в.": "nomn",
    "век": "nomn",
    "века": "gent",
    "веку": "datv",
    "веке": "loct",
    "веком": "ablt",
    "веками": "ablt",
    "веках": "loct",
}
_CENTURY_CASE_TO_WORD_FORM = {
    "nomn": "век",
    "gent": "века",
    "datv": "веку",
    "accs": "век",
    "ablt": "веком",
    "loct": "веке",
}


def _expand_century_abbreviation(text: str, match: re.Match[str], number: int) -> str:
    morph = get_morph()
    left_context = text[max(0, match.start() - 60) : match.start()]
    right_context = text[match.end() : match.end() + 60]
    tokens = simple_tokenize(left_context) + [str(number), "век"] + simple_tokenize(right_context)
    case = get_numeral_case(tokens, len(simple_tokenize(left_context)))
    ending = _CENTURY_CASE_TO_ENDING.get(case, "-й")
    parsed = morph.parse("век")[0]
    noun_form = parsed.inflect({case, "sing"})
    century_word = noun_form.word if noun_form else "век"
    return f"{number}{ending} {century_word}"


def convert_roman_words(text: str) -> str:
    words = {
        "в.": ("век", "-й"),
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
        "тысячелетие": ("тысячелетие", "-е"),
        "тысячелетия": ("тысячелетия", "-го"),
        "тысячелетию": ("тысячелетию", "-му"),
        "тысячелетии": ("тысячелетии", "-м"),
        "тысячелетием": ("тысячелетием", "-м"),
        "тысячелетиях": ("тысячелетиях", "-х"),
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
        "в": ("век", "-й"),
    }
    suffixes_regex = "|".join(map(re.escape, words.keys()))
    pattern = rf"\b([IVXLCDM]+)\s*({suffixes_regex})(?!\w)"

    def repl(match: re.Match[str]) -> str:
        try:
            number = roman.fromRoman(match.group(1).upper())
        except roman.InvalidRomanNumeralError:
            return match.group(0)
        matched_suffix = match.group(2).lower()
        if matched_suffix in {"в.", "в"}:
            return _expand_century_abbreviation(text, match, number)
        target_word, ending = words[matched_suffix]
        return f"{number}{ending} {target_word}"

    return re.sub(pattern, repl, text)


def convert_roman_century_ranges(text: str) -> str:
    pattern = re.compile(
        r"\b(?P<prep>с|со|от)\s+(?P<left>[IVXLCDM]+)\s+(?P<mid>до|по)\s+(?P<right>[IVXLCDM]+)\s+(?P<word>век(?:а|у|е|ом|ами|ах)?|в\.)(?!\w)",
        re.IGNORECASE,
    )
    case_map = {
        "nomn": "nominative",
        "gent": "genitive",
        "datv": "dative",
        "accs": "accusative",
        "ablt": "instrumental",
        "loct": "prepositional",
    }

    def ordinal(number: int, case: str) -> str:
        try:
            return num2words.num2words(
                number, lang="ru", to="ordinal", case=case_map.get(case, "nominative")
            )
        except Exception:
            return num2words.num2words(number, lang="ru", to="ordinal")

    def repl(match: re.Match[str]) -> str:
        try:
            left_number = roman.fromRoman(match.group("left").upper())
            right_number = roman.fromRoman(match.group("right").upper())
        except roman.InvalidRomanNumeralError:
            return match.group(0)
        word = match.group("word").lower()
        right_case = _CENTURY_WORD_TO_CASE.get(word, "nomn")
        century_word = (
            _CENTURY_CASE_TO_WORD_FORM.get(right_case, "век")
            if word == "в."
            else match.group("word")
        )
        return (
            f"{match.group('prep')} {ordinal(left_number, 'gent')} "
            f"{match.group('mid')} {ordinal(right_number, right_case)} {century_word}"
        )

    return pattern.sub(repl, text)


def convert_roman_names(text: str) -> str:
    pattern = r"\b(?P<name>[А-ЯЁ][а-яё]+)\s+(?P<roman>[IVXLCDM]+)\b"

    def pick_name_parse(match: re.Match[str]):
        name = match.group("name")
        parses = [
            candidate
            for candidate in get_morph().parse(name)
            if "NOUN" in candidate.tag
            and "anim" in candidate.tag
            and any(
                marker in candidate.tag for marker in ("Name", "Surn", "Patr")
            )
        ]
        if not parses:
            return None

        left_context = text[max(0, match.start() - 40) : match.start()]
        left_tokens = simple_tokenize(left_context)
        left_word = next(
            (
                normalize_context_token(token)
                for token in reversed(left_tokens)
                if any(char.isalpha() for char in token)
            ),
            "",
        )
        target_case = _REGNAL_CASE_CONTEXT.get(left_word)
        if target_case is not None:
            for candidate in parses:
                candidate_case = "loct" if "loc2" in candidate.tag else candidate.tag.case
                if candidate_case == target_case:
                    return candidate
        return parses[0]

    def repl(match: re.Match[str]) -> str:
        try:
            number = roman.fromRoman(match.group("roman"))
        except roman.InvalidRomanNumeralError:
            return match.group(0)
        parse = pick_name_parse(match)
        if parse is None:
            return match.group(0)
        case = "loct" if "loc2" in parse.tag else (parse.tag.case or "nomn")
        gender = parse.tag.gender or "masc"
        kwargs = {
            "lang": "ru",
            "to": "ordinal",
            "case": _REGNAL_CASE_TO_NUM2WORDS.get(case, "nominative"),
            "gender": _REGNAL_GENDER_TO_NUM2WORDS.get(gender, "m"),
        }
        try:
            ordinal = num2words.num2words(number, **kwargs)
        except Exception:
            ordinal = num2words.num2words(number, lang="ru", to="ordinal")
        return f"{match.group('name')} {ordinal}"

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
        if word != word.upper():
            return word
        if is_safe_numeric_hyphen_unit(word):
            left_context = text[max(0, match.start() - 32) : match.start()]
            if re.search(r"\d+(?:[.,]\d+)?\s*[-–—]?\s*$", left_context):
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
    text = convert_roman_century_ranges(text)
    text = convert_roman_words(text)
    text = convert_roman_names(text)
    text = convert_heading_roman_numerals(text)
    text = convert_other_roman_numerals(text)
    return text
