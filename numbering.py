from __future__ import annotations

import re

import num2words
import roman

from .options import NormalizeOptions
from .preprocess_utils import classify_bracketed_numeric_content


def num_to_word(value: int) -> str:
    try:
        return num2words.num2words(value, lang="ru")
    except Exception:
        return str(value)


def roman_to_word(roman_str: str) -> str:
    try:
        return num_to_word(roman.fromRoman(roman_str.upper()))
    except roman.InvalidRomanNumeralError:
        return roman_str


def convert_numeric_sequence(sequence: str) -> str:
    clean_seq = sequence.rstrip(".")
    if re.match(r"^[IVXLCDM]+$", clean_seq, re.IGNORECASE):
        return roman_to_word(clean_seq)
    parts = [part for part in clean_seq.split(".") if part]
    words: list[str] = []
    for part in parts:
        try:
            words.append(num_to_word(int(part)))
        except ValueError:
            words.append(part)
    return " точка ".join(words)


def convert_line_numbering(text: str) -> str:
    def convert_numbering(match: re.Match[str]) -> str:
        converted = convert_numeric_sequence(match.group(2)).capitalize()
        return f"{match.group(1)}{converted}.{match.group(3)}"

    pattern = r"^([ \t]*)([IVXLCDM]+\.|[\d]+(?:\.[\d]+)*\.)([ \t]*)"
    return "\n".join(
        re.sub(pattern, convert_numbering, line, flags=re.IGNORECASE)
        for line in text.split("\n")
    )


def convert_bracketed_numbers(
    text: str, options: NormalizeOptions | None = None
) -> str:
    active = options or NormalizeOptions()
    pattern = r"([(\[{])\s*([^()\[\]{}]+?)\*?\s*([)\]}])"
    pairs = {"(": ")", "[": "]", "{": "}"}

    def repl(match: re.Match[str]) -> str:
        opener, sequence, closer = match.group(1), match.group(2), match.group(3)
        if pairs.get(opener) != closer:
            return match.group(0)

        stripped = sequence.strip()
        if re.match(r"^[IVXLCDM]+$", stripped, re.IGNORECASE):
            kind = "reference"
        else:
            kind = classify_bracketed_numeric_content(stripped)
        if kind != "reference":
            return match.group(0)

        should_remove = False
        if active.remove_links:
            should_remove = True
            try:
                if stripped.isdigit():
                    value = int(stripped)
                    min_val, max_val = active.remove_links_ignore_interval
                    if min_val <= value <= max_val:
                        should_remove = False
            except Exception:
                pass
        if should_remove:
            return ""
        return match.group(0)

    return re.sub(pattern, repl, text, flags=re.IGNORECASE)
