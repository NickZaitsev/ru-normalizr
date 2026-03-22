from __future__ import annotations

import re

from .constants import CLEANUP_REPLACEMENTS, UNICODE_FRACTIONS

ASCII_DASH_SPACE_PATTERN = re.compile(r" - ")
LETTER_HYPHEN_PATTERN = re.compile(r"(?<=[A-Za-zА-Яа-яЁё])-(?=[A-Za-zА-Яа-яЁё])")
SLASH_FIX_PATTERN = re.compile(r"(?<=[a-zA-Zа-яА-ЯёЁ+])/(?=[a-zA-Zа-яА-ЯёЁ+])")
UNIT_SLASH_PATTERN = re.compile(
    r"\b(?P<left>об|кадров|[kmg]?b|[кмг]?бит|[кмг]?б|байт|[км]?моль|мг|мкг|км|м)/(?P<right>s|с|ч|мин|л|мл|дл)\b",
    re.IGNORECASE,
)
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
    r"(?:(?<=^)|(?<=\n))[ \t]*(?:[*=_~+#\-\xad\u2010-\u2015][ \t]*){3,}(?:(?=$)|(?=\n))"
)
LEGACY_PARAGRAPH_BREAK_DOT_PATTERN = re.compile(
    r"(?P<prev>[^\n.!?…,:;–\-\"'])(?P<break>\n{2,})(?=(?:[\"«„“]\s*)?[А-ЯЁA-Z0-9])"
)
LEGACY_LINEBREAK_DOT_PATTERN = re.compile(
    r"(?P<prev>[^\n.!?…,:;–\-\"'])(?P<break>\n)(?=(?:[\"«„“]\s*)?[А-ЯЁA-Z0-9])"
)
INLINE_LINEBREAK_SPACE_PATTERN = re.compile(
    r"(?<=[^\n])\n(?!(?:[\"«„“]\s*)?[А-ЯЁA-Z0-9])(?=[^\n])"
)
LETTER_HYPHEN_PLACEHOLDER = "\ue000"
NEGATIVE_NUMBER_PLACEHOLDER = "\ue001"
PARAGRAPH_BREAK_PLACEHOLDER = "\ue002"
UNIT_SLASH_PLACEHOLDER = "\ue003"


def protect_unit_slashes(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return (
            f"{match.group('left')}{UNIT_SLASH_PLACEHOLDER}{match.group('right')}"
        )

    return UNIT_SLASH_PATTERN.sub(repl, text)
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
SPACE_INSIDE_QUOTES_PATTERN = re.compile(
    r'(^|[\s([{\-–—,;:])"\s+([^\n"]+?)\s+"(?=$|[\s)\]}\-–—,.;:!?])'
)
SPACE_AFTER_OPEN_QUOTE_PATTERN = re.compile(
    r'(^|[\s([{\-–—,;:])"([ \t]+)(?=\S)'
)
SPACE_BEFORE_CLOSE_QUOTE_PATTERN = re.compile(
    r'(?<=\S)([ \t]+)"(?=$|[\s)\]}\-–—,.;:!?])'
)
ELLIPSIS_SPACE_BEFORE_PATTERN = re.compile(r"[ \t]+(?=…)")
ELLIPSIS_SPACE_AFTER_PATTERN = re.compile(r"(?<=…)(?=[^\s.,;:!?…)\]}\"])\S")
SENTENCE_SPACE_AFTER_PATTERN = re.compile(r"(?<=[.!?…])(?=[\"(«„“]?[A-ZА-ЯЁ])")
CYRILLIC_COMBINING_STRESS_PATTERN = re.compile(
    r"([АЕЁИОУЫЭЮЯаеёиоуыэюя])([\u0300\u0301])"
)
ZERO_WIDTH_FORMATTING_PATTERN = re.compile(r"[\u200B\u200C\u200D\u2060\uFEFF]")
PAGE_ABBREVIATION_PATTERN = re.compile(r"\b[сp]\.\s*(?=\d)", re.IGNORECASE)
APPROXIMATE_ABBREVIATION_PATTERN = re.compile(r"\bок\.\s*(?=\d)", re.IGNORECASE)
ERA_ABBREVIATION_PATTERN = re.compile(
    r"(?<!\w)(?P<abbr>до\s+н\.?\s*э\.?|н\.?\s*э\.?)(?P<tail>\s*)",
    re.IGNORECASE,
)


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
    text = SPACE_INSIDE_QUOTES_PATTERN.sub(r'\1"\2"', text)
    text = SPACE_AFTER_OPEN_QUOTE_PATTERN.sub(r'\1"', text)
    return SPACE_BEFORE_CLOSE_QUOTE_PATTERN.sub('"', text)


def normalize_punctuation_spacing(text: str) -> str:
    text = ELLIPSIS_SPACE_BEFORE_PATTERN.sub("", text)
    text = ELLIPSIS_SPACE_AFTER_PATTERN.sub(lambda m: f" {m.group(0)}", text)
    return SENTENCE_SPACE_AFTER_PATTERN.sub(" ", text)


def normalize_cyrillic_combining_stress_marks(text: str) -> str:
    return CYRILLIC_COMBINING_STRESS_PATTERN.sub(r"+\1", text)


def remove_zero_width_formatting(text: str) -> str:
    return ZERO_WIDTH_FORMATTING_PATTERN.sub("", text)


def normalize_era_abbreviations(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        abbr = match.group("abbr")
        tail = match.group("tail")
        expansion = "до нашей эры" if abbr.lower().startswith("до") else "нашей эры"
        rest = text[match.end() :]
        stripped_rest = rest.lstrip()
        keep_terminal_dot = False
        if abbr.rstrip().endswith("."):
            keep_terminal_dot = (
                not stripped_rest
                or "\n" in tail
                or (stripped_rest[:1] and stripped_rest[:1].isupper())
            )
            if (
                stripped_rest[:1] in '"»”)]}'
                and len(stripped_rest) > 1
                and stripped_rest[1:2].isupper()
            ):
                keep_terminal_dot = True
        return f"{expansion}{'.' if keep_terminal_dot else ''}{tail}"

    return ERA_ABBREVIATION_PATTERN.sub(repl, text)


def normalize_numeric_abbreviations(text: str) -> str:
    text = PAGE_ABBREVIATION_PATTERN.sub("страница ", text)
    text = APPROXIMATE_ABBREVIATION_PATTERN.sub("около ", text)
    return normalize_era_abbreviations(text)


def normalize_explicit_dashes(text: str) -> str:
    return text.translate(str.maketrans({"–": "—", "―": "—"}))


def normalize_spaced_ascii_hyphens(text: str) -> str:
    return ASCII_DASH_SPACE_PATTERN.sub(" — ", text)


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
    return text


def _insert_boundary_dot(match: re.Match[str]) -> str:
    return f"{match.group('prev')}.{match.group('break')}"


def normalize_linebreaks(text: str, keep_paragraph_placeholders: bool = False) -> str:
    del keep_paragraph_placeholders
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = TRAILING_SPACE_BEFORE_NEWLINE_PATTERN.sub("\n", text)
    text = LEADING_SPACE_AFTER_NEWLINE_PATTERN.sub("\n", text)
    text = EXCESSIVE_LINEBREAKS_PATTERN.sub("\n\n", text)
    text = LEGACY_PARAGRAPH_BREAK_DOT_PATTERN.sub(_insert_boundary_dot, text)
    text = LEGACY_LINEBREAK_DOT_PATTERN.sub(_insert_boundary_dot, text)
    text = INLINE_LINEBREAK_SPACE_PATTERN.sub(" ", text)
    return text


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
    text: str,
    keep_paragraph_placeholders: bool = False,
    ignore_interval: tuple[int, int] | None = None,
) -> str:
    pairs = {"[": "]", "<": ">", "(": ")", "{": "}", "«": "»"}

    def repl(match: re.Match[str]) -> str:
        opener, content, closer = match.group(1), match.group(2), match.group(3)
        if pairs.get(opener) != closer:
            return match.group(0)
        stripped = content.strip()
        if classify_bracketed_numeric_content(content) == "reference":
            if ignore_interval is not None and stripped.isdigit():
                value = int(stripped)
                min_val, max_val = ignore_interval
                if min_val <= value <= max_val:
                    return match.group(0)
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
