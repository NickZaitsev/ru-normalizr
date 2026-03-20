from __future__ import annotations

import re

from ._constants import (
    CURRENCY_STANDALONE,
    GREEK_LETTERS,
    MATH_SYMBOLS,
    STANDALONE_CURRENCY_PATTERN,
)

MATH_EXPRESSION_CHAR_PATTERN = re.compile(r"[0-9A-Za-zА-Яа-яЁё_,.%()+\-/*^°№]")
APPROXIMATE_NUMBER_PATTERN = re.compile(r"(?<!\w)~\s*(?=(?:\ue001)?\d)")


def _extract_math_expression_side(text: str, start: int, step: int) -> str:
    chars: list[str] = []
    idx = start
    saw_non_space = False
    while 0 <= idx < len(text):
        char = text[idx]
        if char.isspace() or MATH_EXPRESSION_CHAR_PATTERN.fullmatch(char):
            chars.append(char)
            if not char.isspace():
                saw_non_space = True
            idx += step
            continue
        break
    if not saw_non_space:
        return ""
    side = "".join(reversed(chars)) if step < 0 else "".join(chars)
    return side.strip()


def _contains_digit(fragment: str) -> bool:
    return any(char.isdigit() for char in fragment)


def _should_read_equals_as_ravno(text: str, idx: int) -> bool:
    prev_char = text[idx - 1] if idx > 0 else ""
    next_char = text[idx + 1] if idx + 1 < len(text) else ""
    if prev_char in "<>!=" or next_char in "<>!=":
        return False

    left = _extract_math_expression_side(text, idx - 1, -1)
    right = _extract_math_expression_side(text, idx + 1, 1)
    if not left or not right:
        return False
    return _contains_digit(left) or _contains_digit(right)


def _normalize_contextual_equals(text: str) -> str:
    if "=" not in text:
        return text

    parts: list[str] = []
    last_index = 0
    for match in re.finditer(r"=", text):
        idx = match.start()
        if not _should_read_equals_as_ravno(text, idx):
            continue
        parts.append(text[last_index:idx])
        parts.append(" равно ")
        last_index = idx + 1

    if last_index == 0:
        return text

    parts.append(text[last_index:])
    return "".join(parts)


def normalize_greek_letters(text: str) -> str:
    greek_chars = "".join(re.escape(char) for char in GREEK_LETTERS)
    pattern = re.compile(rf"[{greek_chars}]+")

    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        if len(token) != 1:
            return token
        return GREEK_LETTERS.get(token, token)

    return pattern.sub(repl, text)


def normalize_math_symbols(text: str) -> str:
    text = _normalize_contextual_equals(text)
    text = APPROXIMATE_NUMBER_PATTERN.sub("примерно ", text)
    for char, replacement in MATH_SYMBOLS.items():
        text = text.replace(char, replacement)
    return text


def normalize_standalone_currency(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return CURRENCY_STANDALONE[match.group(0)]

    return STANDALONE_CURRENCY_PATTERN.sub(repl, text)
