from __future__ import annotations

import re

import roman

from ._morph import get_morph
from .constants import KNOWN_ABBREVIATIONS
from .numerals._helpers import get_numeral_case
from .numerals._hyphen import is_safe_numeric_hyphen_unit
from .options import NormalizeOptions
from .ordinal_utils import (
    choose_noun_parse,
    noun_parse_case,
    render_ordinal,
    render_ordinal_from_noun_parse,
    render_ordinal_from_noun_word,
)
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
_ROMAN_CONTEXT_LEMMAS = frozenset(
    {
        "век",
        "столетие",
        "тысячелетие",
        "глава",
        "раздел",
        "часть",
        "том",
        "книга",
        "квартал",
    }
)
_ROMAN_HEADING_LEMMAS = frozenset(
    {"глава", "раздел", "часть", "том", "книга", "квартал"}
)
_ROMAN_ABBREVIATION_TO_CONTEXT = {
    "в": ("век", "sing"),
    "вв": ("век", "plur"),
    "кв": ("квартал", "sing"),
}
_ROMAN_SHARED_SEPARATOR_PATTERN = re.compile(r"(\s*,\s*|\s+и\s+)")
_ROMAN_CONTEXT_WORD_PATTERN = r"[A-Za-zА-ЯЁа-яё]+\.?"
_ROMAN_CYRILLIC_LOOKALIKE_CHARS = frozenset("ХхСсІіМм")
_ROMAN_LATIN_CHARS = frozenset("IVXLCDM")


def _split_context_word_punctuation(word: str) -> tuple[str, str]:
    if word.endswith(".") and normalize_context_token(word) not in _ROMAN_ABBREVIATION_TO_CONTEXT:
        return word[:-1], "."
    return word, ""


def _resolve_roman_context_noun(
    word: str,
    *,
    allow_abbreviations: bool = True,
) -> tuple[str, object, str | None] | None:
    normalized = normalize_context_token(word)
    if not normalized:
        return None
    if allow_abbreviations and normalized in _ROMAN_ABBREVIATION_TO_CONTEXT:
        lemma, abbreviation_number = _ROMAN_ABBREVIATION_TO_CONTEXT[normalized]
        parse = choose_noun_parse(lemma)
        if parse is None:
            return None
        return lemma, parse, abbreviation_number
    parse = choose_noun_parse(word)
    if parse is None or parse.normal_form not in _ROMAN_CONTEXT_LEMMAS:
        return None
    return parse.normal_form, parse, None


def _render_context_noun_word(
    word: str,
    lemma: str,
    noun_parse,
    *,
    case: str,
    abbreviation_number: str | None,
) -> str:
    if abbreviation_number is None:
        return word
    inflected = noun_parse.inflect({case, abbreviation_number})
    return inflected.word if inflected else lemma


def _render_ordinal_for_context_noun(
    number: int,
    noun_parse,
    *,
    case: str | None = None,
) -> str:
    return render_ordinal(
        number,
        case=case or noun_parse_case(noun_parse),
        gender=noun_parse.tag.gender or "masc",
        inanimate="inan" in noun_parse.tag,
    )


def _resolve_explicit_roman_context_form(
    word: str,
    *,
    case_override: str | None = None,
) -> tuple[object, str, str] | None:
    base_word, trailing_punctuation = _split_context_word_punctuation(word)
    resolved = _resolve_roman_context_noun(base_word)
    if resolved is None:
        return None
    lemma, noun_parse, abbreviation_number = resolved
    case = case_override or ("nomn" if abbreviation_number else noun_parse_case(noun_parse))
    rendered_word = _render_context_noun_word(
        base_word,
        lemma,
        noun_parse,
        case=case,
        abbreviation_number=abbreviation_number,
    )
    return noun_parse, case, f"{rendered_word}{trailing_punctuation}"


def _infer_roman_context_case(
    text: str,
    match: re.Match[str],
    noun_word: str,
) -> str:
    left_context = text[max(0, match.start() - 60) : match.start()]
    right_context = text[match.end() : match.end() + 60]
    left_tokens = simple_tokenize(left_context)
    tokens = left_tokens + ["1", noun_word] + simple_tokenize(right_context)
    return get_numeral_case(tokens, len(left_tokens))


def _resolve_full_noun_case_or_none(
    word: str,
    lemma: str,
) -> str | None:
    cases = {
        ("loct" if "loc2" in candidate.tag else (candidate.tag.case or "nomn"))
        for candidate in get_morph().parse(word.lower())
        if "NOUN" in candidate.tag and candidate.normal_form == lemma
    }
    if len(cases) == 1:
        return next(iter(cases))
    return None


def _resolve_contextual_ordinal_case(
    text: str,
    match: re.Match[str],
    noun_word: str,
    lemma: str,
    *,
    abbreviation_number: str | None,
) -> str:
    if abbreviation_number and lemma == "век":
        return _infer_abbreviated_century_case(text, match)
    if abbreviation_number and lemma == "квартал":
        return _infer_abbreviated_quarter_case(text, match)
    if abbreviation_number:
        return _infer_roman_context_case(text, match, lemma)
    explicit_case = _resolve_full_noun_case_or_none(noun_word, lemma)
    if explicit_case is not None:
        return explicit_case
    return _infer_roman_context_case(text, match, noun_word)


def _infer_abbreviated_century_case(
    text: str,
    match: re.Match[str],
) -> str:
    case = _infer_roman_context_case(text, match, "век")
    if case != "accs":
        return case
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
    if left_word in {"в", "во", "на", "о", "об", "обо", "при"}:
        return "loct"
    return case


def _infer_abbreviated_quarter_case(
    text: str,
    match: re.Match[str],
) -> str:
    case = _infer_roman_context_case(text, match, "квартал")
    if case != "accs":
        return case
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
    if left_word in {"в", "во", "о", "об", "обо", "при"}:
        return "loct"
    return case


def _render_shared_ordinal_in_context(
    text: str,
    match: re.Match[str],
    number: int,
    noun_word: str,
) -> str | None:
    resolved = _resolve_roman_context_noun(noun_word, allow_abbreviations=False)
    if resolved is None:
        return None
    lemma, noun_parse, abbreviation_number = resolved
    case = _resolve_contextual_ordinal_case(
        text,
        match,
        noun_word,
        lemma,
        abbreviation_number=abbreviation_number,
    )
    return _render_ordinal_for_context_noun(number, noun_parse, case=case)


def _render_single_roman_with_context(
    text: str,
    match: re.Match[str],
    number: int,
    noun_word: str,
) -> str | None:
    base_word, trailing_punctuation = _split_context_word_punctuation(noun_word)
    resolved = _resolve_roman_context_noun(base_word)
    if resolved is None:
        return None
    lemma, noun_parse, abbreviation_number = resolved
    case = (
        noun_parse_case(noun_parse)
        if not abbreviation_number
        else _resolve_contextual_ordinal_case(
            text,
            match,
            base_word,
            lemma,
            abbreviation_number=abbreviation_number,
        )
    )
    rendered_noun = _render_context_noun_word(
        base_word,
        lemma,
        noun_parse,
        case=case,
        abbreviation_number=abbreviation_number,
    )
    rendered_ordinal = _render_ordinal_for_context_noun(
        number,
        noun_parse,
        case=case,
    )
    return f"{rendered_ordinal} {rendered_noun}{trailing_punctuation}"


def _render_roman_series_with_context(
    text: str,
    match: re.Match[str],
    series: str,
    noun_word: str,
    *,
    noun_first: bool = False,
) -> str | None:
    base_word, trailing_punctuation = _split_context_word_punctuation(noun_word)
    resolved = _resolve_roman_context_noun(base_word)
    if resolved is None:
        return None
    lemma, noun_parse, abbreviation_number = resolved
    case = _resolve_contextual_ordinal_case(
        text,
        match,
        base_word,
        lemma,
        abbreviation_number=abbreviation_number,
    )
    parts = _ROMAN_SHARED_SEPARATOR_PATTERN.split(series)
    rendered_parts: list[str] = []
    for part in parts:
        if not part:
            continue
        if _ROMAN_SHARED_SEPARATOR_PATTERN.fullmatch(part):
            rendered_parts.append(part)
            continue
        try:
            number = roman.fromRoman(part.upper())
        except roman.InvalidRomanNumeralError:
            return None
        rendered_parts.append(
            _render_ordinal_for_context_noun(number, noun_parse, case=case)
        )
    rendered_series = "".join(rendered_parts)
    rendered_noun = _render_context_noun_word(
        base_word,
        lemma,
        noun_parse,
        case=case,
        abbreviation_number=abbreviation_number,
    )
    if noun_first:
        if noun_word[:1].isupper() and rendered_series:
            rendered_series = rendered_series[:1].upper() + rendered_series[1:]
        return f"{rendered_series} {rendered_noun.lower()}{trailing_punctuation}"
    return f"{rendered_series} {rendered_noun}{trailing_punctuation}"


def _render_roman_hyphen_range_with_context(
    text: str,
    match: re.Match[str],
    left_number: int,
    right_number: int,
    noun_word: str,
    *,
    noun_first: bool = False,
) -> str | None:
    base_word, trailing_punctuation = _split_context_word_punctuation(noun_word)
    resolved = _resolve_roman_context_noun(base_word)
    if resolved is None:
        return None
    lemma, noun_parse, abbreviation_number = resolved
    case = _resolve_contextual_ordinal_case(
        text,
        match,
        base_word,
        lemma,
        abbreviation_number=abbreviation_number,
    )
    rendered_noun = _render_context_noun_word(
        base_word,
        lemma,
        noun_parse,
        case=case,
        abbreviation_number=abbreviation_number,
    )
    left_ordinal = _render_ordinal_for_context_noun(left_number, noun_parse, case=case)
    right_ordinal = _render_ordinal_for_context_noun(right_number, noun_parse, case=case)
    rendered_range = f"{left_ordinal} — {right_ordinal}"
    if noun_first:
        if noun_word[:1].isupper() and rendered_range:
            rendered_range = rendered_range[:1].upper() + rendered_range[1:]
        return f"{rendered_range} {base_word.lower()}{trailing_punctuation}"
    return f"{rendered_range} {rendered_noun}{trailing_punctuation}"


def convert_shared_roman_words(text: str) -> str:
    pattern = re.compile(
        rf"\b(?P<series>[IVXLCDM]+(?:\s*(?:,\s*|\s+и\s+)[IVXLCDM]+)+)\s+(?P<suffix>{_ROMAN_CONTEXT_WORD_PATTERN})(?!\w)"
    )

    def repl(match: re.Match[str]) -> str:
        rendered = _render_roman_series_with_context(
            text,
            match,
            match.group("series"),
            match.group("suffix"),
        )
        return rendered if rendered is not None else match.group(0)

    return pattern.sub(repl, text)


def convert_left_shared_roman_words(text: str) -> str:
    pattern = re.compile(
        rf"\b(?P<suffix>{_ROMAN_CONTEXT_WORD_PATTERN})\s+(?P<series>[IVXLCDM]+(?:\s*(?:,\s*|\s+и\s+)[IVXLCDM]+)+)\b",
        re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        rendered = _render_roman_series_with_context(
            text,
            match,
            match.group("series"),
            match.group("suffix"),
            noun_first=True,
        )
        return rendered if rendered is not None else match.group(0)

    return pattern.sub(repl, text)


def convert_roman_words(text: str) -> str:
    pattern = re.compile(
        rf"\b(?P<roman>[IVXLCDM]+)(?P<spacing>\s*)(?P<word>{_ROMAN_CONTEXT_WORD_PATTERN})(?!\w)",
        re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        try:
            number = roman.fromRoman(match.group("roman").upper())
        except roman.InvalidRomanNumeralError:
            return match.group(0)
        left_hyphen_context = text[max(0, match.start() - 16) : match.start()]
        if re.search(r"[IVXLCDM]+[-–—]\s*$", left_hyphen_context, re.IGNORECASE):
            return match.group(0)
        if not match.group("spacing") and normalize_context_token(match.group("word")) != "в":
            return match.group(0)
        rendered = _render_single_roman_with_context(
            text,
            match,
            number,
            match.group("word"),
        )
        return rendered if rendered is not None else match.group(0)

    return pattern.sub(repl, text)


def convert_roman_century_ranges(text: str) -> str:
    pattern = re.compile(
        r"\b(?P<prep>с|со|от)\s+(?P<left>[IVXLCDM]+)\s+(?P<mid>до|по)\s+(?P<right>[IVXLCDM]+)\s+(?P<word>век(?:а|у|е|ом|ами|ах|ов)?|в\.|вв\.)(?!\w)",
        re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        try:
            left_number = roman.fromRoman(match.group("left").upper())
            right_number = roman.fromRoman(match.group("right").upper())
        except roman.InvalidRomanNumeralError:
            return match.group(0)
        normalized_word = normalize_context_token(match.group("word"))
        if match.group("mid").lower() == "до":
            right_case = "gent"
        elif normalized_word == "вв":
            right_case = "nomn"
        else:
            right_case = None
        resolved = _resolve_explicit_roman_context_form(
            match.group("word"),
            case_override=right_case,
        )
        if resolved is None:
            return match.group(0)
        noun_parse, resolved_right_case, rendered_word = resolved
        return (
            f"{match.group('prep')} {_render_ordinal_for_context_noun(left_number, noun_parse, case='gent')} "
            f"{match.group('mid')} {_render_ordinal_for_context_noun(right_number, noun_parse, case=resolved_right_case)} {rendered_word}"
        )

    return pattern.sub(repl, text)


def convert_hyphenated_roman_ranges(text: str) -> str:
    pattern = re.compile(
        rf"\b(?P<left>[IVXLCDM]+)\s*[-–—]\s*(?P<right>[IVXLCDM]+)\s+(?P<word>{_ROMAN_CONTEXT_WORD_PATTERN})(?!\w)"
    )

    def repl(match: re.Match[str]) -> str:
        try:
            left_number = roman.fromRoman(match.group("left").upper())
            right_number = roman.fromRoman(match.group("right").upper())
        except roman.InvalidRomanNumeralError:
            return match.group(0)
        rendered = _render_roman_hyphen_range_with_context(
            text,
            match,
            left_number,
            right_number,
            match.group("word"),
        )
        return rendered if rendered is not None else match.group(0)

    return pattern.sub(repl, text)


def convert_left_shared_hyphenated_roman_ranges(text: str) -> str:
    pattern = re.compile(
        rf"\b(?P<word>{_ROMAN_CONTEXT_WORD_PATTERN})\s+(?P<left>[IVXLCDM]+)\s*[-–—]\s*(?P<right>[IVXLCDM]+)\b",
        re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        try:
            left_number = roman.fromRoman(match.group("left").upper())
            right_number = roman.fromRoman(match.group("right").upper())
        except roman.InvalidRomanNumeralError:
            return match.group(0)
        rendered = _render_roman_hyphen_range_with_context(
            text,
            match,
            left_number,
            right_number,
            match.group("word"),
            noun_first=True,
        )
        return rendered if rendered is not None else match.group(0)

    return pattern.sub(repl, text)


def convert_roman_names(text: str) -> str:
    pattern = r"\b(?P<name>[А-ЯЁ][а-яё]+)\s+(?P<roman>[IVXLCDM]+)(?![-–—][а-яА-ЯёЁ])\b"

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
        case = noun_parse_case(parse)
        gender = parse.tag.gender or "masc"
        return f"{match.group('name')} {render_ordinal(number, case=case, gender=gender)}"

    return re.sub(pattern, repl, text)


def convert_suffixed_roman_regnal_names(text: str) -> str:
    pattern = re.compile(
        r"\b(?P<name>[А-ЯЁ][а-яё]+)\s+(?P<roman>[IVXLCDM]+)[-–—](?P<suffix>[а-яё]{1,4})\b",
        re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        try:
            number = roman.fromRoman(match.group("roman").upper())
        except roman.InvalidRomanNumeralError:
            return match.group(0)
        noun_parse = choose_noun_parse(match.group("name"), prefer_inanimate=False)
        if noun_parse is None or "anim" not in noun_parse.tag:
            return match.group(0)
        return (
            f"{match.group('name')} "
            f"{render_ordinal_from_noun_parse(number, noun_parse, singularize_plural=True)}"
        )

    return pattern.sub(repl, text)


def convert_heading_roman_numerals(text: str) -> str:
    pattern = re.compile(
        rf"\b(?P<word>{_ROMAN_CONTEXT_WORD_PATTERN})\s+(?P<roman>[IVXLCDM]+)\b",
        re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        if match.group("roman") != match.group("roman").upper():
            return match.group(0)
        resolved = _resolve_roman_context_noun(
            match.group("word"),
            allow_abbreviations=False,
        )
        if resolved is None or resolved[0] not in _ROMAN_HEADING_LEMMAS:
            return match.group(0)
        try:
            ordinal = render_ordinal_from_noun_word(
                roman.fromRoman(match.group("roman").upper()),
                match.group("word"),
            )
            if ordinal is None:
                return f"{match.group('word')} {roman.fromRoman(match.group('roman').upper())}"
            return f"{match.group('word')} {ordinal}"
        except roman.InvalidRomanNumeralError:
            return match.group(0)

    return pattern.sub(repl, text)


def convert_other_roman_numerals(text: str) -> str:
    pattern = r"\b([IVXLCDM]{2,})\b"

    def repl(match: re.Match[str]) -> str:
        token = match.group(1).upper()
        left_hyphen_context = text[max(0, match.start() - 16) : match.start()]
        right_hyphen_context = text[match.end() : match.end() + 16]
        left_hyphen_match = re.search(
            r"([IVXLCDM]+)[-–—]\s*$", left_hyphen_context, re.IGNORECASE
        )
        if left_hyphen_match is not None:
            try:
                roman.fromRoman(left_hyphen_match.group(1).upper())
            except roman.InvalidRomanNumeralError:
                return match.group(0)
        right_hyphen_match = re.match(
            r"\s*[-–—]([IVXLCDM]+)", right_hyphen_context, re.IGNORECASE
        )
        if right_hyphen_match is not None:
            try:
                roman.fromRoman(right_hyphen_match.group(1).upper())
            except roman.InvalidRomanNumeralError:
                return match.group(0)
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
        if not any(char in _ROMAN_LATIN_CHARS for char in word) and all(
            char in _ROMAN_CYRILLIC_LOOKALIKE_CHARS for char in word
        ):
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
    text = convert_hyphenated_roman_ranges(text)
    text = convert_shared_roman_words(text)
    text = convert_left_shared_hyphenated_roman_ranges(text)
    text = convert_left_shared_roman_words(text)
    text = convert_roman_words(text)
    text = convert_suffixed_roman_regnal_names(text)
    text = convert_roman_names(text)
    text = convert_heading_roman_numerals(text)
    text = convert_other_roman_numerals(text)
    return text
