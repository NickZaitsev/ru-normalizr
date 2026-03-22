from __future__ import annotations

import re

import num2words

from .options import NormalizeOptions
from .years import year_to_ordinal_words

MONTHS_GENT = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}
TEXT_DATE_RANGE_CASES = {
    "за": "accusative",
    "на": "accusative",
    "в": "accusative",
    "во": "accusative",
    "по": "accusative",
    "с": "genitive",
    "со": "genitive",
    "до": "genitive",
    "от": "genitive",
}
TEXT_DATE_RANGE_PATTERN = re.compile(
    r"\b(?:(?P<prep>за|на|в|во|по|с|со|до|от)\s+)?(?P<day1>\d{1,2})\s*[–—-]\s*(?P<day2>\d{1,2})\s+(?P<month>"
    + "|".join(MONTHS_GENT.keys())
    + r")(?:\s+(?P<year>\d{4})\s*(?:года?)?)?",
    re.IGNORECASE,
)
TEXT_DATE_LIST_PATTERN = re.compile(
    r"\b(?P<days>\d{1,2}(?:\s*(?:,|и)\s*\d{1,2})+)\s+(?P<month>"
    + "|".join(MONTHS_GENT.keys())
    + r")(?:\s+(?P<year>\d{4})\s*(?:года?)?)?",
    re.IGNORECASE,
)
TEXT_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\s+("
    + "|".join(MONTHS_GENT.keys())
    + r")(?:\s+(\d{4})\s*(?:года?)?)?",
    re.IGNORECASE,
)
MONTHS_GENT_BY_NUMBER = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}
NUMERIC_DATE_PATTERN = re.compile(
    r"\b(?P<day>0?[1-9]|[12]\d|3[01])\.(?P<month>0?[1-9]|1[0-2])\.(?P<year>\d{2,4})\b"
)
TIME_PATTERN = re.compile(r"\b(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)\b")
DOTTED_TIME_PATTERN = re.compile(
    r"\b(?P<hour>[01]?\d|2[0-3])\.(?P<minute>[0-5]\d)\b",
    re.IGNORECASE,
)
DOTTED_TIME_LEFT_CONTEXT_PATTERN = re.compile(
    r"(?:^|[\s(\"«])(?:в|во|к|около)\s*$",
    re.IGNORECASE,
)
DOTTED_TIME_RIGHT_CONTEXT_PATTERN = re.compile(
    r"^\s*(?:утр(?:ом|а)?|вечер(?:ом|а)?|ноч(?:ью|и)?|дн(?:ём|ем)?|час(?:ов|а)?\b)",
    re.IGNORECASE,
)


def _day_to_ordinal_genitive(day: int) -> str | None:
    if day < 1 or day > 31:
        return None
    try:
        return num2words.num2words(
            day, lang="ru", to="ordinal", case="genitive", gender="n"
        )
    except Exception:
        try:
            return num2words.num2words(day, lang="ru", to="ordinal")
        except Exception:
            return None


def _day_to_ordinal(day: int, case: str = "genitive") -> str | None:
    if day < 1 or day > 31:
        return None
    try:
        return num2words.num2words(day, lang="ru", to="ordinal", case=case, gender="n")
    except Exception:
        try:
            return num2words.num2words(day, lang="ru", to="ordinal")
        except Exception:
            return None


def normalize_text_dates(text: str) -> str:
    def range_repl(match: re.Match[str]) -> str:
        prep = match.group("prep")
        case = (
            TEXT_DATE_RANGE_CASES.get(prep.lower(), "genitive") if prep else "genitive"
        )
        day1_word = _day_to_ordinal(int(match.group("day1")), case=case)
        day2_word = _day_to_ordinal(int(match.group("day2")), case=case)
        month = match.group("month").lower()
        if day1_word is None or day2_word is None:
            return match.group(0)
        result = f"{day1_word} — {day2_word} {month}"
        if prep:
            result = f"{prep} {result}"
        if match.group("year"):
            result += (
                f" {year_to_ordinal_words(int(match.group('year')), case='gent')} года"
            )
        return result

    def list_repl(match: re.Match[str]) -> str:
        month = match.group("month").lower()
        parts = re.split(r"(\s*(?:,|и)\s*)", match.group("days"))
        rendered_parts: list[str] = []
        for part in parts:
            stripped = part.strip()
            if not stripped:
                continue
            if stripped in {",", "и"}:
                rendered_parts.append(part)
                continue
            day_word = _day_to_ordinal_genitive(int(stripped))
            if day_word is None:
                return match.group(0)
            rendered_parts.append(day_word)
        result = f"{''.join(rendered_parts)} {month}"
        if match.group("year"):
            result += (
                f" {year_to_ordinal_words(int(match.group('year')), case='gent')} года"
            )
        return result

    def repl(match: re.Match[str]) -> str:
        day_word = _day_to_ordinal_genitive(int(match.group(1)))
        month = match.group(2).lower()
        if day_word is None:
            return match.group(0)
        result = f"{day_word} {month}"
        if match.group(3):
            result += f" {year_to_ordinal_words(int(match.group(3)), case='gent')} года"
        return result

    text = TEXT_DATE_RANGE_PATTERN.sub(range_repl, text)
    text = TEXT_DATE_LIST_PATTERN.sub(list_repl, text)
    return TEXT_DATE_PATTERN.sub(repl, text)


def normalize_dates(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        day = int(match.group("day"))
        month = int(match.group("month"))
        year = int(match.group("year"))
        if day < 1 or day > 31 or month < 1 or month > 12:
            return match.group(0)
        if year < 100:
            year = 1900 + year if year >= 50 else 2000 + year
        try:
            day_words = num2words.num2words(
                day, lang="ru", to="ordinal", case="genitive", gender="n"
            )
        except Exception:
            day_words = num2words.num2words(day, lang="ru", to="ordinal")
        try:
            year_words = num2words.num2words(
                year, lang="ru", to="ordinal", case="genitive"
            )
        except Exception:
            year_words = num2words.num2words(year, lang="ru", to="ordinal")
        return f"{day_words} {MONTHS_GENT_BY_NUMBER.get(month, str(month))} {year_words} года"

    return NUMERIC_DATE_PATTERN.sub(repl, text)


def normalize_time(text: str) -> str:
    def render_time(match: re.Match[str]) -> str:
        hour = int(match.group("hour"))
        minute_str = match.group("minute")
        try:
            hour_words = num2words.num2words(hour, lang="ru")
        except Exception:
            hour_words = str(hour)
        if minute_str[0] == "0":
            try:
                minute_words = (
                    f"ноль {num2words.num2words(int(minute_str[1]), lang='ru')}"
                )
            except Exception:
                minute_words = f"ноль {minute_str[1]}"
        else:
            try:
                minute_words = num2words.num2words(int(minute_str), lang="ru")
            except Exception:
                minute_words = minute_str
        return f"{hour_words}, {minute_words}"

    def render_dotted_time(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 16) : match.start()]
        right_context = text[match.end() : match.end() + 24]
        if not (
            DOTTED_TIME_LEFT_CONTEXT_PATTERN.search(left_context)
            or DOTTED_TIME_RIGHT_CONTEXT_PATTERN.search(right_context)
        ):
            return match.group(0)
        return render_time(match)

    text = TIME_PATTERN.sub(render_time, text)
    return DOTTED_TIME_PATTERN.sub(render_dotted_time, text)


def normalize_dates_and_time(text: str, options: NormalizeOptions | None = None) -> str:
    active = options or NormalizeOptions()
    if not active.enable_dates_time_normalization:
        return text
    text = normalize_text_dates(text)
    text = normalize_dates(text)
    text = normalize_time(text)
    return text
