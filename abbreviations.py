from __future__ import annotations

import re

from ._morph import get_morph
from .abbreviation_rules import (
    ABBREVIATION_PATTERNS,
    ADJECTIVE_ABBREVIATION_EXPANSIONS,
)
from .constants import (
    ABBREV_DOTTED_PATTERN,
    ABBREV_MAX_LEN_EN,
    ABBREV_MAX_LEN_RU,
    ABBREV_MIN_LEN,
    ABBREV_SOLID_PATTERN,
    EN_LETTER_NAMES,
    KNOWN_ABBREVIATIONS,
    PERSON_INITIALS_SURNAME_PATTERN,
    PERSON_SINGLE_INITIAL_SURNAME_PATTERN,
    PERSON_SURNAME_INITIALS_PATTERN,
    PERSON_SURNAME_SINGLE_INITIAL_PATTERN,
    REAL_WORD_POS,
    RU_LETTER_NAMES,
    RU_VOWELS,
    RUSSIAN_NAME_TOKEN,
)
from .numerals._helpers import safe_inflect
from .options import NormalizeOptions

_ETC_ABBREVIATION_PATTERN = re.compile(
    r"(?<!\w)(?P<abbr>т\.?\s*[дп]\.)(?P<tail>\s*)(?!\w)", re.IGNORECASE
)
_ADJECTIVE_ABBREVIATION_WORD = (
    r"(?!и\b|или\b|либо\b|да\b|но\b|а\b)[А-ЯЁа-яё-]+"
)
_ADJECTIVE_ABBREVIATION_PATTERN = re.compile(
    rf"(?<!\w)(?P<abbr>{'|'.join(sorted((re.escape(key) for key in ADJECTIVE_ABBREVIATION_EXPANSIONS), key=len, reverse=True))})"
    rf"(?P<space>\s+)(?P<phrase>{_ADJECTIVE_ABBREVIATION_WORD}(?:\s+{_ADJECTIVE_ABBREVIATION_WORD}){{0,2}})",
    re.IGNORECASE,
)
_WORD_AMPERSAND_PATTERN = re.compile(
    r"(?P<left>[A-Za-zА-Яа-яЁё]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)*)\s*&\s*(?P<right>[A-Za-zА-Яа-яЁё]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)*)"
)
_SINGLE_TOKEN_EN_LETTER_NAMES = frozenset(
    value.lower() for value in EN_LETTER_NAMES.values() if " " not in value
)
_LANGUAGE_ORIGIN_ABBREVIATIONS = {
    "англ.": "английский",
    "руск.": "русский",
    "рус.": "русский",
    "немецк.": "немецкий",
    "нем.": "немецкий",
    "франц.": "французский",
    "греч.": "греческий",
    "латин.": "латинский",
    "лат.": "латинский",
}
_LANGUAGE_ORIGIN_PATTERN = re.compile(
    rf"(?<!\w)(?P<prep>от|из|с|со)\s+(?P<abbr>{'|'.join(sorted((re.escape(key) for key in _LANGUAGE_ORIGIN_ABBREVIATIONS), key=len, reverse=True))})"
    r"(?P<space>\s+)(?P<word>[^\s.,;:!?()\"\[\]{}«»]+)",
    re.IGNORECASE,
)
_FOLLOWING_NAME_TOKEN_PATTERN = re.compile(
    rf"^\s+(?P<token>{RUSSIAN_NAME_TOKEN})(?![A-Za-zА-Яа-яЁё])"
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


def _expand_contextual_adjective_abbreviations(text: str) -> str:
    morph = get_morph()

    def choose_head_noun(phrase: str):
        for word in phrase.split():
            parsed = morph.parse(word.lower())
            noun_candidate = next(
                (candidate for candidate in parsed if "NOUN" in candidate.tag),
                None,
            )
            if noun_candidate is not None:
                return noun_candidate
        return None

    def inflect_adjective(lemma: str, noun_parse) -> str:
        parsed = morph.parse(lemma)
        adjective_parse = next(
            (
                candidate
                for candidate in parsed
                if candidate.tag.POS in {"ADJF", "PRTF"}
            ),
            parsed[0] if parsed else None,
        )
        if adjective_parse is None:
            return lemma

        noun_case = "loct" if "loc2" in noun_parse.tag else noun_parse.tag.case
        if noun_case is None:
            return lemma
        target_tags = {noun_case}
        if "plur" in noun_parse.tag:
            target_tags.add("plur")
        else:
            target_tags.add("sing")
            if noun_parse.tag.gender:
                target_tags.add(noun_parse.tag.gender)
        return safe_inflect(
            adjective_parse,
            target_tags,
            fallback_word=lemma,
            pos_filter={"ADJF", "PRTF"},
        )

    def repl(match: re.Match[str]) -> str:
        abbr = match.group("abbr")
        phrase = match.group("phrase")
        if abbr.lower() in _LANGUAGE_ORIGIN_ABBREVIATIONS and phrase[:1].isupper():
            return match.group(0)
        lemma = ADJECTIVE_ABBREVIATION_EXPANSIONS.get(abbr.lower())
        if lemma is None:
            return match.group(0)
        noun_parse = choose_head_noun(phrase)
        if noun_parse is None:
            return match.group(0)
        expanded = inflect_adjective(lemma, noun_parse)
        if abbr[:1].isupper():
            expanded = expanded[:1].upper() + expanded[1:]
        return f"{expanded}{match.group('space')}{phrase}"

    return _ADJECTIVE_ABBREVIATION_PATTERN.sub(repl, text)


def _expand_language_origin_abbreviations(text: str) -> str:
    morph = get_morph()

    def has_non_cyrillic_word(word: str) -> bool:
        letters = [char for char in word if char.isalpha()]
        return bool(letters) and not any(
            ("А" <= char <= "я") or char in "Ёё" for char in letters
        )

    def inflect_language_lemma(lemma: str) -> str:
        parsed = next(
            (
                candidate
                for candidate in morph.parse(lemma)
                if candidate.tag.POS in {"ADJF", "PRTF"}
            ),
            None,
        )
        if parsed is None:
            return lemma
        return safe_inflect(
            parsed,
            {"gent", "sing", "masc"},
            fallback_word=lemma,
            pos_filter={"ADJF", "PRTF"},
        )

    def repl(match: re.Match[str]) -> str:
        word = match.group("word")
        if not has_non_cyrillic_word(word):
            return match.group(0)
        lemma = _LANGUAGE_ORIGIN_ABBREVIATIONS.get(match.group("abbr").lower())
        if lemma is None:
            return match.group(0)
        return (
            f"{match.group('prep')} {inflect_language_lemma(lemma)}"
            f"{match.group('space')}{word}"
        )

    return _LANGUAGE_ORIGIN_PATTERN.sub(repl, text)


def expand_person_initials(text: str) -> str:
    def initial_name(ch: str) -> str:
        return RU_LETTER_NAMES.get(ch.upper(), ch.lower())

    def candidate_grammemes(candidate) -> frozenset[str]:
        grammemes = getattr(candidate.tag, "grammemes", None)
        if grammemes is None:
            return frozenset()
        return frozenset(grammemes)

    def is_likely_person_name_token(token: str) -> bool:
        parsed = get_morph().parse(token)
        if not parsed:
            return True
        meaningful = [
            candidate
            for candidate in parsed
            if "PNCT" not in candidate_grammemes(candidate)
        ]
        if not meaningful:
            return True
        if any(
            marker in candidate_grammemes(candidate)
            for candidate in meaningful
            for marker in ("Surn", "Name", "Patr")
        ):
            return True
        top_candidates = meaningful[:3]
        if top_candidates and all(
            "Geox" in candidate_grammemes(candidate) for candidate in top_candidates
        ):
            return False
        if top_candidates and all(
            "Abbr" in candidate_grammemes(candidate) for candidate in top_candidates
        ):
            return False
        return True

    def is_confident_person_name_token(token: str) -> bool:
        parsed = get_morph().parse(token)
        if not parsed:
            return False
        meaningful = [
            candidate
            for candidate in parsed
            if "PNCT" not in candidate_grammemes(candidate)
        ]
        return any(
            marker in candidate_grammemes(candidate)
            for candidate in meaningful
            for marker in ("Surn", "Name", "Patr")
        )

    def has_following_person_name_token(match_end: int) -> bool:
        match = _FOLLOWING_NAME_TOKEN_PATTERN.match(text[match_end:])
        if match is None:
            return False
        return is_confident_person_name_token(match.group("token"))

    def choose_tail(match_end: int) -> tuple[bool, str]:
        tail = text[match_end:]
        stripped = tail.lstrip()
        if not stripped:
            return True, ""
        if stripped[0] in ".!?…":
            return True, ""
        if stripped[0].islower() or stripped[0].isdigit():
            return False, ""
        return True, ""

    def repl_surname_initials(match):
        if has_following_person_name_token(match.end()):
            return match.group(0)
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

    def repl_surname_single_initial(match):
        if has_following_person_name_token(match.end()):
            return match.group(0)
        surname = match.group("surname")
        if not is_likely_person_name_token(surname):
            return match.group(0)
        i1 = initial_name(match.group("i1"))
        is_final, non_final_tail = choose_tail(match.end())
        if is_final:
            terminal = (
                ""
                if text[match.end() :].lstrip().startswith((".", "!", "?", "…"))
                else "."
            )
            return f"{surname} {i1}{terminal}"
        return f"{surname}, {i1},{non_final_tail}"

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
        return f"{i1} {i2} {surname}{non_final_tail}"

    def repl_single_initial_surname(match):
        surname = match.group("surname")
        if not is_likely_person_name_token(surname):
            return match.group(0)
        i1 = initial_name(match.group("i1"))
        is_final, non_final_tail = choose_tail(match.end())
        if is_final:
            terminal = (
                ""
                if text[match.end() :].lstrip().startswith((".", "!", "?", "…"))
                else "."
            )
            return f"{i1} {surname}{terminal}"
        return f"{i1} {surname}{non_final_tail}"

    text = PERSON_SURNAME_INITIALS_PATTERN.sub(repl_surname_initials, text)
    text = PERSON_INITIALS_SURNAME_PATTERN.sub(repl_initials_surname, text)
    text = PERSON_SURNAME_SINGLE_INITIAL_PATTERN.sub(repl_surname_single_initial, text)
    return PERSON_SINGLE_INITIAL_SURNAME_PATTERN.sub(repl_single_initial_surname, text)


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
                if parsed.tag.POS in REAL_WORD_POS and "Abbr" not in parsed.tag:
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


def _normalize_contextual_ampersands(
    text: str, options: NormalizeOptions | None = None
) -> str:
    active = options or NormalizeOptions()

    def has_ascii_letters(token: str) -> bool:
        return any("A" <= char <= "Z" or "a" <= char <= "z" for char in token)

    def has_cyrillic_letters(token: str) -> bool:
        return any(("А" <= char <= "я") or char in "Ёё" for char in token)

    def is_english_letter_name(token: str) -> bool:
        return token.lower() in _SINGLE_TOKEN_EN_LETTER_NAMES

    def repl(match: re.Match[str]) -> str:
        left = match.group("left")
        right = match.group("right")
        left_has_ascii = has_ascii_letters(left)
        right_has_ascii = has_ascii_letters(right)
        left_is_english = is_english_letter_name(left)
        right_is_english = is_english_letter_name(right)

        brand_like_context = (
            (left_has_ascii and right_has_ascii and active.enable_latinization)
            or (left_is_english and right_is_english)
            or (left_is_english and right_has_ascii)
            or (left_has_ascii and right_is_english)
        )
        if brand_like_context:
            return f"{left} энд {right}"

        if left_has_ascii and right_has_ascii:
            return f"{left} & {right}"

        if (
            has_cyrillic_letters(left)
            or has_cyrillic_letters(right)
            or left_is_english
            or right_is_english
        ):
            return f"{left} и {right}"

        return match.group(0)

    return _WORD_AMPERSAND_PATTERN.sub(repl, text)


def expand_abbreviations(text: str, options: NormalizeOptions | None = None) -> str:
    active = options or NormalizeOptions()
    if not active.enable_abbreviation_expansion:
        return text
    text = _expand_language_origin_abbreviations(text)
    if active.enable_contextual_abbreviation_expansion:
        text = _expand_contextual_etc_abbreviations(text)
        text = _expand_contextual_adjective_abbreviations(text)
        for pattern, replacement in ABBREVIATION_PATTERNS:
            text = pattern.sub(replacement, text)
    if active.enable_initials_expansion:
        text = expand_person_initials(text)
    if active.enable_letter_abbreviation_expansion:
        text = expand_letter_abbreviations(text)
    return _normalize_contextual_ampersands(text, active)
