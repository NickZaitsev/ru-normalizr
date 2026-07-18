from __future__ import annotations

import re

from ._morph import parse_word
from .constants import KNOWN_ABBREVIATIONS

_LINE_SPLIT_PATTERN = re.compile(r"(\n)")
_FIRST_WORD_CAPS_PATTERN = re.compile(
    r"^([^\S\r\n]*)([A-ZА-ЯЁ]{2,})(?=\b|\s|[.,!?;:])", re.MULTILINE
)
_SENTENCE_START_PATTERN = re.compile(
    r"(?P<punct>[.!?…])(?P<prefix>(?:(?=[^\r\n])\s|[\"'«»„“”()\[\]{}])*)"
    r"(?P<letter>[a-zA-Zа-яА-ЯёЁ])"
)
_CAPS_CONNECTORS = {"А", "В", "И", "К", "О", "С", "У"}


def normalize_first_word_caps(text: str, enabled: bool = True) -> str:
    if not enabled:
        return text

    def normalize_line_start(match: re.Match[str]) -> str:
        line_end = text.find("\n", match.end())
        rest = text[match.end() : line_end if line_end >= 0 else len(text)]
        word = match.group(2)
        if (
            word not in KNOWN_ABBREVIATIONS
            and len(word) > 3
            and any(char.isalpha() or char.isdigit() for char in rest)
        ):
            return match.group(1) + word.capitalize()
        return match.group(0)

    return _FIRST_WORD_CAPS_PATTERN.sub(normalize_line_start, text)


def normalize_sentence_start_caps(text: str, enabled: bool = True) -> str:
    if not enabled:
        return text

    def uppercase_sentence_start(match: re.Match[str]) -> str:
        punctuation = match.group("punct")
        prefix = match.group("prefix")
        letter = match.group("letter")
        if (
            punctuation in {"?", "!"}
            and any(quote in prefix for quote in ('"', "'", "»", "”"))
            and letter.islower()
        ):
            return match.group(0)
        return f"{punctuation}{prefix}{letter.upper()}"

    return _SENTENCE_START_PATTERN.sub(uppercase_sentence_start, text)


def _letters_only(token: str) -> str:
    return "".join(
        char
        for char in token
        if ("A" <= char <= "Z")
        or ("a" <= char <= "z")
        or ("А" <= char <= "я")
        or char in "Ёё"
    )


def _is_caps_token(token: str) -> bool:
    """Check if a whitespace-split token is an all-caps non-abbreviation word."""
    if not token.isupper():
        return False
    letters_only = _letters_only(token)
    return (
        len(letters_only) >= 2
        and letters_only.isupper()
        and letters_only not in KNOWN_ABBREVIATIONS
    )


def _is_caps_connector(token: str) -> bool:
    letters_only = _letters_only(token)
    return letters_only in _CAPS_CONNECTORS


def _normalize_inline_caps(line: str) -> str:
    tokens = re.split(r"(\s+)", line)

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.isspace():
            i += 1
            continue

        if _is_caps_token(token):
            run_start = i
            caps_count = 1
            j = i + 1
            while j < len(tokens):
                if tokens[j].isspace():
                    j += 1
                    continue
                if _is_caps_token(tokens[j]):
                    caps_count += 1
                    j += 1
                elif _is_caps_connector(tokens[j]):
                    j += 1
                else:
                    break
            if caps_count >= 2:
                first_word = True
                for k in range(run_start, j):
                    if not tokens[k].isspace():
                        if first_word:
                            tokens[k] = _lowercase_preserve_abbrevs(
                                tokens[k]
                            ).capitalize()
                            first_word = False
                        else:
                            tokens[k] = _lowercase_preserve_abbrevs(tokens[k])
            i = j
        else:
            i += 1
    return "".join(tokens)


def _lowercase_preserve_abbrevs(token: str) -> str:
    """Lowercase a token, but preserve known abbreviation substrings."""
    letters = _letters_only(token)
    if letters.isupper() and letters in KNOWN_ABBREVIATIONS:
        return token
    return token.lower()


def _restore_known_abbreviations(original: str, lowered: str) -> str:
    """After lowering, restore tokens that were originally known abbreviations."""
    orig_tokens = re.split(r"(\s+)", original)
    low_tokens = re.split(r"(\s+)", lowered)
    if len(orig_tokens) != len(low_tokens):
        return lowered
    vowels = set("АЕЁИОУЫЭЮЯ")
    for i, orig_tok in enumerate(orig_tokens):
        letters = _letters_only(orig_tok)
        if not letters or not letters.isupper():
            continue
        upper_letters = letters.upper()
        is_known = upper_letters in KNOWN_ABBREVIATIONS
        is_short_abbrev = len(letters) <= 3
        is_real_short_word = False
        if 2 <= len(letters) <= 3:
            parsed = parse_word(letters.lower())[0]
            is_real_short_word = parsed.tag.POS is not None
        is_consonant_heavy = (
            len(letters) == 4 and sum(1 for c in upper_letters if c in vowels) <= 1
        )
        if is_known or ((is_short_abbrev and not is_real_short_word)) or is_consonant_heavy:
            low_tokens[i] = orig_tok
    return "".join(low_tokens)


def normalize_caps_lines(
    text: str, enabled: bool = True, caps_threshold: float = 0.8, min_length: int = 10
) -> str:
    if not enabled:
        return text

    parts = _LINE_SPLIT_PATTERN.split(text)
    for idx in range(0, len(parts), 2):
        line = parts[idx]
        letters = [char for char in line if char.isalpha()]
        if len(letters) >= min_length:
            uppercase_count = sum(1 for char in letters if char.isupper())
            caps_ratio = uppercase_count / len(letters)
            if caps_ratio >= caps_threshold:
                stripped = line.strip()
                lowered = stripped.lower()
                lowered = _restore_known_abbreviations(stripped, lowered)
                for ci, ch in enumerate(lowered):
                    if ch.isalpha():
                        lowered = lowered[:ci] + ch.upper() + lowered[ci + 1 :]
                        break
                parts[idx] = (
                    line[: len(line) - len(line.lstrip())]
                    + lowered
                    + line[len(line.rstrip()) :]
                )
                continue
            if uppercase_count < 4:
                continue
        elif sum(1 for char in letters if char.isupper()) < 4:
            continue
        parts[idx] = _normalize_inline_caps(line)
    return "".join(parts)
