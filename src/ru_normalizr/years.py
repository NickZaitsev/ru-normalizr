from __future__ import annotations

import functools
import logging
import re

import num2words

from ._morph import canonicalize_case, parse_word, select_parse
from .abbreviation_context import (
    allows_short_abbreviated_year,
    has_mass_measurement_context,
    should_keep_terminal_abbreviation_dot,
)
from .numerals._num2words import resolve_num2words_case, resolve_primary_case
from .text_context import normalize_context_token, simple_tokenize
from .text_scan import ScanPattern, compile_scan, first_non_whitespace_index
from .years_context import (
    DECIMAL_TAIL,
    SPACED_THOUSANDS_TAIL,
    YEAR_ANY_NUMBER_PATTERN,
    YEAR_IMPLICIT_PREP_PATTERN,
    YEAR_RANGE_NUMBER_PATTERN,
    is_plausible_year,
    should_treat_as_implicit_year,
)

logger = logging.getLogger(__name__)

YEAR_SUFFIX_TO_CASE = {
    "ый": "nomn",
    "ой": "nomn",
    "й": "nomn",
    "ые": "nomn",
    "ого": "gent",
    "го": "gent",
    "ых": "gent",
    "ому": "datv",
    "ым": "ablt",
    "ыми": "ablt",
    "ом": "loct",
    "му": "datv",
    "е": "nomn",
    "х": "gent",
    "м": "datv",
    "ми": "ablt",
}
YEAR_SUFFIX_REGEX = "|".join(
    sorted((re.escape(suffix) for suffix in YEAR_SUFFIX_TO_CASE), key=len, reverse=True)
)
PLURAL_SUFFIXES = {"е", "х", "м", "ми", "ые", "ых", "ыми"}
YEAR_WORD_TO_CASE = {
    "год": "nomn",
    "года": "gent",
    "году": "loct",
    "годом": "ablt",
    "годе": "loct",
    "годы": "nomn",
    "годов": "gent",
    "годам": "datv",
    "года́ми": "ablt",
    "годами": "ablt",
    "годах": "loct",
    "г.": "nomn",
    "гг.": "nomn",
}
YEAR_WORD_FORMS = {
    ("год", "nomn"): "год",
    ("год", "gent"): "года",
    ("год", "datv"): "году",
    ("год", "accs"): "год",
    ("год", "ablt"): "годом",
    ("год", "loct"): "году",
    ("годы", "nomn"): "годы",
    ("годы", "gent"): "годов",
    ("годы", "datv"): "годам",
    ("годы", "accs"): "годы",
    ("годы", "ablt"): "годами",
    ("годы", "loct"): "годах",
}
YEAR_PLURAL_ABBREV_REGEX = r"(?:гг\.?|г\.\s*г\.?)"
# `preprocess` represents a combining Cyrillic stress mark as `+` before the
# stressed vowel. Keep that marker inside year words long enough for this stage
# to recognize the whole word, then canonicalize the matched word before
# morphology lookup and output.
YEAR_WORD_PATTERN = r"г\+?о\+?д(?:\+?[а-яё])*"
PREPOSITIONS_TO_CASE = {
    "в": "loct",
    "во": "loct",
    "о": "loct",
    "об": "loct",
    "к": "datv",
    "ко": "datv",
    "с": "gent",
    "со": "gent",
    "до": "gent",
    "от": "gent",
    "за": "accs",
    "на": "accs",
    "по": "accs",
    "между": "ablt",
    "около": "gent",
    "под": "ablt",
}
# The hyphen lookahead leaves «6—7-тысячного» to the compound adjective rule
# of the numerals stage: it is one attribute, not an enumeration.
NUMERIC_RANGE_PATTERN = compile_scan(
    r"(\d+)\s*[—–]\s*(\d+)(?!\d)(?!\s*[а-яА-ЯёЁa-zA-Z%°$€₽Ω])(?!-[а-яА-ЯёЁ])"
)
YEAR_PREPOSITION_REGEX = r"в|во|о|об|к|ко|с|со|до|от|за|на|по|между|около|под"
YEAR_IMPLICIT_PREP_REGEX = r"в|во|о|об|к|ко|на|за|под"
ERA_REGEX = (
    r"(?:до\s+н\.?\s*э\.?|н\.?\s*э\.?|до\s+нашей\s+эры|нашей\s+эры|"
    r"B\.?\s*C\.?\s*E\.?|B\.?\s*C\.?|C\.?\s*E\.?|A\.?\s*D\.?)"
)


def _normalize_era_marker(raw: str) -> str | None:
    compact = re.sub(r"[\s.]+", "", raw)
    compact_upper = compact.upper()
    if compact_upper in {"BC", "BCE"} and compact == compact_upper:
        return "до нашей эры"
    if compact_upper in {"AD", "CE"} and compact == compact_upper:
        return "нашей эры"

    lowered = raw.lower().strip()
    if re.fullmatch(r"до\s+н\.?\s*э\.?", lowered, re.IGNORECASE):
        return "до нашей эры"
    if re.fullmatch(r"н\.?\s*э\.?", lowered, re.IGNORECASE):
        return "нашей эры"
    if lowered.startswith("до нашей эры"):
        return "до нашей эры"
    if lowered.startswith("нашей эры"):
        return "нашей эры"
    return None


def _should_keep_era_terminal_dot(source_text: str, match: re.Match[str]) -> bool:
    raw_era = match.group("era")
    if raw_era is None or not raw_era.rstrip().endswith("."):
        return False

    next_index, saw_newline = first_non_whitespace_index(source_text, match.end())
    if next_index >= len(source_text):
        return True
    if saw_newline:
        return True
    next_char = source_text[next_index]
    if next_char in '.!?…)"»”]}':
        return True
    if next_char.isupper():
        return True
    return (
        next_char in '"»”)]}'
        and next_index + 1 < len(source_text)
        and source_text[next_index + 1].isupper()
    )


def _resolve_explicit_year_word_case(prep: str | None, word: str) -> str:
    word_lower = word.replace("+", "").lower()
    if word_lower == "году" and prep:
        return "datv" if prep.lower() in ("к", "ко") else "loct"
    return YEAR_WORD_TO_CASE.get(word_lower, "nomn")


def _follows_month_name(text: str, start: int) -> bool:
    """Check whether a genitive month name stands right before ``start``."""
    from .dates_time import MONTHS_GENT

    tail = text[max(0, start - 12) : start]
    match = re.search(r"([а-яё]+)\s+$", tail, re.IGNORECASE)
    return match is not None and match.group(1).lower() in MONTHS_GENT


def _month_gent_fragment() -> str:
    """Фрагмент имён месяцев в родительном падеже (с дореформенными формами)."""
    from .dates_time import MONTH_NAME_FRAGMENT

    return MONTH_NAME_FRAGMENT


def _month_name_precedes(text: str, start: int) -> bool:
    """Имя месяца в любом падеже стоит прямо перед ``start`` — «в марте 1771»."""
    from .numerals.numeric_suffixes import MONTH_LEMMAS

    tail = text[max(0, start - 14) : start]
    match = re.search(r"([а-яё]+)\s+$", tail, re.IGNORECASE)
    if match is None:
        return False
    parsed = select_parse(match.group(1).lower(), pos="NOUN")
    return parsed is not None and parsed.normal_form in MONTH_LEMMAS


def _counted_noun_follows(text: str, end: int, number: int) -> bool:
    """«до мая 1500 солдат» — число считает существительное, а не называет год."""
    match = re.match(r"\s+([а-яё]+)", text[end : end + 24])
    if match is None:
        return False
    tail, last = number % 100, number % 10
    if last == 1 and tail != 11:
        return False
    if last in {2, 3, 4} and tail not in {12, 13, 14}:
        required: tuple[str, ...] = ("sing",)
    else:
        required = ("plur",)
    parsed = select_parse(
        match.group(1), pos="NOUN", required_grammemes=required, case="gent"
    )
    return parsed is not None and parsed.normal_form not in {"год", "день", "число"}


def _canonicalize_year_word(word: str) -> str:
    return word.replace("+", "")


#: Части речи служебных слов: у таких токенов есть и предметное чтение
#: («в» — название буквы), но измеряемым веществом они быть не могут.
_FUNCTION_WORD_POS = frozenset({"PREP", "CONJ", "PRCL", "INTJ"})


def _genitive_mass_noun_follows(text: str, end: int) -> bool:
    """Check whether a bare genitive noun follows — «под 30 г. песка».

    The annalistic «под 964 г. записано» is followed by a verb, an adverb or a
    capitalized name, never by a lowercase genitive noun measuring the grams.

    Служебное слово веществом не бывает: «под 1185 г. в рассказе» — предлог,
    хотя у «в» есть и существительное-чтение (название буквы), которое иначе
    превращает летописный год в граммы.
    """
    match = re.match(r"\s+([а-яё]+)", text[end : end + 20])
    if match is None:
        return False
    token = match.group(1)
    parses = parse_word(token)
    if any(parse.tag.POS in _FUNCTION_WORD_POS for parse in parses):
        return False
    parsed = select_parse(parses, pos="NOUN")
    return (
        parsed is not None
        and parsed.tag.case == "gent"
        and "anim" not in parsed.tag
    )


_SURNAME_SUBJECT_PATTERN = re.compile(r"\s+([А-ЯЁ][а-яё]+)")


def _surname_subject_follows(text: str, end: int) -> bool:
    """Фамилия-подлежащее сразу после «г.» — фраза продолжается.

    «В 1867 г. Семёнов поместил…» — дата вынесена вперёд, а заглавная буква
    принадлежит фамилии, не новому предложению. Настоящая граница предложения
    перед голой фамилией-подлежащим встречается заметно реже, чем этот оборот,
    поэтому словарная фамилия в именительном падеже снимает точку.
    """
    match = _SURNAME_SUBJECT_PATTERN.match(text, end)
    if match is None:
        return False
    return any(
        "Surn" in parse.tag and "nomn" in parse.tag and "sing" in parse.tag
        for parse in parse_word(match.group(1))
    )


# Годы «от сотворения мира» в летописях доходят до середины восьмого тысячелетия.
_BYZANTINE_YEAR_MAX = 7600


_GOSPODA_OBLIQUE_CASES = frozenset({"gent", "datv", "accs", "ablt", "loct"})


def _gospoda_case_around(text: str, start: int, end: int) -> str | None:
    """Падеж обращения «господа», если «гг.» стоит внутри именной группы.

    «всем гг. батарейным командирам»: модификатор слева и одушевлённая
    вершина справа согласованы в косвенном падеже множественного числа —
    это «господам», а не «годы». Орфанное «гг.» со значением «годы»
    («в те гг. людям пришлось…») такого сквозного согласования не имеет:
    слева стоит определение к «годам» в другом падеже.
    """
    before = re.search(r"([а-яёА-ЯЁ]+)\s+$", text[:start])
    after = re.match(r"\s+([а-яё]+)(?:\s+([а-яё]+))?", text[end : end + 40])
    if before is None or after is None:
        return None
    first, second = after.group(1), after.group(2)
    head = select_parse(first, pos="NOUN", required_grammemes=("anim", "plur"))
    modifier: str | None = None
    if head is None and second is not None:
        head = select_parse(second, pos="NOUN", required_grammemes=("anim", "plur"))
        modifier = first
    if head is None:
        return None
    case = canonicalize_case(head.tag.case)
    if case not in _GOSPODA_OBLIQUE_CASES:
        return None
    if modifier is not None and (
        select_parse(modifier, pos="ADJF", required_grammemes=("plur",), case=case)
        is None
    ):
        return None
    left = select_parse(
        before.group(1),
        pos=("ADJF", "NPRO"),
        required_grammemes=("plur",),
        case=case,
    )
    if left is None:
        return None
    return case


def _render_gospoda(case: str) -> str | None:
    parsed = select_parse("господа", pos="NOUN", required_grammemes=("plur",))
    if parsed is None:
        return None
    inflected = parsed.inflect(frozenset({case, "plur"}))
    return inflected.word if inflected is not None else None


@functools.lru_cache(maxsize=4096)
def year_to_ordinal_words(year: int, case: str = "nomn", plural: bool = False) -> str:
    case = resolve_primary_case(case)
    normalized_case = "nomn" if case == "accs" and not plural else case
    if year >= 10000 and not plural and year % 1000:
        high = (year // 1000) * 1000
        tail = year % 1000
        try:
            high_words = num2words.num2words(
                high,
                lang="ru",
                case=resolve_num2words_case(normalized_case),
            )
            tail_words = year_to_ordinal_words(tail, normalized_case)
            return f"{high_words} {tail_words}"
        except Exception as exc:
            logger.debug("num2words failed for split year %r: %s", year, exc)
    num2words_case = resolve_num2words_case(normalized_case, default="")
    if num2words_case:
        try:
            return num2words.num2words(
                year,
                lang="ru",
                to="ordinal",
                case=num2words_case,
                plural=plural,
            )
        except Exception as exc:
            logger.debug("num2words ordinal failed for year %r (case=%s): %s", year, num2words_case, exc)
    try:
        ordinal = num2words.num2words(year, lang="ru", to="ordinal")
    except Exception as exc:
        logger.debug("num2words ordinal failed for year %r: %s", year, exc)
        return str(year)
    words = ordinal.split()
    if not words:
        return ordinal
    parsed = parse_word(words[-1])
    if not parsed:
        return ordinal
    tags = {normalized_case, "plur" if plural else "masc"}
    if "Anum" in parsed[0].tag:
        tags.add("Anum")
    inflected = parsed[0].inflect(tags)
    if inflected:
        words[-1] = inflected.word
    return " ".join(words)


def normalize_numeric_ranges(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        # Малые числа без слова после — перечисление («выпуск 5—7.»), но
        # крупные круглые величины — настоящий диапазон: «50 000—60 000»
        # читается через тире, а не через запятую.
        if len(match.group(1)) >= 4 or len(match.group(2)) >= 4:
            return match.group(0)
        return f"{match.group(1)}, {match.group(2)}"

    return NUMERIC_RANGE_PATTERN.sub(repl, text)


@functools.lru_cache(maxsize=1)
def _year_patterns() -> tuple[ScanPattern, ...]:
    entry_boundary = r"(?<!\w)"
    flags = re.IGNORECASE | re.UNICODE
    return (
        compile_scan(
            rf"{entry_boundary}(?:(?P<prep>в|во|к|ко|с|со|до|от|на|за)\s+)?(?P<year1>\d{{2,4}})\s*(?P<separator>[-–—]|,)\s*(?P<year2>\d{{2,4}})[-–—](?P<suffix>е|х|м|ми)(?:\s+(?P<word>{YEAR_WORD_PATTERN}\b))?",
            flags,
        ),
        compile_scan(
            rf"{entry_boundary}(?P<prep>с|со|от)\s+(?P<year1>{YEAR_ANY_NUMBER_PATTERN})\s+(?P<mid>до|по)\s+(?P<year2>{YEAR_ANY_NUMBER_PATTERN})(?!\d)(?:\s+(?P<word>{YEAR_WORD_PATTERN}\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w)|г\.?(?!\w)))?(?:\s+(?P<era>{ERA_REGEX}))?",
            flags,
        ),
        compile_scan(
            rf"{entry_boundary}(?:(?P<prep>с|со|из|от|в|во)\s+)?(?P<year1>{YEAR_ANY_NUMBER_PATTERN})\s*[-–—]\s*(?P<year2>{YEAR_ANY_NUMBER_PATTERN})\s+(?P<word>{YEAR_WORD_PATTERN}\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w)|г\.?(?!\w))(?:\s+(?P<era>{ERA_REGEX}))?",
            flags,
        ),
        compile_scan(
            rf"{entry_boundary}(?:(?P<prep>{YEAR_PREPOSITION_REGEX})\s+)?(?P<years>{YEAR_RANGE_NUMBER_PATTERN}(?:\s*,\s*{YEAR_RANGE_NUMBER_PATTERN})*\s+и\s+{YEAR_RANGE_NUMBER_PATTERN})\s+(?P<word>{YEAR_WORD_PATTERN}\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w))",
            flags,
        ),
        compile_scan(
            rf"(?:^|(?<=\s)|(?<=[«\"'(]))(\d+)[-–—]({YEAR_SUFFIX_REGEX})(?![а-яА-ЯёЁ\d])(?:\s+({YEAR_WORD_PATTERN}\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w)|г\.?(?!\w)))?",
            flags,
        ),
        compile_scan(
            rf"{entry_boundary}(?:(?P<prep>{YEAR_PREPOSITION_REGEX})\s+)?(?P<year1>\d{{3,4}})\s*"
            rf"(?P<open>[\(\[])(?P<year2>\d{{3,4}})(?P<close>[\)\]])\s+"
            rf"(?P<word>{YEAR_WORD_PATTERN}\b|г\.?(?!\w))",
            flags,
        ),
        compile_scan(
            r"(?P<open>[\(\[])(?P<year>1\d{3}|20\d{2})(?P<close>[\)\]])",
            flags,
        ),
        compile_scan(
            rf"{entry_boundary}(?:(?P<prep>{YEAR_PREPOSITION_REGEX})\s+)?(?P<year>{YEAR_ANY_NUMBER_PATTERN})(?:\s*[-–—](?P<suffix>{YEAR_SUFFIX_REGEX}))?(?:\s+(?P<word>{YEAR_WORD_PATTERN}\b|г\.?(?!\w)))?\s+(?P<era>{ERA_REGEX})",
            flags,
        ),
        compile_scan(
            rf"{entry_boundary}(?:(?P<prep>{YEAR_PREPOSITION_REGEX})\s+)?(?P<year1>{YEAR_ANY_NUMBER_PATTERN})\s*[-–—]\s*(?P<year2>{YEAR_ANY_NUMBER_PATTERN})(?:\s+(?P<word>{YEAR_WORD_PATTERN}\b|г\.?(?!\w)))?\s+(?P<era>{ERA_REGEX})",
            flags,
        ),
        compile_scan(
            rf"{entry_boundary}(?:(?P<prep>{YEAR_PREPOSITION_REGEX})\s+)?(?P<year>{YEAR_ANY_NUMBER_PATTERN})\s+(?P<word>{YEAR_WORD_PATTERN}\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w)|г\.?(?!\w))",
            flags,
        ),
        compile_scan(
            rf"\s*(?:{YEAR_WORD_PATTERN}\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w)|г\.?(?!\w))",
            flags,
        ),
        compile_scan(rf"\s*[-–—](?:{YEAR_SUFFIX_REGEX})\b", flags),
        compile_scan(
            rf"{entry_boundary}(?P<prep>с|со|от)\s+(?P<year1>{YEAR_RANGE_NUMBER_PATTERN})\s+(?P<mid>до|по)\s+(?P<year2>{YEAR_RANGE_NUMBER_PATTERN})(?!\d)",
            flags,
        ),
        compile_scan(
            rf"\b(?P<prep>{YEAR_IMPLICIT_PREP_REGEX})\s+(?P<year>{YEAR_IMPLICIT_PREP_PATTERN})(?![\d/])",
            flags,
        ),
        # «Зиму 1856/57 гг.» — разделённое написание двух смежных годов.
        compile_scan(
            rf"{entry_boundary}(?:(?P<prep>{YEAR_PREPOSITION_REGEX})\s+)?(?P<year1>1\d{{3}}|20\d{{2}})/(?P<year2>\d{{2}})\s+(?P<word>{YEAR_WORD_PATTERN}\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w)|г\.?(?!\w))",
            flags,
        ),
        # «Лета 7078 марта…» — архаичная датировка; «лета 2021» — лето года.
        compile_scan(
            rf"(?<!\w)(?P<word>лета)\s+(?P<year>\d{{4}}){SPACED_THOUSANDS_TAIL}{DECIMAL_TAIL}(?!\s*[-–—/])(?!\s+(?:{YEAR_WORD_PATTERN}\b|{YEAR_PLURAL_ABBREV_REGEX}|г\.?(?!\w)))",
            flags,
        ),
        # Голый год после родительного имени месяца: «в марте 1771: …».
        compile_scan(
            rf"(?<!\w)(?P<year>1\d{{3}}|20\d{{2}}){SPACED_THOUSANDS_TAIL}{DECIMAL_TAIL}(?!\s*[-–—/])(?!\s+(?:{YEAR_WORD_PATTERN}\b|{YEAR_PLURAL_ABBREV_REGEX}|г\.?(?!\w)))",
            flags,
        ),
        # «1709 июня 24-го дня» — в архаичной датировке год стоит перед
        # месяцем; слово «года» восстанавливается при чтении.
        compile_scan(
            rf"(?<!\w)(?P<year>1\d{{3}}|20\d{{2}})(?=\s+{_month_gent_fragment()}\s+\d{{1,2}}(?!\d))",
            flags,
        ),
        # Библиографический год после места издания: «, СПБ, 1850.»
        compile_scan(
            r"(?<![\w.])(?P<place>(?:СПб|СПБ|Пг|Птг|[МЛ]\.)\.?\s*,\s*)(?P<year>1\d{3}|20\d{2})(?=\s*(?:[.;)\]]|$))",
            re.UNICODE,
        ),
    )


def normalize_years(text: str) -> str:
    if not any(char.isdecimal() for char in text):
        return text

    (
        pattern_range_decade,
        pattern_s_po,
        pattern_range,
        pattern_multiple_years,
        pattern_suffix,
        pattern_dual_dating,
        pattern_parenthesized_year,
        pattern_era_year,
        pattern_era_range_shared,
        pattern_year_word,
        explicit_year_word_tail_pattern,
        year_suffix_tail_pattern,
        pattern_ot_do_implicit,
        pattern_prep_year_implicit,
        pattern_split_year,
        pattern_leta_year,
        pattern_month_year,
        pattern_year_before_month,
        pattern_bibliographic_year,
    ) = _year_patterns()

    def infer_suffix_case(match: re.Match[str], suffix: str) -> str:
        default_case = YEAR_SUFFIX_TO_CASE.get(suffix, "nomn")
        if suffix not in {"х", "м"}:
            return default_case
        left_context = text[max(0, match.start() - 30) : match.start()]
        prep_match = re.search(
            r"(?:^|[\s«\"'(])(?P<prep>в|во|о|об|на|к|ко|с|со|до|от|из|по)\s*$",
            left_context,
            re.IGNORECASE | re.UNICODE,
        )
        if not prep_match:
            return default_case
        prep = prep_match.group("prep").lower()
        # «на» задаёт местный падеж так же, как «в»: «на 81-м году жизни» —
        # «на восемьдесят первом году», а не «первым».
        if suffix == "х":
            if prep in {"в", "во", "о", "об", "на"}:
                return "loct"
            if prep in {"с", "со", "до", "от", "из"}:
                return "gent"
        if suffix == "м":
            if prep in {"в", "во", "о", "об", "на"}:
                return "loct"
            if prep in {"к", "ко", "по"}:
                return "datv"
        return default_case

    def replace_range_decade(m: re.Match[str]) -> str:
        if m.group("separator") == "," and not m.group("word"):
            return m.group(0)
        case = YEAR_SUFFIX_TO_CASE.get(m.group("suffix").lower(), "nomn")
        result = (
            (f"{m.group('prep')} " if m.group("prep") else "")
            + f"{year_to_ordinal_words(int(m.group('year1')), case, True)} — {year_to_ordinal_words(int(m.group('year2')), case, True)}"
        )
        if m.group("word"):
            result += f" {_canonicalize_year_word(m.group('word'))}"
        return result

    def replace_s_po(m: re.Match[str]) -> str:
        prep = m.group("prep")
        mid = m.group("mid")
        year1 = int(m.group("year1"))
        year2 = int(m.group("year2"))
        era_text = (
            _normalize_era_marker(m.group("era")) if m.group("era") is not None else None
        )
        if m.group("era") is not None and era_text is None:
            return m.group(0)
        if (
            era_text is None
            and not m.group("word")
            and not (is_plausible_year(year1) and is_plausible_year(year2))
        ):
            return m.group(0)
        if era_text is None and not m.group("word") and not should_treat_as_implicit_year(
            text,
            m.end(),
            explicit_year_word_pattern=explicit_year_word_tail_pattern,
            year_suffix_tail_pattern=year_suffix_tail_pattern,
        ):
            return m.group(0)
        case2 = "accs" if mid.lower() == "по" else "gent"
        result = (
            f"{prep} {year_to_ordinal_words(year1, 'gent')} "
            f"{mid} {year_to_ordinal_words(year2, case2)}"
        )
        word = m.group("word")
        if word:
            word = _canonicalize_year_word(word)
        if word:
            word_lower = word.lower()
            if word_lower in ("г.", "г"):
                word_norm = "год"
                word_inflected = YEAR_WORD_FORMS.get((word_norm, case2), word_norm)
            elif re.fullmatch(YEAR_PLURAL_ABBREV_REGEX, word_lower):
                word_norm = "годы"
                word_inflected = YEAR_WORD_FORMS.get((word_norm, case2), word_norm)
            else:
                word_inflected = word
            keep_terminal_dot = should_keep_terminal_abbreviation_dot(text, m.end())
            if (
                keep_terminal_dot
                and word.endswith(".")
                and not word_inflected.endswith(".")
            ):
                word_inflected += "."
            result += f" {word_inflected}"
        elif era_text is not None:
            result += f" {YEAR_WORD_FORMS.get(('год', case2), 'год')}"
        if era_text is not None:
            result += f" {era_text}"
            if _should_keep_era_terminal_dot(text, m):
                result += "."
        return result

    def replace_suffix(m: re.Match[str]) -> str:
        year = int(m.group(1))
        suffix = m.group(2).lower()
        word = m.group(3)
        if word:
            word = _canonicalize_year_word(word)
        case = infer_suffix_case(m, suffix)
        plural = suffix in PLURAL_SUFFIXES and not (suffix == "м" and case == "loct")
        if plural:
            if year < 100 and not word:
                return m.group(0)
            # Bare decade-like forms such as "1980-х" are common for years,
            # but model codes like "6301-Х" should not be routed through
            # year normalization when there is no explicit year word.
            if not word and not is_plausible_year(year):
                return m.group(0)
            # A decade needs at least two digits: rounding a single digit down
            # turned "5-х годах" into "нулевых годах". The "-х" suffix is still a
            # plural ordinal, so render it as one instead of rounding.
            #
            # «-м» омонимичен: дательный множественного («к 1990-м годам») и
            # творительный единственного («с 2023-м годом»). Десятилетием может
            # быть только круглый год, иначе округление молча меняет год:
            # «с 2023-м» читалось «двадцатым». Формы при этом совпадают —
            # у порядковых мужского рода дательный множественного и
            # творительный единственного равны («двадцать третьим»), поэтому
            # падеж остаётся выведенным по суффиксу.
            if year >= 10 and not (suffix == "м" and year % 10):
                year = (year // 10) * 10
        elif not word and not is_plausible_year(year):
            return m.group(0)
        result = year_to_ordinal_words(year, case, plural)
        if word:
            word_lower = word.lower()
            if word_lower in ("г.", "г"):
                word_norm = "год"
                inflected = YEAR_WORD_FORMS.get((word_norm, case), word_norm)
            elif re.fullmatch(YEAR_PLURAL_ABBREV_REGEX, word_lower):
                word_norm = "годы"
                inflected = YEAR_WORD_FORMS.get((word_norm, case), word_norm)
            else:
                inflected = word
            if word.endswith(".") and should_keep_terminal_abbreviation_dot(text, m.end()):
                inflected += "."
            result += f" {inflected}"
        return result

    def replace_multiple_years(m: re.Match[str]) -> str:
        prep = m.group("prep")
        years_text = m.group("years")
        word = _canonicalize_year_word(m.group("word"))
        word_lower = word.lower()
        if re.fullmatch(YEAR_PLURAL_ABBREV_REGEX, word_lower):
            case = PREPOSITIONS_TO_CASE.get(prep.lower(), "nomn") if prep else "nomn"
            word_norm = "годы"
        else:
            case = YEAR_WORD_TO_CASE.get(word_lower, "nomn")
            if prep and case == "nomn":
                case = PREPOSITIONS_TO_CASE.get(prep.lower(), case)
            word_norm = "годы" if word_lower.startswith("год") else word

        # IGNORECASE — как и в самом паттерне: «1812 И 1813 годы» иначе не
        # разбивалось, и первый год оставался ненормализованным.
        parts = re.split(r"(\s*,\s*|\s+и\s+)", years_text, flags=re.IGNORECASE)
        rendered_parts: list[str] = []
        for part in parts:
            stripped = part.strip()
            if not stripped:
                continue
            if stripped.isdigit():
                rendered_parts.append(year_to_ordinal_words(int(stripped), case))
            else:
                rendered_parts.append(part)

        prefix = f"{prep} " if prep else ""
        inflected_word = YEAR_WORD_FORMS.get((word_norm, case), word_norm)
        return f"{prefix}{''.join(rendered_parts)} {inflected_word}"

    def replace_era_year(m: re.Match[str]) -> str:
        prep = m.group("prep")
        word = m.group("word")
        if word:
            word = _canonicalize_year_word(word)
        suffix = m.group("suffix")
        era_text = _normalize_era_marker(m.group("era"))
        if era_text is None:
            return m.group(0)
        if suffix:
            case = YEAR_SUFFIX_TO_CASE.get(suffix.lower(), "nomn")
            if suffix.lower() == "м":
                case = "loct"
        elif word:
            word_lower = word.lower()
            if word_lower in ("г.", "г"):
                case = PREPOSITIONS_TO_CASE.get(prep.lower(), "nomn") if prep else "nomn"
            else:
                case = _resolve_explicit_year_word_case(prep, word)
        elif prep:
            case = PREPOSITIONS_TO_CASE.get(prep.lower(), "nomn")
        else:
            case = "nomn"
        if word and word.lower() in ("г.", "г"):
            word_form = YEAR_WORD_FORMS.get(("год", case), "год")
        elif word:
            word_form = word
        else:
            word_form = YEAR_WORD_FORMS.get(("год", case), "год")
        prefix = f"{prep} " if prep else ""
        result = (
            f"{prefix}{year_to_ordinal_words(int(m.group('year')), case)} "
            f"{word_form} {era_text}"
        )
        if _should_keep_era_terminal_dot(text, m):
            result += "."
        return result

    def replace_era_range_shared(m: re.Match[str]) -> str:
        prep = m.group("prep")
        word = m.group("word")
        if word:
            word = _canonicalize_year_word(word)
        era_text = _normalize_era_marker(m.group("era"))
        if era_text is None:
            return m.group(0)
        if word:
            word_lower = word.lower()
            if word_lower in ("г.", "г"):
                case = PREPOSITIONS_TO_CASE.get(prep.lower(), "nomn") if prep else "nomn"
            else:
                case = _resolve_explicit_year_word_case(prep, word)
        elif prep:
            case = PREPOSITIONS_TO_CASE.get(prep.lower(), "nomn")
        else:
            case = "nomn"

        if word and word.lower() in ("г.", "г"):
            word_form = YEAR_WORD_FORMS.get(("год", case), "год")
        elif word:
            word_form = word
        else:
            word_form = YEAR_WORD_FORMS.get(("год", case), "год")

        prefix = f"{prep} " if prep else ""
        result = (
            f"{prefix}{year_to_ordinal_words(int(m.group('year1')), case)} — "
            f"{year_to_ordinal_words(int(m.group('year2')), case)} "
            f"{word_form} {era_text}"
        )
        if _should_keep_era_terminal_dot(text, m):
            result += "."
        return result

    def replace_dual_dating(m: re.Match[str]) -> str:
        """Render «7092 (1582) года» — one date given in two calendars.

        The year word stands after the bracket and governs both numbers: they
        name the same date, so the bracketed equivalent reads as an ordinal in
        the same case as the leading year. Rendering both numbers here also
        keeps the date stage from appending a second «года» to the leading year.
        """
        year1 = int(m.group("year1"))
        year2 = int(m.group("year2"))
        if not is_plausible_year(year2):
            return m.group(0)
        prep = m.group("prep")
        case = _resolve_explicit_year_word_case(prep, m.group("word"))
        if prep is None and _follows_month_name(text, m.start()):
            # A month name before the year makes the whole date genitive, which
            # an abbreviated «г.» after the bracket cannot show by itself.
            case = "gent"
        # Оба числа называют одну дату, поэтому эквивалент в скобках читается
        # тем же порядковым в том же падеже, что и ведущий год.
        bracketed = year_to_ordinal_words(year2, case)
        word = _canonicalize_year_word(m.group("word"))
        if word.startswith("г."):
            word = YEAR_WORD_FORMS[("год", resolve_primary_case(case))]
        return (
            f"{prep + ' ' if prep else ''}{year_to_ordinal_words(year1, case)} "
            f"{m.group('open')}{bracketed}{m.group('close')} {word}"
        )

    def replace_parenthesized_year(m: re.Match[str]) -> str:
        year = int(m.group("year"))
        if not is_plausible_year(year):
            return m.group(0)
        left_context = text[max(0, m.start() - 40) : m.start()]
        left_tokens = [
            normalize_context_token(token)
            for token in simple_tokenize(left_context)
            if normalize_context_token(token)
        ]
        if len(left_tokens) >= 2 and left_tokens[-2] in {"под", "при"}:
            return f"{m.group('open')}{year_to_ordinal_words(year)}{m.group('close')}"
        try:
            rendered = num2words.num2words(year, lang="ru")
        except Exception as exc:
            logger.debug("num2words failed for year %r: %s", year, exc)
            rendered = str(year)
        return f"{m.group('open')}{rendered}{m.group('close')}"

    def replace_with_word(m: re.Match[str]) -> str:
        prep = m.group("prep")
        year = int(m.group("year"))
        word = _canonicalize_year_word(m.group("word"))
        word_lower = word.lower()
        if word_lower in ("г.", "г"):
            word_norm = "год"
            is_abbrev = True
            plural = False
        elif re.fullmatch(YEAR_PLURAL_ABBREV_REGEX, word_lower):
            word_norm = "годы"
            is_abbrev = True
            plural = True
        else:
            word_norm = word
            is_abbrev = False
            plural = word_lower in ("годы", "годов", "годам", "годами", "годах")

        # Короткое число перед словом «год» чаще считает длительность («прошло
        # 33 года»), чем называет год. Но счётная форма жёстко связана с
        # последней цифрой: «года» считает только 2–4, «год»/«годом» — только 1.
        # Форма, невозможная при счёте («около 678 года», «под 859 годом»), —
        # это датировка, и она читается порядковым.
        tail_two, last_digit = year % 100, year % 10
        # «года» счётно и в родительном: «в возрасте 21 года» — поэтому для
        # него счётной остаётся вся группа 1–4.
        is_counting_form = (
            word_lower in ("год", "годом") and last_digit == 1 and tail_two != 11
        ) or (
            word_lower == "года"
            and last_digit in {1, 2, 3, 4}
            and tail_two not in {11, 12, 13, 14}
        )
        # Хвост десятичной дроби («1,5 года») — не год, какая бы цифра ни была.
        year_start = m.start("year")
        is_decimal_tail = (
            year_start >= 2
            and text[year_start - 1] in ",."
            and text[year_start - 2].isdigit()
        )
        is_year_naming_word = word_lower == "году" or (
            word_lower in ("год", "года", "годом")
            and not is_counting_form
            and not is_decimal_tail
        )
        if not is_year_naming_word and year < 1000 and not is_abbrev:
            return m.group(0)
        if is_abbrev and has_mass_measurement_context(text, m.start()):
            return m.group(0)
        if (
            is_abbrev
            and prep
            and prep.lower() == "под"
            and _genitive_mass_noun_follows(text, m.end())
        ):
            # «под 30 г. песка» measures grams; the annalistic «под 964 г.
            # записано» is never followed by a bare genitive noun.
            return m.group(0)
        if is_abbrev and year < 1000 and not allows_short_abbreviated_year(
            text,
            m.end(),
            prep,
        ):
            return m.group(0)
        if not is_abbrev:
            case = _resolve_explicit_year_word_case(prep, word)
        elif prep:
            case = PREPOSITIONS_TO_CASE.get(prep.lower(), "nomn")
        else:
            case = "gent"

        ordinal = year_to_ordinal_words(year, case, plural)
        prefix = f"{prep} " if prep else ""
        if is_abbrev:
            result = (
                f"{prefix}{ordinal} {YEAR_WORD_FORMS.get((word_norm, case), word_norm)}"
            )
            if (
                word.endswith(".")
                and should_keep_terminal_abbreviation_dot(text, m.end())
                and not _surname_subject_follows(text, m.end())
            ):
                result += "."
            return result
        return f"{prefix}{ordinal} {word}"

    def replace_range(m: re.Match[str]) -> str:
        prep = m.group("prep")
        word = _canonicalize_year_word(m.group("word"))
        year1 = int(m.group("year1"))
        year2 = int(m.group("year2"))
        era_text = (
            _normalize_era_marker(m.group("era")) if m.group("era") is not None else None
        )
        if m.group("era") is not None and era_text is None:
            return m.group(0)
        word_lower = word.lower()
        if word_lower == "г." or re.fullmatch(YEAR_PLURAL_ABBREV_REGEX, word_lower):
            word_norm = "годы"
            is_abbrev = True
        else:
            word_norm = word
            is_abbrev = False
        if (
            prep is None
            and re.fullmatch(YEAR_PLURAL_ABBREV_REGEX, word_lower)
            and is_plausible_year(year1)
            and is_plausible_year(year2)
        ):
            result = (
                f"с {year_to_ordinal_words(year1, 'gent')} "
                f"по {year_to_ordinal_words(year2, 'accs')} год"
            )
            # Every other branch carries the era marker; without this one
            # "1941-1945 гг. до н. э." silently lost "до н. э." entirely.
            if era_text is not None:
                result += f" {era_text}"
                if _should_keep_era_terminal_dot(text, m):
                    result += "."
            elif word.endswith(".") and should_keep_terminal_abbreviation_dot(
                text, m.end()
            ):
                result += "."
            return result
        if word and not is_abbrev:
            case = YEAR_WORD_TO_CASE.get(word_lower, "nomn")
        elif prep:
            case = PREPOSITIONS_TO_CASE.get(prep.lower(), "nomn")
        else:
            case = "nomn"
        # Диапазон именует конкретные годы, поэтому каждый читается порядковым
        # в единственном числе: «1475—1481 годов» — «…пятого — …первого годов».
        # Порядковые во множественном означают десятилетия, а не границы.
        result = (
            (f"{prep} " if prep else "")
            + f"{year_to_ordinal_words(year1, case)} — {year_to_ordinal_words(year2, case)}"
        )
        if word_norm:
            if is_abbrev:
                inflected = YEAR_WORD_FORMS.get((word_norm, case), word_norm)
                if (
                    era_text is None
                    and word.endswith(".")
                    and not inflected.endswith(".")
                    and should_keep_terminal_abbreviation_dot(text, m.end())
                ):
                    inflected += "."
                result += f" {inflected}"
            else:
                result += f" {word}"
        if era_text is not None:
            result += f" {era_text}"
            if _should_keep_era_terminal_dot(text, m):
                result += "."
        return result

    def replace_ot_do_implicit(m: re.Match[str]) -> str:
        year1 = int(m.group("year1"))
        year2 = int(m.group("year2"))
        if not (is_plausible_year(year1) and is_plausible_year(year2)):
            return m.group(0)
        if not should_treat_as_implicit_year(
            text,
            m.end(),
            explicit_year_word_pattern=explicit_year_word_tail_pattern,
            year_suffix_tail_pattern=year_suffix_tail_pattern,
        ):
            return m.group(0)
        case2 = "accs" if m.group("mid").lower() == "по" else "gent"
        return f"{m.group('prep')} {year_to_ordinal_words(year1, 'gent')} {m.group('mid')} {year_to_ordinal_words(year2, case2)}"

    def replace_prep_year_implicit(m: re.Match[str]) -> str:
        if not should_treat_as_implicit_year(
            text,
            m.end(),
            explicit_year_word_pattern=explicit_year_word_tail_pattern,
            year_suffix_tail_pattern=year_suffix_tail_pattern,
        ):
            return m.group(0)
        prep = m.group("prep").lower()
        if prep in ("в", "во", "о", "об"):
            case = "loct"
        elif prep in ("к", "ко", "по"):
            case = "datv"
        elif prep in ("с", "со", "до", "от", "из"):
            case = "gent"
        elif prep in ("на", "за", "под"):
            case = "accs"
        else:
            case = "nomn"
        return f"{m.group('prep')} {year_to_ordinal_words(int(m.group('year')), case)}"

    def replace_split_year(m: re.Match[str]) -> str:
        """«Зиму 1856/57 гг.» — два смежных года, записанных через дробь."""
        year1 = int(m.group("year1"))
        year2_short = int(m.group("year2"))
        if (year1 + 1) % 100 != year2_short:
            return m.group(0)
        prep = m.group("prep")
        word = _canonicalize_year_word(m.group("word"))
        word_lower = word.lower()
        plural_abbrev = bool(re.fullmatch(YEAR_PLURAL_ABBREV_REGEX, word_lower))
        is_abbrev = plural_abbrev or word_lower in ("г.", "г")
        if not is_abbrev:
            case = YEAR_WORD_TO_CASE.get(word_lower, "nomn")
        elif prep:
            case = PREPOSITIONS_TO_CASE.get(prep.lower(), "nomn")
        else:
            case = "gent"
        result = (
            (f"{prep} " if prep else "")
            + f"{year_to_ordinal_words(year1, case)} — "
            + f"{year_to_ordinal_words(year2_short, case)}"
        )
        if is_abbrev:
            word_norm = "годы" if plural_abbrev else "год"
            inflected = YEAR_WORD_FORMS.get((word_norm, case), word_norm)
            if word.endswith(".") and should_keep_terminal_abbreviation_dot(
                text, m.end()
            ):
                inflected += "."
            result += f" {inflected}"
        else:
            result += f" {word}"
        return result

    def replace_leta_year(m: re.Match[str]) -> str:
        year = int(m.group("year"))
        if not (is_plausible_year(year) or 5500 <= year <= _BYZANTINE_YEAR_MAX):
            return m.group(0)
        if _counted_noun_follows(text, m.end(), year):
            return m.group(0)
        return f"{m.group('word')} {year_to_ordinal_words(year, 'gent')}"

    def replace_month_year(m: re.Match[str]) -> str:
        if not _month_name_precedes(text, m.start()):
            return m.group(0)
        year = int(m.group("year"))
        if _counted_noun_follows(text, m.end(), year):
            return m.group(0)
        return year_to_ordinal_words(year, "gent")

    def replace_bibliographic_year(m: re.Match[str]) -> str:
        return f"{m.group('place')}{year_to_ordinal_words(int(m.group('year')))}"

    def replace_year_before_month(m: re.Match[str]) -> str:
        return f"{year_to_ordinal_words(int(m.group('year')), 'gent')} года"

    text = pattern_split_year.sub(replace_split_year, text)
    text = pattern_range_decade.sub(replace_range_decade, text)
    text = pattern_s_po.sub(replace_s_po, text)
    text = pattern_range.sub(replace_range, text)
    text = pattern_multiple_years.sub(replace_multiple_years, text)
    text = pattern_dual_dating.sub(replace_dual_dating, text)
    text = pattern_parenthesized_year.sub(replace_parenthesized_year, text)
    text = pattern_era_range_shared.sub(replace_era_range_shared, text)
    text = pattern_era_year.sub(replace_era_year, text)
    text = pattern_suffix.sub(replace_suffix, text)
    text = pattern_ot_do_implicit.sub(replace_ot_do_implicit, text)
    text = pattern_prep_year_implicit.sub(replace_prep_year_implicit, text)
    text = pattern_year_before_month.sub(replace_year_before_month, text)
    text = pattern_leta_year.sub(replace_leta_year, text)
    text = pattern_month_year.sub(replace_month_year, text)
    text = pattern_bibliographic_year.sub(replace_bibliographic_year, text)
    text = pattern_year_word.sub(replace_with_word, text)

    def replace_orphan_plural_abbrev(m: re.Match[str]) -> str:
        case = _gospoda_case_around(m.string, m.start(), m.end())
        if case is not None:
            rendered = _render_gospoda(case)
            if rendered is not None:
                return rendered
        return "годы"

    return re.sub(
        rf"(?<![А-Яа-яA-Za-z_]){YEAR_PLURAL_ABBREV_REGEX}(?!\w)",
        replace_orphan_plural_abbrev,
        text,
        flags=re.IGNORECASE,
    )
