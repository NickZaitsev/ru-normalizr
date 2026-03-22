from __future__ import annotations

import functools
import re

import num2words

from ._morph import get_morph
from .options import NormalizeOptions
from .text_context import normalize_context_token, simple_tokenize
from .years_context import (
    YEAR_ANY_NUMBER_PATTERN,
    YEAR_IMPLICIT_PREP_PATTERN,
    YEAR_RANGE_NUMBER_PATTERN,
    is_plausible_year,
    should_treat_as_implicit_year,
)

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
}
NUMERIC_RANGE_PATTERN = re.compile(
    r"(\d+)\s*[—–]\s*(\d+)(?!\d)(?!\s*[а-яА-ЯёЁa-zA-Z%°$€₽Ω])"
)
YEAR_PREPOSITION_REGEX = r"в|во|о|об|к|ко|с|со|до|от|за|на|по|между|около"
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

    rest = source_text[match.end() :]
    stripped_rest = rest.lstrip()
    if not stripped_rest:
        return True
    if "\n" in rest[: len(rest) - len(stripped_rest)]:
        return True
    next_char = stripped_rest[:1]
    if next_char in '.!?…)"»”]}':
        return True
    if next_char.isupper():
        return True
    if (
        next_char in '"»”)]}'
        and len(stripped_rest) > 1
        and stripped_rest[1:2].isupper()
    ):
        return True
    return False


def _resolve_explicit_year_word_case(prep: str | None, word: str) -> str:
    word_lower = word.lower()
    if word_lower == "году" and prep:
        return "datv" if prep.lower() in ("к", "ко") else "loct"
    return YEAR_WORD_TO_CASE.get(word_lower, "nomn")


@functools.lru_cache(maxsize=1024)
def year_to_ordinal_words(year: int, case: str = "nomn", plural: bool = False) -> str:
    normalized_case = "nomn" if case == "accs" and not plural else case
    cases_map = {
        "nomn": "nominative",
        "gent": "genitive",
        "datv": "dative",
        "accs": "accusative",
        "ablt": "instrumental",
        "loct": "prepositional",
    }
    if year >= 10000 and not plural and year % 1000:
        high = (year // 1000) * 1000
        tail = year % 1000
        try:
            high_words = num2words.num2words(
                high,
                lang="ru",
                case=cases_map.get(normalized_case, "nominative"),
            )
            tail_words = year_to_ordinal_words(tail, normalized_case)
            return f"{high_words} {tail_words}"
        except Exception:
            pass
    if normalized_case in cases_map:
        try:
            return num2words.num2words(
                year,
                lang="ru",
                to="ordinal",
                case=cases_map[normalized_case],
                plural=plural,
            )
        except Exception:
            pass
    try:
        ordinal = num2words.num2words(year, lang="ru", to="ordinal")
    except Exception:
        return str(year)
    words = ordinal.split()
    if not words:
        return ordinal
    parsed = get_morph().parse(words[-1])
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
    return NUMERIC_RANGE_PATTERN.sub(lambda m: f"{m.group(1)}, {m.group(2)}", text)


def normalize_years(text: str, options: NormalizeOptions | None = None) -> str:
    active = options or NormalizeOptions()
    if not active.enable_year_normalization:
        return text

    pattern_range_decade = re.compile(
        r"(?:(?P<prep>в|во|к|ко|с|со|до|от|на|за)\s+)?(?P<year1>\d{2,4})\s*(?:[-–—]|,)\s*(?P<year2>\d{2,4})[-–—](?P<suffix>е|х|м|ми)(?:\s+(?P<word>год[а-яё]*\b))?",
        re.IGNORECASE | re.UNICODE,
    )
    pattern_s_po = re.compile(
        rf"(?P<prep>с|со|от)\s+(?P<year1>{YEAR_ANY_NUMBER_PATTERN})\s+(?P<mid>до|по)\s+(?P<year2>{YEAR_ANY_NUMBER_PATTERN})(?!\d)(?:\s+(?P<word>год[а-яё]*\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w)|г\.?(?!\w)))?(?:\s+(?P<era>{ERA_REGEX}))?",
        re.IGNORECASE | re.UNICODE,
    )
    pattern_range = re.compile(
        rf"(?:(?P<prep>с|со|из|от|в|во)\s+)?(?P<year1>{YEAR_ANY_NUMBER_PATTERN})\s*[-–—]\s*(?P<year2>{YEAR_ANY_NUMBER_PATTERN})\s+(?P<word>год[а-яё]*\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w)|г\.?(?!\w))(?:\s+(?P<era>{ERA_REGEX}))?",
        re.IGNORECASE | re.UNICODE,
    )
    pattern_multiple_years = re.compile(
        rf"(?:(?P<prep>{YEAR_PREPOSITION_REGEX})\s+)?(?P<years>{YEAR_RANGE_NUMBER_PATTERN}(?:\s*,\s*{YEAR_RANGE_NUMBER_PATTERN})*\s+и\s+{YEAR_RANGE_NUMBER_PATTERN})\s+(?P<word>год[а-яё]*\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w))",
        re.IGNORECASE | re.UNICODE,
    )
    pattern_suffix = re.compile(
        rf"(?:^|(?<=\s)|(?<=[«\"'(]))(\d+)[-–—]({YEAR_SUFFIX_REGEX})(?![а-яА-ЯёЁ\d])(?:\s+(год[а-яё]*\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w)|г\.?(?!\w)))?",
        re.IGNORECASE | re.UNICODE,
    )
    pattern_parenthesized_year = re.compile(
        r"(?P<open>[\(\[])(?P<year>1\d{3}|20\d{2})(?P<close>[\)\]])",
        re.IGNORECASE | re.UNICODE,
    )
    pattern_era_year = re.compile(
        rf"(?:(?P<prep>{YEAR_PREPOSITION_REGEX})\s+)?(?P<year>{YEAR_ANY_NUMBER_PATTERN})(?:\s*[-–—](?P<suffix>{YEAR_SUFFIX_REGEX}))?(?:\s+(?P<word>год[а-яё]*\b|г\.?(?!\w)))?\s+(?P<era>{ERA_REGEX})",
        re.IGNORECASE | re.UNICODE,
    )
    pattern_era_range_shared = re.compile(
        rf"(?:(?P<prep>{YEAR_PREPOSITION_REGEX})\s+)?(?P<year1>{YEAR_ANY_NUMBER_PATTERN})\s*[-–—]\s*(?P<year2>{YEAR_ANY_NUMBER_PATTERN})(?:\s+(?P<word>год[а-яё]*\b|г\.?(?!\w)))?\s+(?P<era>{ERA_REGEX})",
        re.IGNORECASE | re.UNICODE,
    )
    pattern_year_word = re.compile(
        rf"(?:(?P<prep>{YEAR_PREPOSITION_REGEX})\s+)?(?P<year>{YEAR_ANY_NUMBER_PATTERN})\s+(?P<word>год[а-яё]*\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w)|г\.?(?!\w))",
        re.IGNORECASE | re.UNICODE,
    )
    explicit_year_word_tail_pattern = re.compile(
        rf"\s*(?:год[а-яё]*\b|{YEAR_PLURAL_ABBREV_REGEX}(?!\w)|г\.?(?!\w))",
        re.IGNORECASE | re.UNICODE,
    )
    year_suffix_tail_pattern = re.compile(
        rf"\s*[-–—](?:{YEAR_SUFFIX_REGEX})\b",
        re.IGNORECASE | re.UNICODE,
    )
    pattern_ot_do_implicit = re.compile(
        rf"(?P<prep>с|со|от)\s+(?P<year1>{YEAR_RANGE_NUMBER_PATTERN})\s+(?P<mid>до|по)\s+(?P<year2>{YEAR_RANGE_NUMBER_PATTERN})(?!\d)",
        re.IGNORECASE | re.UNICODE,
    )
    pattern_prep_year_implicit = re.compile(
        rf"\b(?P<prep>{YEAR_IMPLICIT_PREP_REGEX})\s+(?P<year>{YEAR_IMPLICIT_PREP_PATTERN})(?!\d)",
        re.IGNORECASE | re.UNICODE,
    )

    def infer_suffix_case(match: re.Match[str], suffix: str) -> str:
        default_case = YEAR_SUFFIX_TO_CASE.get(suffix, "nomn")
        if suffix not in {"х", "м"}:
            return default_case
        left_context = text[max(0, match.start() - 30) : match.start()]
        prep_match = re.search(
            r"(?:^|[\s«\"'(])(?P<prep>в|во|о|об|к|ко|с|со|до|от|из|по)\s*$",
            left_context,
            re.IGNORECASE | re.UNICODE,
        )
        if not prep_match:
            return default_case
        prep = prep_match.group("prep").lower()
        if suffix == "х":
            if prep in {"в", "во", "о", "об"}:
                return "loct"
            if prep in {"с", "со", "до", "от", "из"}:
                return "gent"
        if suffix == "м":
            if prep in {"в", "во", "о", "об"}:
                return "loct"
            if prep in {"к", "ко", "по"}:
                return "datv"
        return default_case

    def replace_range_decade(m: re.Match[str]) -> str:
        case = YEAR_SUFFIX_TO_CASE.get(m.group("suffix").lower(), "nomn")
        result = (
            (f"{m.group('prep')} " if m.group("prep") else "")
            + f"{year_to_ordinal_words(int(m.group('year1')), case, True)} — {year_to_ordinal_words(int(m.group('year2')), case, True)}"
        )
        if m.group("word"):
            result += f" {m.group('word')}"
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
            word_lower = word.lower()
            if word_lower in ("г.", "г"):
                word_norm = "год"
                word_inflected = YEAR_WORD_FORMS.get((word_norm, case2), word_norm)
            elif re.fullmatch(YEAR_PLURAL_ABBREV_REGEX, word_lower):
                word_norm = "годы"
                word_inflected = YEAR_WORD_FORMS.get((word_norm, case2), word_norm)
            else:
                word_inflected = word
            tail = text[m.end() :].lstrip()
            keep_terminal_dot = not tail or tail[:1].isupper()
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
        plural = suffix in PLURAL_SUFFIXES
        case = infer_suffix_case(m, suffix)
        if plural:
            if year < 100 and not word:
                return m.group(0)
            # Bare decade-like forms such as "1980-х" are common for years,
            # but model codes like "6301-Х" should not be routed through
            # year normalization when there is no explicit year word.
            if not word and not is_plausible_year(year):
                return m.group(0)
            year = (year // 10) * 10
        elif not word and not is_plausible_year(year):
            return m.group(0)
        result = year_to_ordinal_words(year, case, plural)
        if word:
            word_lower = word.lower()
            if word_lower == "г.":
                word_norm = "год"
                inflected = YEAR_WORD_FORMS.get((word_norm, case), word_norm)
            elif re.fullmatch(YEAR_PLURAL_ABBREV_REGEX, word_lower):
                word_norm = "годы"
                inflected = YEAR_WORD_FORMS.get((word_norm, case), word_norm)
            else:
                inflected = word
            result += f" {inflected}"
        return result

    def replace_multiple_years(m: re.Match[str]) -> str:
        prep = m.group("prep")
        years_text = m.group("years")
        word = m.group("word")
        word_lower = word.lower()
        if re.fullmatch(YEAR_PLURAL_ABBREV_REGEX, word_lower):
            case = PREPOSITIONS_TO_CASE.get(prep.lower(), "nomn") if prep else "nomn"
            word_norm = "годы"
        else:
            case = YEAR_WORD_TO_CASE.get(word_lower, "nomn")
            if prep and case == "nomn":
                case = PREPOSITIONS_TO_CASE.get(prep.lower(), case)
            word_norm = "годы" if word_lower.startswith("год") else word

        parts = re.split(r"(\s*,\s*|\s+и\s+)", years_text)
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
                case = PREPOSITIONS_TO_CASE.get(
                    prep.lower(), "nomn"
                )
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
        era_text = _normalize_era_marker(m.group("era"))
        if era_text is None:
            return m.group(0)
        if word:
            word_lower = word.lower()
            if word_lower in ("г.", "г"):
                case = PREPOSITIONS_TO_CASE.get(
                    prep.lower(), "nomn"
                )
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
        except Exception:
            rendered = str(year)
        return f"{m.group('open')}{rendered}{m.group('close')}"

    def replace_with_word(m: re.Match[str]) -> str:
        prep = m.group("prep")
        year = int(m.group("year"))
        word = m.group("word")
        word_lower = word.lower()
        if word_lower == "г.":
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

        is_year_prepositional = word_lower == "году" and prep
        if not is_year_prepositional and year < 1000 and not is_abbrev:
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
            return (
                f"{prefix}{ordinal} {YEAR_WORD_FORMS.get((word_norm, case), word_norm)}"
            )
        return f"{prefix}{ordinal} {word}"

    def replace_range(m: re.Match[str]) -> str:
        prep = m.group("prep")
        word = m.group("word")
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
        if word and not is_abbrev:
            case = YEAR_WORD_TO_CASE.get(word_lower, "nomn")
        elif prep:
            case = PREPOSITIONS_TO_CASE.get(prep.lower(), "nomn")
        else:
            case = "nomn"
        result = (
            (f"{prep} " if prep else "")
            + f"{year_to_ordinal_words(int(m.group('year1')), case, True)} — {year_to_ordinal_words(int(m.group('year2')), case, True)}"
        )
        if word_norm:
            if is_abbrev:
                inflected = YEAR_WORD_FORMS.get((word_norm, case), word_norm)
                if word.endswith(".") and not inflected.endswith("."):
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

    text = pattern_range_decade.sub(replace_range_decade, text)
    text = pattern_s_po.sub(replace_s_po, text)
    text = pattern_range.sub(replace_range, text)
    text = pattern_multiple_years.sub(replace_multiple_years, text)
    text = pattern_parenthesized_year.sub(replace_parenthesized_year, text)
    text = pattern_era_range_shared.sub(replace_era_range_shared, text)
    text = pattern_era_year.sub(replace_era_year, text)
    text = pattern_suffix.sub(replace_suffix, text)
    text = pattern_ot_do_implicit.sub(replace_ot_do_implicit, text)
    text = pattern_prep_year_implicit.sub(replace_prep_year_implicit, text)
    text = pattern_year_word.sub(replace_with_word, text)
    return re.sub(
        rf"(?<![А-Яа-яA-Za-z_]){YEAR_PLURAL_ABBREV_REGEX}(?!\w)",
        "годы",
        text,
        flags=re.IGNORECASE,
    )
