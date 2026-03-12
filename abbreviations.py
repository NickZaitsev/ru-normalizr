from __future__ import annotations

import re

from ._morph import get_morph
from .abbreviation_rules import ABBREVIATION_PATTERNS
from .constants import (
    ABBREV_DOTTED_PATTERN,
    ABBREV_MAX_LEN_EN,
    ABBREV_MAX_LEN_RU,
    ABBREV_MIN_LEN,
    ABBREV_SOLID_PATTERN,
    EN_LETTER_NAMES,
    KNOWN_ABBREVIATIONS,
    PERSON_INITIALS_SURNAME_PATTERN,
    PERSON_SURNAME_INITIALS_PATTERN,
    REAL_WORD_POS,
    RU_LETTER_NAMES,
    RU_VOWELS,
    RUSSIAN_NAME_TOKEN,
)
from .options import NormalizeOptions

_ETC_ABBREVIATION_PATTERN = re.compile(
    r"(?<!\w)(?P<abbr>т\.?\s*[дп]\.)(?P<tail>\s*)(?!\w)", re.IGNORECASE
)


def _expand_contextual_etc_abbreviations(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        raw_abbr = match.group("abbr")
        tail = match.group("tail")
        normalized_abbr = re.sub(r"\s+", "", raw_abbr).lower()
        expansion = "так далее" if "д" in normalized_abbr else "тому подобное"

        rest = text[match.end() :]
        next_char = rest[:1]
        stripped_rest = rest.lstrip()
        next_significant = stripped_rest[:1]
        has_linebreak_before_next = "\n" in tail or (
            "\n" in rest and rest[: len(rest) - len(stripped_rest)] != ""
        )

        keep_terminal_dot = (
            not stripped_rest
            or has_linebreak_before_next
            or (next_significant and next_significant.isupper())
        )

        if (
            next_char in '"»”)]}'
            and len(stripped_rest) > 1
            and stripped_rest[1:2].isupper()
        ):
            keep_terminal_dot = True

        return f"{expansion}{'.' if keep_terminal_dot else ''}{tail}"

    return _ETC_ABBREVIATION_PATTERN.sub(repl, text)


def expand_person_initials(text: str) -> str:
    def initial_name(ch: str) -> str:
        return RU_LETTER_NAMES.get(ch.upper(), ch.lower())

    def choose_tail(match_end: int) -> tuple[bool, str]:
        tail = text[match_end:]
        stripped = tail.lstrip()
        if not stripped:
            return True, ""
        if stripped[0] in ".!?…":
            return True, ""
        if stripped[0] in ",;:":
            return False, ""

        if re.match(rf"^\s+{RUSSIAN_NAME_TOKEN}\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.", tail):
            return False, ","
        if stripped[0].islower() or stripped[0].isdigit():
            return False, ","
        return True, ""

    def repl_surname_initials(match):
        surname = match.group("surname")
        i1 = initial_name(match.group("i1"))
        i2 = initial_name(match.group("i2"))
        is_final, non_final_tail = choose_tail(match.end())
        if is_final:
            terminal = (
                ""
                if text[match.end() :].lstrip().startswith((".", "!", "?", "…"))
                else "."
            )
            return f"{surname} {i1} {i2}{terminal}"
        return f"{surname}, {i1}, {i2}{non_final_tail}"

    def repl_initials_surname(match):
        i1 = initial_name(match.group("i1"))
        i2 = initial_name(match.group("i2"))
        surname = match.group("surname")
        is_final, non_final_tail = choose_tail(match.end())
        if is_final:
            terminal = (
                ""
                if text[match.end() :].lstrip().startswith((".", "!", "?", "…"))
                else "."
            )
            return f"{i1} {i2} {surname}{terminal}"
        return f"{i1}, {i2}, {surname}{non_final_tail}"

    text = PERSON_SURNAME_INITIALS_PATTERN.sub(repl_surname_initials, text)
    return PERSON_INITIALS_SURNAME_PATTERN.sub(repl_initials_surname, text)


def expand_letter_abbreviations(text: str) -> str:
    def expand_token(token: str, is_dotted: bool) -> str:
        tail_dot = token.endswith(".")
        letters = [char for char in token if char.isalpha()]
        if len(letters) < ABBREV_MIN_LEN:
            return token

        letters_upper = [char.upper() for char in letters]
        joined_key = "".join(letters_upper)
        if joined_key in KNOWN_ABBREVIATIONS:
            custom_reading = KNOWN_ABBREVIATIONS[joined_key]
            return (
                custom_reading + "."
                if custom_reading and tail_dot
                else custom_reading or token
            )

        if all(char in RU_LETTER_NAMES for char in letters_upper):
            if not is_dotted:
                parsed = get_morph().parse(joined_key.lower())[0]
                if parsed.tag.POS in REAL_WORD_POS:
                    return token
            if not is_dotted:
                if len(letters_upper) > ABBREV_MAX_LEN_RU:
                    return token
                if sum(1 for char in letters_upper if char in RU_VOWELS) > 1:
                    return token
            names = [RU_LETTER_NAMES[char] for char in letters_upper]
        elif all(char in EN_LETTER_NAMES for char in letters_upper):
            if not is_dotted and len(letters_upper) > ABBREV_MAX_LEN_EN:
                return token
            names = [EN_LETTER_NAMES[char] for char in letters_upper]
        else:
            return token

        expanded = " ".join(names)
        return expanded + "." if tail_dot else expanded

    text = ABBREV_DOTTED_PATTERN.sub(lambda m: expand_token(m.group(0), True), text)
    return ABBREV_SOLID_PATTERN.sub(lambda m: expand_token(m.group(0), False), text)


def expand_abbreviations(text: str, options: NormalizeOptions | None = None) -> str:
    active = options or NormalizeOptions()
    if not active.enable_abbreviation_expansion:
        return text
    if active.enable_contextual_abbreviation_expansion:
        text = _expand_contextual_etc_abbreviations(text)
        for pattern, replacement in ABBREVIATION_PATTERNS:
            text = pattern.sub(replacement, text)
    if active.enable_initials_expansion:
        text = expand_person_initials(text)
    if active.enable_letter_abbreviation_expansion:
        text = expand_letter_abbreviations(text)
    return text
