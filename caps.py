from __future__ import annotations

import re

from ._morph import get_morph
from .constants import KNOWN_ABBREVIATIONS
from .preprocess_utils import PARAGRAPH_BREAK_PLACEHOLDER

_LINE_SPLIT_PATTERN = re.compile(rf"(\n|{re.escape(PARAGRAPH_BREAK_PLACEHOLDER)})")
_SENTENCE_START_PATTERN = re.compile(
    r"((?<=[.!?…])(?:[\s\"'«»„“”()\[\]{}]*))([a-zA-Zа-яА-ЯёЁ])"
)


def normalize_first_word_caps(text: str, enabled: bool = True) -> str:
    if not enabled:
        return text

    parts = _LINE_SPLIT_PATTERN.split(text)
    first_word_pattern = re.compile(r"^(\s*)([A-ZА-ЯЁ]{2,})(?=\b|\s|[.,!?;:])")

    for idx in range(0, len(parts), 2):
        line = parts[idx]
        match = first_word_pattern.match(line)
        if match:
            word = match.group(2)
            rest = line[match.end() :]
            has_following_alpha = any(char.isalpha() for char in rest)
            if word not in KNOWN_ABBREVIATIONS and len(word) > 3 and has_following_alpha:
                parts[idx] = match.group(1) + word.capitalize() + line[match.end() :]

    return "".join(parts)


def normalize_sentence_start_caps(text: str, enabled: bool = True) -> str:
    if not enabled:
        return text

    def uppercase_sentence_start(match: re.Match[str]) -> str:
        prefix = match.group(1)
        letter = match.group(2)
        return f"{prefix}{letter.upper()}"

    parts = _LINE_SPLIT_PATTERN.split(text)
    for idx in range(0, len(parts), 2):
        parts[idx] = _SENTENCE_START_PATTERN.sub(uppercase_sentence_start, parts[idx])
    return "".join(parts)


def _is_caps_token(token: str) -> bool:
    """Check if a whitespace-split token is an all-caps non-abbreviation word."""
    letters_only = re.sub(r"[^a-zA-Zа-яА-ЯёЁ]", "", token)
    return (
        len(letters_only) >= 2
        and letters_only.isupper()
        and letters_only not in KNOWN_ABBREVIATIONS
    )


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
    letters = re.sub(r"[^a-zA-Zа-яА-ЯёЁ]", "", token)
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
        letters = re.sub(r"[^a-zA-Zа-яА-ЯёЁ]", "", orig_tok)
        if not letters or not letters.isupper():
            continue
        upper_letters = letters.upper()
        is_known = upper_letters in KNOWN_ABBREVIATIONS
        is_short_abbrev = len(letters) <= 3
        is_real_short_word = False
        if 2 <= len(letters) <= 3:
            parsed = get_morph().parse(letters.lower())[0]
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
            caps_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
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
        parts[idx] = _normalize_inline_caps(line)
    return "".join(parts)
