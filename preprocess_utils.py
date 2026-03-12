from __future__ import annotations

import re

from .constants import CLEANUP_REPLACEMENTS, UNICODE_FRACTIONS

DASH_SPACE_PATTERN = re.compile(r" - ")
LETTER_HYPHEN_PATTERN = re.compile(r"(?<=[A-Za-zА-Яа-яЁё])-(?=[A-Za-zА-Яа-яЁё])")
SLASH_FIX_PATTERN = re.compile(r"(?<=[a-zA-Zа-яА-ЯёЁ+])/(?=[a-zA-Zа-яА-ЯёЁ+])")
NUMBER_CLEANUP_PATTERN = re.compile(
    r"(?<!\d)(?:\d{1,3}(?:[ \u00A0\u2009\u202F]\d{3})+|\d+)(?:[,\.]\d+)?(?!\d)"
)
BRACKETED_NUMERIC_PATTERN = re.compile(r"([\[<({«])\s*([^()\[\]{}<>«»]+?)\s*([\]>)}»])")
SPACE_BEFORE_PUNCT_PATTERN = re.compile(r"[ \t]+([,.;:!?])")
MULTI_SPACE_PATTERN = re.compile(r"[ \t]{2,}")
SPACE_BEFORE_CLOSE_BRACKET_PATTERN = re.compile(r"[ \t]+([\)\]\}])")
SPACE_AFTER_OPEN_BRACKET_PATTERN = re.compile(r"([\(\[\{])[ \t]+")
TRAILING_SPACE_BEFORE_NEWLINE_PATTERN = re.compile(r"[ \t]+\n")
LEADING_SPACE_AFTER_NEWLINE_PATTERN = re.compile(r"\n[ \t]+")
EXCESSIVE_LINEBREAKS_PATTERN = re.compile(r"\n{2,}")
DECORATIVE_SEPARATOR_PATTERN = re.compile(
    r"(?:(?<=^)|(?<=\n)|(?<=\uE002))[ \t]*(?:[*=_~+#\-\xad\u2010-\u2015][ \t]*){3,}(?:(?=$)|(?=\n)|(?=\uE002))"
)
LEGACY_LINEBREAK_DOT_PATTERN = re.compile(
    r"(?<=[^\n.!?…,:;–\-\"'])(\n)(?=[А-ЯЁA-Z0-9])"
)
INLINE_LINEBREAK_SPACE_PATTERN = re.compile(r"(?<=[^\n])\n(?=[^А-ЯЁA-Z0-9\n])")
LETTER_HYPHEN_PLACEHOLDER = "\ue000"
NEGATIVE_NUMBER_PLACEHOLDER = "\ue001"
PARAGRAPH_BREAK_PLACEHOLDER = "\ue002"
LEGACY_PLACEHOLDER_BREAK_DOT_PATTERN = re.compile(
    rf"(?<=[^\n.!?…,:;–\-\"'])({re.escape(PARAGRAPH_BREAK_PLACEHOLDER)}+)(?=[А-ЯЁA-Z0-9])"
)
YEARS_AGO_ABBREVIATION_PATTERN = re.compile(
    r"(?<!\w)л\.?\s*н\.(?P<tail>\s*)",
    re.IGNORECASE,
)
UNARY_MINUS_NUMBER_PATTERN = re.compile(
    r"(?P<prefix>^|[(\[{«]|(?<!\d)\s)(?P<sign>[−-])(?P<space>\s*)(?P<number>\d+(?:[.,]\d+)?)"
)
THOUSANDS_SEPARATORS = " \u00a0\u2009\u202f"
SIGNED_COMMA_NUMBER_PATTERN = re.compile(
    r"^[−-]?(?:\d{1,3}(?:[" + THOUSANDS_SEPARATORS + r"]\d{3})+|\d+),\d+$"
)
SIGNED_INTEGER_WITH_UNIT_PATTERN = re.compile(
    r"^[−-]?(?:\d{1,3}(?:[" + THOUSANDS_SEPARATORS + r"]\d{3})+|\d+)(?:,\d+)?\s*"
    r"(?:[%‰°]|[₽$€£¥]|[A-Za-zА-Яа-яЁё]+(?:\s+[A-Za-zА-Яа-яЁё.]+)?)$"
)
INTEGER_LIST_PATTERN = re.compile(r"^\d+(?:\s*,\s*\d+)+$")
INTEGER_RANGE_PATTERN = re.compile(r"^\d+\s*[–—-]\s*\d+$")
SPACE_INSIDE_QUOTES_PATTERN = re.compile(r'"\s+([^\n"]+?)\s+"')
SPACE_AFTER_OPEN_QUOTE_PATTERN = re.compile(r'(^|[\s([{\-–—,;:])"([ \t]+)(?=\S)')
SPACE_BEFORE_CLOSE_QUOTE_PATTERN = re.compile(
    r'(?<=\S)([ \t]+)"(?=$|[\s)\]}\-–—,.;:!?])'
)
ELLIPSIS_SPACE_BEFORE_PATTERN = re.compile(r"[ \t]+(?=…)")
ELLIPSIS_SPACE_AFTER_PATTERN = re.compile(r"(?<=…)(?=[^\s.,;:!?…)\]}\"])\S")
SENTENCE_SPACE_AFTER_PATTERN = re.compile(r"(?<=[.!?…])(?=[\"(«„“]?[A-ZА-ЯЁ])")


def normalize_ascii_quote_pairs(text: str) -> str:
    replacements = (
        ("``", '"'),
        ("''", '"'),
        ("‘‘", '"'),
        ("’’", '"'),
        ("´´", '"'),
        ("«", '"'),
        ("»", '"'),
        ("“", '"'),
        ("”", '"'),
        ("„", '"'),
        ("‟", '"'),
        ("〝", '"'),
        ("〞", '"'),
        ("＂", '"'),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    text = SPACE_INSIDE_QUOTES_PATTERN.sub(r'"\1"', text)
    text = SPACE_AFTER_OPEN_QUOTE_PATTERN.sub(r'\1"', text)
    return SPACE_BEFORE_CLOSE_QUOTE_PATTERN.sub('"', text)


def normalize_punctuation_spacing(text: str) -> str:
    text = ELLIPSIS_SPACE_BEFORE_PATTERN.sub("", text)
    text = ELLIPSIS_SPACE_AFTER_PATTERN.sub(lambda m: f" {m.group(0)}", text)
    return SENTENCE_SPACE_AFTER_PATTERN.sub(" ", text)


def normalize_spaced_hyphens(text: str) -> str:
    return DASH_SPACE_PATTERN.sub(" — ", text)


def protect_negative_numbers(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        number = match.group("number")
        return f"{prefix}{NEGATIVE_NUMBER_PLACEHOLDER}{number}"

    return UNARY_MINUS_NUMBER_PATTERN.sub(repl, text)


def protect_letter_hyphens(text: str) -> str:
    return LETTER_HYPHEN_PATTERN.sub(LETTER_HYPHEN_PLACEHOLDER, text)


def restore_letter_hyphens(text: str) -> str:
    return text.replace(LETTER_HYPHEN_PLACEHOLDER, "-")


def expand_years_ago_abbreviation(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        tail = match.group("tail")
        next_char_index = match.end()
        next_char = text[next_char_index] if next_char_index < len(text) else ""
        if (
            not next_char
            or next_char == "\n"
            or next_char.isalnum()
            or next_char.isalpha()
        ):
            return f"лет назад.{tail}"
        return f"лет назад{tail}"

    return YEARS_AGO_ABBREVIATION_PATTERN.sub(repl, text)


def normalize_unicode_fractions(text: str) -> str:
    for char, replacement in UNICODE_FRACTIONS.items():
        text = text.replace(char, replacement)
    return text


def apply_cleanup_replacements(text: str) -> str:
    for old, new in CLEANUP_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def restore_paragraph_breaks(text: str) -> str:
    text = re.sub(
        rf"{PARAGRAPH_BREAK_PLACEHOLDER}[ \t]*\.[ \t]*{PARAGRAPH_BREAK_PLACEHOLDER}",
        f".{PARAGRAPH_BREAK_PLACEHOLDER}{PARAGRAPH_BREAK_PLACEHOLDER}",
        text,
    )
    text = re.sub(
        rf"[ \t]*{PARAGRAPH_BREAK_PLACEHOLDER}[ \t]*", PARAGRAPH_BREAK_PLACEHOLDER, text
    )
    return text.replace(PARAGRAPH_BREAK_PLACEHOLDER, "\n")


def normalize_linebreaks(text: str, keep_paragraph_placeholders: bool = False) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = TRAILING_SPACE_BEFORE_NEWLINE_PATTERN.sub("\n", text)
    text = LEADING_SPACE_AFTER_NEWLINE_PATTERN.sub("\n", text)
    paragraph_break = (
        PARAGRAPH_BREAK_PLACEHOLDER if keep_paragraph_placeholders else "\n"
    )
    text = EXCESSIVE_LINEBREAKS_PATTERN.sub(paragraph_break, text)
    if keep_paragraph_placeholders:
        text = LEGACY_PLACEHOLDER_BREAK_DOT_PATTERN.sub(r".\1", text)
    text = LEGACY_LINEBREAK_DOT_PATTERN.sub(r".\1", text)
    text = INLINE_LINEBREAK_SPACE_PATTERN.sub(" ", text)
    return text if keep_paragraph_placeholders else restore_paragraph_breaks(text)


def remove_decorative_separators(text: str) -> str:
    return DECORATIVE_SEPARATOR_PATTERN.sub("", text)


def classify_bracketed_numeric_content(content: str) -> str:
    stripped = content.strip()
    if not stripped:
        return "other"

    if SIGNED_COMMA_NUMBER_PATTERN.fullmatch(stripped):
        return "numeric"

    if SIGNED_INTEGER_WITH_UNIT_PATTERN.fullmatch(stripped):
        return "numeric"

    if stripped.isdigit():
        return "reference"

    if INTEGER_RANGE_PATTERN.fullmatch(stripped):
        return "reference"

    if INTEGER_LIST_PATTERN.fullmatch(stripped):
        if stripped.count(",") == 1 and ", " not in stripped and " ," not in stripped:
            return "numeric"
        return "reference"

    if "." in stripped:
        parts = stripped.split(".")
        if all(part.isdigit() for part in parts):
            if len(parts) >= 3:
                return "reference"
            if len(parts) == 2:
                left, right = parts
                if len(left) <= 2 and len(right) <= 3:
                    return "reference"
                return "numeric"

    return "other"


def remove_numeric_footnotes(
    text: str, keep_paragraph_placeholders: bool = False
) -> str:
    pairs = {"[": "]", "<": ">", "(": ")", "{": "}", "«": "»"}

    def repl(match: re.Match[str]) -> str:
        opener, content, closer = match.group(1), match.group(2), match.group(3)
        if pairs.get(opener) != closer:
            return match.group(0)
        if classify_bracketed_numeric_content(content) == "reference":
            return ""
        return match.group(0)

    text = BRACKETED_NUMERIC_PATTERN.sub(repl, text)
    text = SPACE_BEFORE_PUNCT_PATTERN.sub(r"\1", text)
    text = MULTI_SPACE_PATTERN.sub(" ", text)
    text = SPACE_BEFORE_CLOSE_BRACKET_PATTERN.sub(r"\1", text)
    text = SPACE_AFTER_OPEN_BRACKET_PATTERN.sub(r"\1", text)
    return normalize_linebreaks(
        text, keep_paragraph_placeholders=keep_paragraph_placeholders
    ).strip()


def clean_numbers(text: str) -> str:
    def repl_spaces(match: re.Match[str]) -> str:
        return (
            match.group(0)
            .replace(" ", "")
            .replace("\u00a0", "")
            .replace("\u2009", "")
            .replace("\u202f", "")
        )

    text = NUMBER_CLEANUP_PATTERN.sub(repl_spaces, text)
    text = re.sub(
        r"(?<!\d)(\d{1,3}(?:\.\d{3}){2,})(?!\d)",
        lambda m: m.group(1).replace(".", ""),
        text,
    )
    text = re.sub(
        r"(?<!\d)(\d{1,3}\.\d{3})(?=,\d+)", lambda m: m.group(1).replace(".", ""), text
    )
    unit_lookahead = (
        r"(?=\s*(?:[₽$€£¥%‰]|\b(?:руб|долл|евро|тыс|млн|млрд|г|кг|т|м|км|шт)\b))"
    )
    return re.sub(
        r"(?<!\d)(\d{1,3}\.\d{3})" + unit_lookahead,
        lambda m: m.group(1).replace(".", ""),
        text,
    )
