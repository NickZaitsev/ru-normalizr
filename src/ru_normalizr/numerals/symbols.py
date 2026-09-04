from __future__ import annotations

import re

from ..ordinal_utils import render_ordinal
from ..placeholders import NEGATIVE_NUMBER_PLACEHOLDER
from ..text_scan import compile_scan
from ._constants import (
    CURRENCY_STANDALONE,
    GREEK_LETTERS,
    MATH_SYMBOLS,
    STANDALONE_CURRENCY_PATTERN,
    UNIT_TOKEN_FRAGMENT,
    resolve_unit_info,
)
from .unit_rendering import render_unit_expression

MATH_EXPRESSION_CHAR_PATTERN = compile_scan(r"[0-9A-Za-zА-Яа-яЁё_,.%()+\-/*^°№]")
APPROXIMATE_NUMBER_PATTERN = compile_scan(
    rf"(?<!\w)~\s*(?=(?:{re.escape(NEGATIVE_NUMBER_PLACEHOLDER)})?\d)"
)
BINARY_MATH_OPERATOR_PATTERN = compile_scan(
    r"(?<=\d)\s*(?P<operator>[+−^*])\s*(?=\d)"
)
BINARY_MATH_OPERATOR_READINGS = {
    "+": " плюс ",
    "−": " минус ",
    "^": " в степени ",
    # Between two digits an asterisk has no competing meaning, unlike "-"
    # (ranges) or "/" (dates, fractions, unit denominators), so it needs no
    # equation context. Runs of asterisks are consumed by the preprocess
    # separator rules before this point and never have digits on both sides.
    "*": " умножить на ",
}
# An ASCII "-" between two numbers is a range separator everywhere except
# inside an arithmetic expression, where it is a subtraction. An equals sign is
# what tells the two apart: "10-20" is a range, "10-5 = 5" is not.
ASCII_BINARY_MINUS_PATTERN = compile_scan(r"(?<=\d)\s*-\s*(?=\d)")
DIMENSION_OPERATOR_PATTERN = compile_scan(
    r"(?P<left>\d+(?:[.,]\d+)?)\s*×\s*(?P<right>\d+(?:[.,]\d+)?)"
)
INCH_MARK_PATTERN = compile_scan(r"(?P<value>\d+(?:[.,]\d+)?)\s*″")
INCH_CONTEXT_PATTERN = compile_scan(
    r"\b(?:монитор\w*|экран\w*|диспле\w*|размер\w*|диаметр\w*|"
    r"ширин\w*|высот\w*)\b[^.!?;:]{0,32}$",
    re.IGNORECASE,
)
DIMENSION_HEAD_PATTERN = compile_scan(
    r"\b(?:размер(?:ом|ы)?|разрешение|габарит(?:ами|ы)?|ширина|высота)\s*$",
    re.IGNORECASE,
)
NUMERIC_RELATION_PATTERN = compile_scan(
    r"(?<![\w.])(?P<left>\d+(?:[ \u00a0\u2009\u202f]\d{3})*)"
    r"\s*:\s*"
    r"(?P<right>\d+(?:[ \u00a0\u2009\u202f]\d{3})*)(?!\d)"
)
INEQUALITY_OPERATOR_PATTERN = compile_scan(
    r"(?P<left>\b(?:\d+(?:[.,]\d+)?|[A-Za-zА-Яа-яЁё]+)\b)"
    r"\s+(?P<operator>[<>])\s+(?=\d)"
)
MATH_X_VARIABLE_PATTERN = compile_scan(r"(?<!\w)[xX](?=\s*(?:[<>≤≥]))")
WORD_PLUS_NUMBER_PATTERN = compile_scan(
    r"(?<=[A-Za-zА-Яа-яЁё])\s*\+\s*(?=\d)"
)
DOUBLE_PLUS_VERSION_PATTERN = compile_scan(
    r"(?<!\w)(?P<name>[A-Za-z][A-Za-z0-9]*)\s*\+\s*\+\s*(?P<version>\d+)\b"
)
ANGLE_MINUTE_MARK_PATTERN = compile_scan(r"(?P<value>\d+(?:[.,]\d+)?)\s*′")
ANGLE_SECOND_MARK_PATTERN = compile_scan(r"(?P<value>\d+(?:[.,]\d+)?)\s*″")
ANGLE_CONTEXT_PATTERN = compile_scan(
    r"(?:°|\bугол\w*|\bкоординат\w*|\bотклонени\w*)",
    re.IGNORECASE,
)
CAMERA_APERTURE_PATTERN = compile_scan(
    r"(?<!\w)f\s*/\s*(?P<whole>\d+)\.(?P<fraction>\d+)(?!\w)",
    re.IGNORECASE,
)
IPV4_PORT_PATTERN = compile_scan(
    r"(?<![\w.])(?P<address>(?:\d{1,3}\.){3}\d{1,3}):(?P<port>\d+)(?!\w)"
)
SCIENTIFIC_EXPONENT_PATTERN = compile_scan(
    rf"(?P<base>\d+(?:[.,]\d+)?)\s*⁻(?P<exponent>\d+)"
    rf"(?:\s+(?P<unit>{UNIT_TOKEN_FRAGMENT}))?"
)
RATIO_CONTEXT_PATTERN = compile_scan(
    r"\b(?:пропорци\w*|масштаб\w*|соотношени\w*)\s*$", re.IGNORECASE
)
SCORE_CONTEXT_PATTERN = compile_scan(
    r"\b(?:выиграл\w*|победил\w*|сч[её]т\w*)\s*$", re.IGNORECASE
)
_EQUATION_OPERAND = r"\(*(?:\d+(?:[.,]\d+)?|[^\W\d_]\w*)\)*"
EQUATION_PATTERN = compile_scan(
    rf"(?<!\w){_EQUATION_OPERAND}(?:\s*[-+*/^=]\s*{_EQUATION_OPERAND})+",
    re.UNICODE,
)
# Сосед по греческому блоку (включая политоническое письмо) означает
# греческое слово, а не обозначение: «Μαῦρο» не формула, и «α» внутри него
# не читается «альфа».
_GREEK_SCRIPT_CLASS = "Ͱ-Ͽἀ-῿"
_GREEK_PATTERN = compile_scan(
    rf"(?<![{_GREEK_SCRIPT_CLASS}])"
    rf"[{''.join(re.escape(char) for char in GREEK_LETTERS)}]+"
    rf"(?![{_GREEK_SCRIPT_CLASS}])"
)


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


def _equation_spans(text: str) -> list[tuple[int, int]]:
    """Spans of chained operand/operator runs that contain an equals sign.

    Deliberately narrower than :data:`MATH_EXPRESSION_CHAR_PATTERN`, which is a
    bag of characters and would run across a comma and any following prose: in
    ``x = 5, возраст 10-20 лет`` that reaches the range and turns it into a
    subtraction. Requiring an operator between operands stops the expression at
    the comma, leaving the range alone.
    """
    if "=" not in text:
        return []
    return [
        match.span()
        for match in EQUATION_PATTERN.finditer(text)
        if "=" in match.group(0)
    ]


def normalize_arithmetic_minus(text: str) -> str:
    """Read a hyphen between two numbers as «минус» inside an equation."""
    spans = _equation_spans(text)
    if not spans:
        return text

    def repl(match: re.Match[str]) -> str:
        position = match.start()
        if any(start <= position < end for start, end in spans):
            return " минус "
        return match.group(0)

    return ASCII_BINARY_MINUS_PATTERN.sub(repl, text)


def _normalize_contextual_equals(text: str) -> str:
    if "=" not in text:
        return text

    parts: list[str] = []
    last_index = 0
    for match in re.finditer(r"=", text):
        idx = match.start()
        if not _should_read_equals_as_ravno(text, idx):
            continue
        # The padded replacement swallows the surrounding spaces so that
        # "3 = 5" and "3=5" both come out with single spaces around «равно».
        left_end = idx
        while left_end > last_index and text[left_end - 1] in " \t":
            left_end -= 1
        right_start = idx + 1
        while right_start < len(text) and text[right_start] in " \t":
            right_start += 1
        parts.append(text[last_index:left_end])
        parts.append(" равно ")
        last_index = right_start

    if last_index == 0:
        return text

    parts.append(text[last_index:])
    return "".join(parts)


def _normalize_dimension_operator(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        tail = text[match.end() : match.end() + 40]
        unit_match = re.match(rf"\s+(?P<unit>{UNIT_TOKEN_FRAGMENT})(?!\w)", tail)
        if unit_match is not None and resolve_unit_info(unit_match.group("unit")) is not None:
            return f"{match.group('left')} на {match.group('right')}"
        left_context = text[max(0, match.start() - 30) : match.start()]
        if DIMENSION_HEAD_PATTERN.search(left_context):
            return f"{match.group('left')} на {match.group('right')}"
        return match.group(0)

    return DIMENSION_OPERATOR_PATTERN.sub(repl, text)


def _normalize_inch_marks(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 64) : match.start()]
        if not INCH_CONTEXT_PATTERN.search(left_context):
            return match.group(0)
        return f"{match.group('value')} дюйм"

    return INCH_MARK_PATTERN.sub(repl, text)


def _normalize_angle_marks(text: str) -> str:
    def has_angle_context(start: int) -> bool:
        left_context = text[max(0, start - 80) : start]
        return ANGLE_CONTEXT_PATTERN.search(left_context) is not None

    def minute_repl(match: re.Match[str]) -> str:
        if not has_angle_context(match.start()):
            return match.group(0)
        return f"{match.group('value')} мин"

    def second_repl(match: re.Match[str]) -> str:
        if not has_angle_context(match.start()):
            return match.group(0)
        return f"{match.group('value')} сек"

    text = ANGLE_MINUTE_MARK_PATTERN.sub(minute_repl, text)
    return ANGLE_SECOND_MARK_PATTERN.sub(second_repl, text)


def _normalize_numeric_relations(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 40) : match.start()]
        if RATIO_CONTEXT_PATTERN.search(left_context):
            relation = "к"
        elif SCORE_CONTEXT_PATTERN.search(left_context):
            relation = "—"
        else:
            return match.group(0)
        return f"{match.group('left')} {relation} {match.group('right')}"

    return NUMERIC_RELATION_PATTERN.sub(repl, text)


def _normalize_inequality_operators(text: str) -> str:
    return INEQUALITY_OPERATOR_PATTERN.sub(
        lambda match: (
            f"{match.group('left')} меньше "
            if match.group("operator") == "<"
            else f"{match.group('left')} больше "
        ),
        text,
    )


def _normalize_math_variables(text: str) -> str:
    return MATH_X_VARIABLE_PATTERN.sub("икс", text)


def _normalize_word_plus_number(text: str) -> str:
    return WORD_PLUS_NUMBER_PATTERN.sub(" плюс ", text)


def _normalize_double_plus_versions(text: str) -> str:
    return DOUBLE_PLUS_VERSION_PATTERN.sub(
        lambda match: f"{match.group('name')} плюс плюс {match.group('version')}",
        text,
    )


def _normalize_scientific_exponents(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        try:
            exponent = int(match.group("exponent"))
            ordinal = render_ordinal(
                exponent, case="gent", gender="femn", inanimate=True
            )
        except (TypeError, ValueError):
            return match.group(0)
        result = f"{match.group('base')} в минус {ordinal} степени"
        unit_raw = match.group("unit")
        if unit_raw:
            unit_info = resolve_unit_info(unit_raw)
            if unit_info is None:
                return match.group(0)
            result += " " + render_unit_expression(unit_info, {"nomn", "sing"})
        return result

    return SCIENTIFIC_EXPONENT_PATTERN.sub(repl, text)


def _normalize_camera_aperture(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 80) : match.start()]
        if not re.search(r"\b(?:iso|кадр\w*|диафрагм\w*|выдержк\w*)\b", left_context, re.IGNORECASE):
            return match.group(0)
        return f"f {match.group('whole')} и {match.group('fraction')}"

    return CAMERA_APERTURE_PATTERN.sub(repl, text)


def _normalize_ipv4_ports(text: str) -> str:
    return IPV4_PORT_PATTERN.sub(
        lambda match: f"{match.group('address')} двоеточие {match.group('port')}",
        text,
    )


def normalize_greek_letters(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        if len(token) != 1:
            return token
        return GREEK_LETTERS.get(token, token)

    return _GREEK_PATTERN.sub(repl, text)


def normalize_math_symbols(text: str) -> str:
    # Before the equals sign is spoken, while it still marks the expression.
    text = _normalize_inch_marks(text)
    text = _normalize_angle_marks(text)
    text = _normalize_math_variables(text)
    text = _normalize_double_plus_versions(text)
    text = _normalize_scientific_exponents(text)
    text = _normalize_camera_aperture(text)
    text = _normalize_ipv4_ports(text)
    text = _normalize_word_plus_number(text)
    text = _normalize_dimension_operator(text)
    text = _normalize_numeric_relations(text)
    text = _normalize_inequality_operators(text)
    text = normalize_arithmetic_minus(text)
    text = _normalize_contextual_equals(text)
    text = APPROXIMATE_NUMBER_PATTERN.sub("примерно ", text)
    text = BINARY_MATH_OPERATOR_PATTERN.sub(
        lambda match: BINARY_MATH_OPERATOR_READINGS[match.group("operator")],
        text,
    )
    for char, replacement in MATH_SYMBOLS.items():
        text = text.replace(char, replacement)
    return text


def normalize_standalone_currency(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return CURRENCY_STANDALONE[match.group(0)]

    return STANDALONE_CURRENCY_PATTERN.sub(repl, text)
