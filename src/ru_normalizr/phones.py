"""Осторожное чтение международных телефонов с явным префиксом «+»."""

from __future__ import annotations

import re
from itertools import pairwise

import phonenumbers
from num2words import num2words

from ._morph import parse_word
from .numerals._constants import is_unit_token

# Только горизонтальные пробелы: кандидат никогда не захватывает следующую
# строку. Ограничение размера не позволяет сканировать цифровую простыню.
_SPACES = " \t\u00a0\u202f\u2009"
_HYPHENS = "-\u2010\u2011"
_CANDIDATE = re.compile(
    rf"(?<![\w+.,*/=<>−-])\+[1-9][0-9{re.escape(_SPACES + _HYPHENS)}()]{{0,79}}"
)
_DIGITS = re.compile(r"[0-9]+")
_PAREN_GROUP = re.compile(rf"\([{_SPACES}]*[0-9]+[{_SPACES}]*\)")
_PHONE_CONTEXT = re.compile(
    r"\b(?:телефон\w*|тел\.|позвон\w*|звон\w*|контакт\w*|факс\w*)"
    r"|\bномер\s*:\s*$",
    re.IGNORECASE,
)
_RIGHT_TOKEN = re.compile(rf"[{_SPACES}]*(%|[$€₽°]|[\w/·]+)")
_QUANTITY_NOUN = re.compile(
    r"(?:рубл\w*|доллар\w*|евро|процент\w*|год\w*|лет|дн\w*|час\w*|минут\w*)\Z",
    re.IGNORECASE,
)


def _phone_context(text: str, start: int, end: int) -> bool:
    """Телефонная метка слева или номер, занимающий отдельную строку."""
    left = text[max(0, start - 80) : start]
    right = text[end : end + 80]
    left_clause = left.rsplit("\n", 1)[-1]
    context = list(_PHONE_CONTEXT.finditer(left_clause))
    if context and not re.search(r"[.!?;]", left_clause[context[-1].end() :]):
        return True
    # Обе стороны ограничены окном: не перечитываем префикс книги на каждый
    # телефон. Если границы строки вне окна, отдельной строкой её не объявляем.
    left_line = left.rsplit("\n", 1)[-1]
    right_line = right.split("\n", 1)[0]
    return (
        (start <= 80 or "\n" in left)
        and (len(text) - end <= 80 or "\n" in right)
        and not left_line.strip(_SPACES + '(«"')
        and not right_line.strip(_SPACES + ').»"')
    )


def _written_groups(raw: str) -> list[str] | None:
    """Проверить разделители и скобки, сохранив группы и начальные нули."""
    if "(" in raw or ")" in raw:
        if raw.count("(") != 1 or raw.count(")") != 1:
            return None
        if not _PAREN_GROUP.search(raw):
            return None
    digits = list(_DIGITS.finditer(raw))
    for previous, following in pairwise(digits):
        separator = raw[previous.end() : following.start()]
        if sum(char in _HYPHENS for char in separator) > 1:
            return None
        if "(" in separator and ")" in separator:
            return None
    return [match.group() for match in digits]


def _read_group(group: str) -> str:
    tail = group.lstrip("0")
    zeros = len(group) - len(tail)
    parts = ["ноль"] * zeros
    if tail:
        parts.append(str(num2words(int(tail), lang="ru")))
    return " ".join(parts)


def _is_quantity(token: str) -> bool:
    return (
        is_unit_token(token)
        or bool(_QUANTITY_NOUN.fullmatch(token))
        or any(
            "NOUN" in parsed.tag and is_unit_token(parsed.normal_form)
            for parsed in parse_word(token)
        )
    )


def normalize_international_phone_numbers(text: str) -> str:
    """Читать только подтверждённые контекстом номера, не угадывая числа."""
    if "+" not in text:
        return text

    def replace(match: re.Match[str]) -> str:
        raw = match.group().rstrip(_SPACES)
        # Закрывающая скобка вокруг всего номера — пунктуация предложения.
        if raw.endswith(")") and raw.count(")") == raw.count("(") + 1:
            raw = raw[:-1].rstrip(_SPACES)
        end = match.start() + len(raw)
        after = text[end : end + 80]
        if not raw[-1].isdigit() and not raw.endswith(")"):
            return match.group()
        if after and (after[0].isalnum() or after[0] in "_/-" + _HYPHENS):
            return match.group()
        if re.match(r"[.,:][0-9]", after):
            return match.group()
        if after.lstrip(_SPACES).startswith(("+", "=", "*", "/", "^", "<", ">")):
            return match.group()
        before = text[max(0, match.start() - 80) : match.start()].rstrip(_SPACES)
        if before and (before[-1].isdigit() or before[-1] in "=+*/^<>−-"):
            return match.group()
        token = _RIGHT_TOKEN.match(after)
        if token and _is_quantity(token.group(1)):
            return match.group()
        if not _phone_context(text, match.start(), end):
            return match.group()
        groups = _written_groups(raw)
        if groups is None:
            return match.group()
        digits = "".join(groups)
        if not 1 <= len(digits) <= 15:
            return match.group()
        try:
            number = phonenumbers.parse("+" + digits, None)
        except phonenumbers.NumberParseException:
            return match.group()
        if not phonenumbers.is_valid_number(number):
            return match.group()
        # parse() умеет удалять национальный префикс. Для нормализации текста
        # это потеря исходных цифр; международная запись должна быть обратима.
        if phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164) != "+" + digits:
            return match.group()
        country = str(number.country_code)
        if len(groups) == 1:
            formatted = phonenumbers.format_number(
                number, phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )
            groups = _DIGITS.findall(formatted)
        elif groups[0] != country:
            if not groups[0].startswith(country):
                return match.group()
            groups = [country, groups[0][len(country) :], *groups[1:]]
        try:
            reading = "плюс " + ", ".join(_read_group(group) for group in groups)
        except (ValueError, OverflowError, NotImplementedError):
            # Внешний конвертер не должен ни терять номер, ни выводить его в лог.
            return match.group()
        return reading + match.group()[len(raw) :]

    return _CANDIDATE.sub(replace, text)
