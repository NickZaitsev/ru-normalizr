from __future__ import annotations

import logging
import re

import num2words

from .abbreviation_context import should_keep_terminal_abbreviation_dot
from .options import NormalizeOptions
from .years import year_to_ordinal_words

logger = logging.getLogger(__name__)

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
MONTH_NAME_FRAGMENT = (
    r"(?:" + "|".join(map(re.escape, MONTHS_GENT)) + r")(?![а-яё])"
)
# The era word is optional but the whitespace in front of it is not: consuming a
# trailing space without the word leaves the rendered date glued to whatever
# follows ("две тысячи двадцатого годаг."). The alternation matches the shape the
# years stage already accepts, so both stages absorb the same trailing forms.
YEAR_ERA_TAIL_FRAGMENT = r"(?:\s+(?P<era_word>год[а-яё]*\b|г\.?(?!\w)))?"
YEAR_TAIL_FRAGMENT = r"(?:\s+(?P<year>\d{4})" + YEAR_ERA_TAIL_FRAGMENT + r")?"
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
TEXT_DATE_FROM_TO_PATTERN = re.compile(
    r"\b(?P<start_prep>с|со)\s+(?P<day1>\d{1,2})\s+"
    r"(?P<end_prep>по|до)\s+(?P<day2>\d{1,2})\s+(?P<month>"
    + MONTH_NAME_FRAGMENT
    + r")"
    + YEAR_TAIL_FRAGMENT,
    re.IGNORECASE,
)
TEXT_DATE_RANGE_PATTERN = re.compile(
    r"\b(?:(?P<prep>за|на|в|во|по|с|со|до|от)\s+)?(?P<day1>\d{1,2})\s*[–—-]\s*(?P<day2>\d{1,2})\s+(?P<month>"
    + MONTH_NAME_FRAGMENT
    + r")"
    + YEAR_TAIL_FRAGMENT,
    re.IGNORECASE,
)
TEXT_DATE_LIST_PATTERN = re.compile(
    r"\b(?P<days>\d{1,2}(?:\s*(?:,|и)\s*\d{1,2})+)\s+(?P<month>"
    + MONTH_NAME_FRAGMENT
    + r")"
    + YEAR_TAIL_FRAGMENT,
    re.IGNORECASE,
)
TEXT_DATE_PATTERN = re.compile(
    r"\b(?:(?P<prep>перед)\s+)?(?P<day>\d{1,2})\s+(?P<month>"
    + MONTH_NAME_FRAGMENT
    + r")"
    + YEAR_TAIL_FRAGMENT,
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
MONTH_ABBREVIATIONS = {
    "янв": 1,
    "фев": 2,
    "февр": 2,
    "мар": 3,
    "апр": 4,
    "май": 5,
    "июн": 6,
    "июл": 7,
    "авг": 8,
    "сен": 9,
    "сент": 9,
    "окт": 10,
    "ноя": 11,
    "нояб": 11,
    "дек": 12,
}
ABBREVIATED_TEXT_DATE_PATTERN = re.compile(
    r"(?<!\w)(?P<day>0?[1-9]|[12]\d|3[01])\s+"
    r"(?P<month>янв\.?|февр?\.?|мар\.?|апр\.?|май\.?|июн\.?|июл\.?|"
    r"авг\.?|сент?\.?|окт\.?|нояб?\.?|дек\.?)\s+"
    r"(?P<year>\d{4})(?:\s+г\.?)?(?![-–—]?[A-Za-zА-Яа-яЁё])",
    re.IGNORECASE,
)
DAY_MONTH_DATE_PATTERN = re.compile(
    r"(?<![\w.])(?P<day>0?[1-9]|[12]\d|3[01])\."
    r"(?P<month>0?[1-9]|1[0-2])(?!\d)(?!\.\d)"
)
DAY_MONTH_DATE_CONTEXT_PATTERN = re.compile(
    r"\b(?:дат(?:а|у|ой|е)|срок\w*|при[её]м\w*|встреч\w*|мероприяти\w*|"
    r"заявк\w*|законч\w*|начал\w*|назнач\w*|родил\w*|праздник\w*|дн[её]м)\b",
    re.IGNORECASE,
)
NUMERIC_DATE_PATTERN = re.compile(
    r"\b(?P<day>0?[1-9]|[12]\d|3[01])\.(?P<month>0?[1-9]|1[0-2])\.(?P<year>\d{2,4})(?!\w)"
    + YEAR_ERA_TAIL_FRAGMENT,
    re.IGNORECASE,
)
ISO_DATE_PATTERN = re.compile(
    r"(?<![\w.])(?P<year>\d{4})[-–—](?P<month>0?[1-9]|1[0-2])[-–—]"
    r"(?P<day>0?[1-9]|[12]\d|3[01])(?!\d)"
    r"(?![-–—]?[A-Za-zА-Яа-яЁё])"
)
TIME_PATTERN = re.compile(
    r"\b(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)(?::(?P<second>[0-5]\d))?\b"
)
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
    except Exception as exc:
        logger.debug("num2words genitive ordinal failed for day %r: %s", day, exc)
        try:
            return num2words.num2words(day, lang="ru", to="ordinal")
        except Exception as exc:
            logger.debug("num2words ordinal failed for day %r: %s", day, exc)
            return None


def _day_to_ordinal(day: int, case: str = "genitive") -> str | None:
    if day < 1 or day > 31:
        return None
    try:
        return num2words.num2words(day, lang="ru", to="ordinal", case=case, gender="n")
    except Exception as exc:
        logger.debug("num2words ordinal failed for day %r (case=%s): %s", day, case, exc)
        try:
            return num2words.num2words(day, lang="ru", to="ordinal")
        except Exception as exc:
            logger.debug("num2words ordinal failed for day %r: %s", day, exc)
            return None


def _era_tail_dot(source_text: str, match: re.Match[str]) -> str:
    """Give back a sentence-final dot swallowed together with a «г.» tail."""
    era_word = match.groupdict().get("era_word")
    if not era_word or not era_word.endswith("."):
        return ""
    if not should_keep_terminal_abbreviation_dot(source_text, match.end()):
        return ""
    return "."


# «7092 (1582) года»: one date written in two calendars. The year word stands
# after the bracket and serves both numbers, so a date must not add its own.
_DUAL_DATING_TAIL_PATTERN = re.compile(
    r"\s*[\(\[]\d{3,4}[\)\]]\s+(?:г\+?о\+?д(?:\+?[а-яё])*(?![а-яё])|г\.?(?!\w))",
    re.IGNORECASE,
)


def _date_year_tail(source_text: str, match: re.Match[str], year: str) -> str:
    """Render the «… года» tail of a date.

    A dual dating is left to the years stage: it owns both numbers and the
    single year word that stands after the bracket, and it is the stage that
    knows how to inflect an abbreviated «г.» there. Only the day and the month
    are rendered here, and the year digits are handed over untouched.
    """
    if _DUAL_DATING_TAIL_PATTERN.match(source_text, match.end()):
        return f" {year}"
    return f" {year_to_ordinal_words(int(year), case='gent')} года"


def normalize_text_dates(text: str) -> str:
    def from_to_repl(match: re.Match[str]) -> str:
        day1_word = _day_to_ordinal(int(match.group("day1")), case="genitive")
        end_case = "accusative" if match.group("end_prep").lower() == "по" else "genitive"
        day2_word = _day_to_ordinal(int(match.group("day2")), case=end_case)
        if day1_word is None or day2_word is None:
            return match.group(0)
        result = (
            f"{match.group('start_prep')} {day1_word} {match.group('end_prep')} "
            f"{day2_word} {match.group('month').lower()}"
        )
        if match.group("year"):
            result += _date_year_tail(text, match, match.group("year"))
        return result + _era_tail_dot(text, match)

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
            result += _date_year_tail(text, match, match.group("year"))
        return result + _era_tail_dot(text, match)

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
            result += _date_year_tail(text, match, match.group("year"))
        return result + _era_tail_dot(text, match)

    def repl(match: re.Match[str]) -> str:
        prep = match.group("prep")
        day_case = "instrumental" if prep else "genitive"
        day_word = _day_to_ordinal(int(match.group("day")), case=day_case)
        month = match.group("month").lower()
        if day_word is None:
            return match.group(0)
        result = f"{prep} {day_word} {month}" if prep else f"{day_word} {month}"
        if match.group("year"):
            result += _date_year_tail(text, match, match.group("year"))
        return result + _era_tail_dot(text, match)

    text = TEXT_DATE_FROM_TO_PATTERN.sub(from_to_repl, text)
    text = TEXT_DATE_RANGE_PATTERN.sub(range_repl, text)
    text = TEXT_DATE_LIST_PATTERN.sub(list_repl, text)
    return TEXT_DATE_PATTERN.sub(repl, text)


def normalize_dates(text: str) -> str:
    def date_case(source_text: str, start: int) -> str:
        left_context = source_text[max(0, start - 12) : start]
        if re.search(r"\b(?:на|по)\s*$", left_context, re.IGNORECASE):
            return "accusative"
        if re.search(r"\b(?:с|со|от|до)\s*$", left_context, re.IGNORECASE):
            return "genitive"
        return "genitive"

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
                day,
                lang="ru",
                to="ordinal",
                case=date_case(text, match.start()),
                gender="n",
            )
        except Exception as exc:
            logger.debug("num2words genitive ordinal failed for day %r: %s", day, exc)
            day_words = num2words.num2words(day, lang="ru", to="ordinal")
        try:
            year_words = num2words.num2words(
                year, lang="ru", to="ordinal", case="genitive"
            )
        except Exception as exc:
            logger.debug("num2words genitive ordinal failed for year %r: %s", year, exc)
            year_words = num2words.num2words(year, lang="ru", to="ordinal")
        rendered = (
            f"{day_words} {MONTHS_GENT_BY_NUMBER.get(month, str(month))} "
            f"{year_words} года"
        )
        return rendered + _era_tail_dot(text, match)

    return NUMERIC_DATE_PATTERN.sub(repl, text)


def normalize_abbreviated_text_dates(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        month_key = match.group("month").lower().rstrip(".")
        month = MONTH_ABBREVIATIONS.get(month_key)
        if month is None:
            return match.group(0)
        return f"{match.group('day')}.{month:02d}.{match.group('year')}"

    return ABBREVIATED_TEXT_DATE_PATTERN.sub(repl, text)


def normalize_day_month_dates(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 64) : match.start()]
        right_context = text[match.end() : match.end() + 16]
        if not (
            DAY_MONTH_DATE_CONTEXT_PATTERN.search(left_context)
            or re.match(r"\s+в\s+\d{1,2}:\d{2}\b", right_context, re.IGNORECASE)
        ):
            return match.group(0)
        day = _day_to_ordinal(int(match.group("day")), case="genitive")
        if day is None:
            return match.group(0)
        month = MONTHS_GENT_BY_NUMBER[int(match.group("month"))]
        return f"{day} {month}"

    return DAY_MONTH_DATE_PATTERN.sub(repl, text)


def normalize_time(text: str) -> str:
    def counted_noun(value: int, forms: tuple[str, str, str]) -> str:
        last_two = value % 100
        last = value % 10
        if 11 <= last_two <= 14:
            return forms[2]
        if last == 1:
            return forms[0]
        if 2 <= last <= 4:
            return forms[1]
        return forms[2]

    def genitive_counted_noun(value: int, forms: tuple[str, str, str]) -> str:
        return forms[1] if value % 10 == 1 and value % 100 != 11 else forms[2]

    def render_time(match: re.Match[str]) -> str:
        hour = int(match.group("hour"))
        minute_str = match.group("minute")
        minute = int(minute_str)
        second_str = match.groupdict().get("second")
        left_context = text[max(0, match.start() - 12) : match.start()]
        governed_range = bool(
            re.search(r"\b(?:с|со|от|до|после)\s*$", left_context, re.IGNORECASE)
        )
        if second_str is not None:
            second = int(second_str)
            try:
                hour_words = num2words.num2words(hour, lang="ru")
                minute_words = num2words.num2words(
                    minute, lang="ru", gender="feminine"
                )
                second_words = num2words.num2words(second, lang="ru")
            except Exception as exc:
                logger.debug("num2words failed for time %02d:%02d:%02d: %s", hour, minute, second, exc)
                return match.group(0)
            return (
                f"{hour_words} {counted_noun(hour, ('час', 'часа', 'часов'))} "
                f"{minute_words} {counted_noun(minute, ('минута', 'минуты', 'минут'))} "
                f"{second_words} {counted_noun(second, ('секунда', 'секунды', 'секунд'))}"
            )
        try:
            if governed_range:
                hour_words = num2words.num2words(
                    hour, lang="ru", case="genitive"
                )
            else:
                hour_words = num2words.num2words(hour, lang="ru")
        except Exception as exc:
            logger.debug("num2words failed for hour %r: %s", hour, exc)
            hour_words = str(hour)
        if minute_str[0] == "0":
            try:
                minute_words = (
                    f"ноль {num2words.num2words(int(minute_str[1]), lang='ru')}"
                )
            except Exception as exc:
                logger.debug("num2words failed for minute %r: %s", minute_str, exc)
                minute_words = f"ноль {minute_str[1]}"
        else:
            try:
                minute_words = num2words.num2words(int(minute_str), lang="ru")
            except Exception as exc:
                logger.debug("num2words failed for minute %r: %s", minute_str, exc)
                minute_words = minute_str
        if governed_range:
            try:
                minute_words = num2words.num2words(
                    int(minute_str), lang="ru", case="genitive"
                )
            except Exception as exc:
                logger.debug("num2words genitive minute failed for %r: %s", minute_str, exc)
                minute_words = minute_str
            return (
                f"{hour_words} {genitive_counted_noun(hour, ('час', 'часа', 'часов'))} "
                f"{minute_words} {genitive_counted_noun(minute, ('минута', 'минуты', 'минут'))}"
            )
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
    if not any(char.isdecimal() for char in text):
        return text
    text = normalize_abbreviated_text_dates(text)
    text = normalize_day_month_dates(text)
    text = normalize_text_dates(text)
    text = ISO_DATE_PATTERN.sub(
        lambda match: (
            f"{match.group('day')}.{match.group('month')}.{match.group('year')}"
        ),
        text,
    )
    text = normalize_dates(text)
    text = normalize_time(text)
    return text
