from __future__ import annotations

import functools
import logging
import math
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import num2words

from .._log_once import warn_once
from .._morph import (
    MorphParse,
    canonicalize_case,
    canonicalize_grammemes,
    first_parse_required,
    parse_word,
    select_parse,
)
from ..preprocess_utils import (
    NEGATIVE_NUMBER_PLACEHOLDER,
)
from ..text_context import PUNCT_STRIP, normalize_context_token
from ..text_scan import compile_scan, first_non_whitespace_index
from ._constants import (
    ALL_UNITS,
    ENTITY_DEFAULT_CASE,
    ENTITY_KEYWORDS,
    PREP_CASE,
    TIME_WORDS,
    VERB_CASE,
    UnitDescriptor,
    UnitMorphology,
    is_unit_token,
)
from ._num2words import (
    CARDINAL_GENDER_TO_NUM2WORDS,
    resolve_num2words_case,
    resolve_primary_case,
)
from ._rules import (
    DASH_TOKENS,
    CaseRule,
    NumeralContext,
    deciders,
    dependency_case,
    resolve_case,
)

_TIME_CONTEXT_LEMMAS = frozenset(
    {
        *TIME_WORDS,
        "январь",
        "февраль",
        "март",
        "апрель",
        "май",
        "июнь",
        "июль",
        "август",
        "сентябрь",
        "октябрь",
        "ноябрь",
        "декабрь",
    }
)

#: Партитивно-временные вершины — часть или граница отрезка. Такое слово само
#: управляет родительным справа и потому прозрачно для предлога слева:
#: «до исхода 14 [века]», «с половины 11 века», «до полудня 27 числа».
_PARTITIVE_BOUNDARY_LEMMAS = frozenset(
    {
        "исход",
        "конец",
        "начало",
        "окончание",
        "половина",
        "полдень",
        "полночь",
        "середина",
        "треть",
        "четверть",
    }
)

logger = logging.getLogger(__name__)

#: A decimal literal, matched at the end of a token so a sign or a protection
#: placeholder in front of the digits does not hide it.
DECIMAL_TOKEN_PATTERN = compile_scan(r"\d+[.,]\d+\Z")
NUMERAL_CONTEXT_BARRIERS = {"равно", "="}
#: Sentence-final punctuation ends the region a numeral may look back over.
#: Nothing before it can govern the numeral's case, so «Мы завершили деплой.
#: 12 задач осталось.» must not inherit a case from the previous sentence.
SENTENCE_BOUNDARY_TOKENS = frozenset({".", "!", "?", "…", ";"})
MORPHOLOGICAL_CONTEXT_BARRIER_POS = {"VERB", "INFN", "GRND"}
GENITIVE_QUANTITY_GOVERNORS = {
    "выигрыш",
    "датировка",
    "количество",
    "потеря",
    "сумма",
    "стоимость",
    "цена",
}
#: Parameter nouns whose following measurement is an apposition naming the
#: value: «при температуре 660 °C» is «температура = 660 °C». The parameter, not
#: the measurement, is what the preposition governs, so the measurement stays
#: nominative regardless of the case the parameter itself carries. A genitive
#: reading requires an explicit «в» in the source: «при температуре в 660
#: градусов».
MEASURE_PARAMETER_HEADS = frozenset(
    {
        "вес",
        "влажность",
        "высота",
        "глубина",
        "давление",
        "дальность",
        "диаметр",
        "длина",
        "доза",
        "ёмкость",
        "концентрация",
        "масса",
        "мощность",
        "напряжение",
        "плотность",
        "площадь",
        "радиус",
        "скорость",
        "температура",
        "толщина",
        "частота",
        "ширина",
    }
)
#: Quantity nouns that govern a genitive of their own inside the «в …» frame:
#: «в возрасте двадцати пяти лет», «в количестве пяти штук». Unlike the
#: parameter nouns above these are relational — «возраст чего», «размер чего» —
#: so the quantity is their complement, not an apposition.
LOCATIVE_GENITIVE_QUANTITY_HEADS = frozenset(
    {
        "возраст",
        "количество",
        "размер",
        "состав",
        "сумма",
        "число",
    }
)
#: Nouns whose immediately following bare number labels them instead of
#: counting them. The label never inherits the noun's case: "ключи от квартиры
#: тридцать пять", not "от квартиры тридцати пяти". Postal elements are here
#: because the address stage now expands "кв. 35" into a declinable noun.
LABEL_NOUN_LEMMAS = frozenset(
    {
        "том",
        "номер",
        "дом",
        "корпус",
        "квартира",
        "строение",
        "владение",
        "помещение",
        "офис",
        "этаж",
        "подъезд",
        "кабинет",
        "комната",
        "палата",
        "литера",
        "страница",
        # Ссылочные существительные метят номером ту же запись, что «том» и
        # «страница»: «в статье пять», «в таблице три» — номер остаётся
        # именительным и падежа от фразы не получает.
        "статья",
        "пункт",
        "подпункт",
        "таблица",
        "приложение",
        "рисунок",
    }
)
#: Gender of the magnitude nouns num2words emits, for agreement of the unit
#: word before them ("одна тысяча" but "один миллион").
MAGNITUDE_GENDERS = {
    "тысяча": "femn",
    "миллион": "masc",
    "миллиард": "masc",
    "триллион": "masc",
    "биллион": "masc",
}
#: Numeric value of each magnitude noun, used to recover its own multiplier from
#: the whole number. "биллион" is deliberately absent: num2words never emits it
#: and its scale is ambiguous (10^9 short scale vs 10^12 long scale).
MAGNITUDE_SCALES = {
    "тысяча": 10**3,
    "миллион": 10**6,
    "миллиард": 10**9,
    "триллион": 10**12,
}


@dataclass(frozen=True, slots=True)
class _NumeralTokenContext:
    left_scan_starts: tuple[int, ...]
    #: Памятка решений на весь поток токенов: члены одного ряда спрашивают
    #: падеж друг у друга, и без общей памятки каждый внешний вызов считал бы
    #: всю цепочку заново. Контекст строится по конкретному списку токенов и
    #: живёт, пока живёт он: список на стадии числительных не меняется.
    decisions: dict[tuple[int, int], str | None] = field(default_factory=dict, repr=False)


def _build_numeral_token_context(tokens: list[str]) -> _NumeralTokenContext:
    left_scan_starts: list[int] = []
    current_start = 0
    for position, token in enumerate(tokens):
        left_scan_starts.append(current_start)
        if (
            normalize_context_token(token) in NUMERAL_CONTEXT_BARRIERS
            or token in SENTENCE_BOUNDARY_TOKENS
        ):
            current_start = position + 1
    return _NumeralTokenContext(tuple(left_scan_starts))


def is_integer_token(token: str) -> bool:
    clean_token = token.strip(PUNCT_STRIP)
    if clean_token.startswith(NEGATIVE_NUMBER_PLACEHOLDER):
        clean_token = clean_token[len(NEGATIVE_NUMBER_PLACEHOLDER) :]
    return _normalize_unicode_integer_text(clean_token) is not None


def _normalize_unicode_integer_text(text: str) -> str | None:
    if not text:
        return None

    if text.isascii() and text.isdigit():
        return text

    normalized_digits: list[str] = []
    for char in text:
        digit = unicodedata.digit(char, None)
        if digit is None:
            break
        normalized_digits.append(str(digit))
    else:
        return "".join(normalized_digits)

    if len(text) == 1:
        numeric_value = unicodedata.numeric(text, None)
        if numeric_value is not None and float(numeric_value).is_integer() and numeric_value >= 0:
            return str(int(numeric_value))

    return None


def parse_integer_token(token: str) -> tuple[bool, str] | None:
    clean_token = token.strip(PUNCT_STRIP)
    is_negative = clean_token.startswith(NEGATIVE_NUMBER_PLACEHOLDER)
    if is_negative:
        clean_token = clean_token[len(NEGATIVE_NUMBER_PLACEHOLDER) :]
    normalized = _normalize_unicode_integer_text(clean_token)
    if normalized is None:
        return None
    return is_negative, normalized


def build_number_token(
    token: str, clean_token: str, replacement: str, is_negative: bool
) -> str:
    source = (
        f"{NEGATIVE_NUMBER_PLACEHOLDER}{clean_token}" if is_negative else clean_token
    )
    result = token.replace(source, replacement, 1)
    if result == token:
        stripped_source = token.strip(PUNCT_STRIP)
        result = (
            token.replace(stripped_source, replacement, 1)
            if stripped_source
            else replacement
        )
    if is_negative:
        return f"минус {result}"
    return result


def apply_genitive_plural_heuristic(word: str, pos: str | None) -> str:
    if pos not in {"ADJF", "PRTF"}:
        return word
    lower_word = word.lower()
    if lower_word.endswith("ые"):
        return word[:-2] + ("ЫХ" if word.isupper() else "ых")
    if lower_word.endswith("ие"):
        return word[:-2] + ("ИХ" if word.isupper() else "их")
    if lower_word.endswith("ый") or lower_word.endswith("ой"):
        return word[:-2] + ("ОГО" if word.isupper() else "ого")
    if lower_word.endswith("ий") or lower_word.endswith("ее"):
        return word[:-2] + ("ЕГО" if word.isupper() else "его")
    if lower_word.endswith("ая"):
        return word[:-2] + ("ОЙ" if word.isupper() else "ой")
    if lower_word.endswith("яя"):
        return word[:-2] + ("ЕЙ" if word.isupper() else "ей")
    return word


def safe_inflect(
    parsed_word: MorphParse,
    target_tags: set[str],
    fallback_word: str | None = None,
    pos_filter: set[str] | None = None,
) -> str:
    if fallback_word is None:
        fallback_word = parsed_word.word
    try:
        inflected = parsed_word.inflect(target_tags)
        if inflected:
            return inflected.word
    except Exception as exc:
        warn_once(
            logger,
            f"inflect:{parsed_word.word}:{target_tags}",
            "inflect failed for %r -> %s: %s",
            parsed_word.word,
            target_tags,
            exc,
        )
    pos = parsed_word.tag.POS
    if (
        (pos_filter is None or pos in pos_filter)
        and "gent" in target_tags
        and "plur" in target_tags
        and pos in {"ADJF", "PRTF"}
    ):
        heuristic_result = apply_genitive_plural_heuristic(parsed_word.word, pos)
        if heuristic_result != parsed_word.word:
            return heuristic_result
    return fallback_word


def _unit_descriptor_for_lemma(lemma: str) -> UnitDescriptor:
    return UnitDescriptor(
        lemma=lemma,
        gender="masc",
        category="measure",
        morphology=UnitMorphology(expected_normal_form=lemma),
    )


def inflect_unit_lemma(
    unit: UnitDescriptor | str, target_tags: set[str], *, paucal: bool = False
) -> str:
    """Inflect a unit lemma.

    ``paucal`` says the genitive singular was requested because a numeral
    ending in 2–4 counts the unit. A two-word unit needs that distinction: the
    noun stays genitive singular either way, but its modifier goes plural only
    under a paucal numeral ("три кубических метра"), not after a decimal
    ("три целых пять десятых кубического метра").
    """
    descriptor = (
        unit if isinstance(unit, UnitDescriptor) else _unit_descriptor_for_lemma(unit)
    )
    canonical_tags = frozenset(canonicalize_grammemes(target_tags))
    return _inflect_unit_lemma_cached(descriptor, canonical_tags, paucal)


@functools.lru_cache(maxsize=8192)
def _inflect_unit_lemma_cached(
    descriptor: UnitDescriptor, canonical_tags: frozenset[str], paucal: bool = False
) -> str:
    lemma = descriptor.lemma
    target_tags = set(canonical_tags)

    def pick_preferred_parse(word: str) -> Any | None:
        parsed = parse_word(word)
        if not parsed:
            return None
        for candidate in parsed:
            if "NOUN" in candidate.tag:
                return candidate
        return parsed[0]

    if " " not in lemma:
        morphology = descriptor.morphology
        target_case = canonicalize_case(
            next(
                (
                    grammeme
                    for grammeme in target_tags
                    if grammeme in {"nomn", "gent", "datv", "accs", "ablt", "loct"}
                ),
                None,
            )
        )
        target_number = "plur" if "plur" in target_tags else "sing"
        if morphology.plural_only:
            target_number = "plur"
        if morphology.indeclinable:
            return lemma
        paradigm_form = morphology.form(target_case, target_number)
        if paradigm_form is not None:
            return paradigm_form

        forbidden = set(morphology.forbidden_grammemes)
        if morphology.byte_family:
            forbidden.add("Coun")
        expected_gender = (
            descriptor.gender
            if descriptor.gender in {"masc", "femn", "neut"}
            else None
        )
        required = (
            {morphology.animacy} if morphology.animacy is not None else set()
        )
        selected = select_parse(
            lemma,
            pos="NOUN",
            normal_forms={morphology.expected_normal_form or lemma},
            required_grammemes=required,
            forbidden_grammemes=forbidden,
            preferred_grammemes=morphology.preferred_grammemes,
            gender=expected_gender,
        )
        if selected is None and morphology.morphology_seed is not None:
            selected = select_parse(
                morphology.morphology_seed,
                pos="NOUN",
                normal_forms={morphology.expected_normal_form or lemma},
                required_grammemes=required,
                forbidden_grammemes=forbidden,
                gender=expected_gender,
            )
        if selected is not None:
            inflected = safe_inflect(selected, target_tags, fallback_word="")
            if inflected:
                return inflected
        warn_once(
            logger,
            f"unit-morphology:{lemma}:{target_tags}",
            "No validated morphology form for unit %r and tags %s",
            lemma,
            target_tags,
        )
        return lemma

    parts = lemma.split()
    if len(parts) != 2:
        return lemma

    adj_text, noun_text = parts
    adj_parsed = pick_preferred_parse(adj_text)
    noun_parsed = pick_preferred_parse(noun_text)
    if not adj_parsed or not noun_parsed:
        return lemma

    noun_form = safe_inflect(noun_parsed, target_tags, fallback_word=noun_text)
    adj_tags = {
        tag
        for tag in target_tags
        if tag in {"nomn", "gent", "datv", "accs", "ablt", "loct", "sing", "plur"}
    }
    if paucal and adj_tags == {"gent", "sing"}:
        # A numeral ending in 2–4 keeps the counted noun in the genitive
        # singular but pushes its modifier into the plural: genitive for
        # masculine and neuter ("три кубических метра"), nominative for
        # feminine ("две международные единицы").
        noun_gender = noun_parsed.tag.gender
        adj_tags = {"plur", "nomn"} if noun_gender == "femn" else {"gent", "plur"}
    elif "plur" not in adj_tags:
        noun_gender = noun_parsed.tag.gender
        if noun_gender:
            adj_tags.add(noun_gender)
    adj_form = safe_inflect(
        adj_parsed,
        adj_tags,
        fallback_word=adj_text,
        pos_filter={"ADJF", "PRTF"},
    )
    return f"{adj_form} {noun_form}"


#: Hemisphere letters of a geographic coordinate marker and the axis letters
#: that follow them: «с. ш.», «ю. ш.», «в. д.», «з. д.».
_COORDINATE_HEMISPHERE_LETTERS = frozenset({"с", "ю", "в", "з"})
_COORDINATE_AXIS_LETTERS = frozenset({"ш", "д"})


def is_coordinate_marker(tokens: Sequence[str], index: int) -> bool:
    """Whether a dotted two-letter coordinate marker starts at ``index``.

    The hemisphere letters overlap the temperature scales («с» is both «°С» and
    «северной широты»), so a degree sign followed by a bare «с» is Celsius while
    «42° с. ш.» is a latitude. Only the full dotted pair tells them apart, and
    without the check the latitude swallowed the degree sign and left «°» in the
    output.
    """
    if index + 3 >= len(tokens):
        return False
    hemisphere = tokens[index].lower().strip(PUNCT_STRIP)
    axis = tokens[index + 2].lower().strip(PUNCT_STRIP)
    return (
        hemisphere in _COORDINATE_HEMISPHERE_LETTERS
        and tokens[index + 1] == "."
        and axis in _COORDINATE_AXIS_LETTERS
        and tokens[index + 3] == "."
    )


def is_case_reliable_noun(parsed_word: Any) -> bool:
    return "NOUN" in parsed_word.tag and "Fixd" not in parsed_word.tag


def top_scoring_verb_parses(parses: Sequence[MorphParse]) -> list[MorphParse]:
    """Verb parses that are as likely as the word's best parse overall.

    A low-frequency verb homonym of a noun must not govern the numeral's case:
    in "на встречу пришли 3 сотрудницы" the noun "встреча" outscores the verb
    "встретить" by an order of magnitude, so the phrase has no governing verb.
    """
    if not parses:
        return []
    top_score = max(candidate.score for candidate in parses)
    return [
        candidate
        for candidate in parses
        if candidate.tag.POS in {"VERB", "INFN"}
        and math.isclose(candidate.score, top_score, rel_tol=1e-9, abs_tol=1e-12)
    ]


def paucal_accusative_case(value: int, case: str, *, animate: bool) -> str:
    """Case for a cardinal in the accusative before a noun it counts.

    A numeral ending in 2, 3 or 4 does not inflect for the accusative: "вижу
    двадцать два человека", not "двадцати двух человека". Only a bare 2, 3 or 4
    before an animate noun takes the genitive ("вижу двух человек") — as soon as
    the numeral is compound, the nominative form is the accusative one.
    """
    if case != "accs":
        return case
    if value % 10 not in (2, 3, 4) or value % 100 in (12, 13, 14):
        return case
    return "gent" if animate and value in (2, 3, 4) else "nomn"


def inanimate_cardinal_case(value: int, case: str) -> str:
    """Case for a cardinal in the accusative before an inanimate counted noun.

    Only a numeral whose final group ends in 1 keeps the accusative ("выставили
    на одну тысячу двести пятьдесят рублей"); every other ending is identical to
    the nominative, so asking pymorphy for the accusative only risks a wrong
    form. The thousands group is checked separately because "тысяча" is the word
    that actually inflects in "одну тысячу двести".
    """
    if case != "accs":
        return case
    final_group_needs_accusative = value % 10 == 1 and value % 100 != 11
    thousands = (value // 1000) % 1000
    thousands_need_accusative = thousands % 10 == 1 and thousands % 100 != 11
    return "accs" if final_group_needs_accusative or thousands_need_accusative else "nomn"


def noun_number_form(n: int) -> str:
    if n == 0:
        return "many"
    last_two = n % 100
    last_digit = n % 10
    if last_two in {11, 12, 13, 14}:
        return "many"
    if last_digit == 1:
        return "one"
    if last_digit in {2, 3, 4}:
        return "few"
    return "many"


def should_consume_abbreviation_dot(tokens: list[str], dot_index: int) -> bool:
    if dot_index >= len(tokens) or tokens[dot_index] != ".":
        return False
    if dot_index + 1 >= len(tokens):
        return False
    next_token = tokens[dot_index + 1]
    if "\n" in next_token:
        return False
    if next_token in {",", ";", ":", ")", "]", "}", "»", '"', "”"}:
        return True
    stripped_next = next_token.strip(PUNCT_STRIP)
    if not stripped_next:
        return False
    first_char = stripped_next[:1]
    return first_char.islower() or first_char.isdigit()


def should_keep_decimal_unit_dot_at(source_text: str, start: int) -> bool:
    next_index, saw_newline = first_non_whitespace_index(source_text, start)
    if next_index >= len(source_text):
        return True
    if saw_newline:
        return True
    next_char = source_text[next_index]
    if next_char in ".!?…":
        return True
    if next_char == ",":
        return False
    return not (next_char.islower() or next_char.isdigit())


def should_keep_decimal_unit_dot(rest: str) -> bool:
    return should_keep_decimal_unit_dot_at(rest, 0)


def should_keep_tokenized_decimal_unit_dot(tokens: list[str], start_index: int) -> bool:
    for index in range(start_index, len(tokens)):
        token = tokens[index]
        if not token:
            continue
        if "\n" in token:
            return True
        next_char = token[:1]
        if next_char in ".!?…":
            return True
        if next_char == ",":
            return False
        return not (next_char.islower() or next_char.isdigit())
    return True


def inflect_numeral_string(
    num_str: str,
    case: str,
    gender: str | None = None,
    animate: bool | None = None,
) -> str:
    """Render a numeral after canonicalizing pymorphy grammeme values.

    ``pymorphy3`` may return string-like typed grammemes whose equality operator
    raises when compared with a grammeme from another category (for example,
    ``masc == "plur"``).  Keeping those objects out of both the implementation and
    its cache key makes rendering independent of call order.
    """
    normalized_case = str(case)
    normalized_gender = str(gender) if gender is not None else None
    return _inflect_numeral_string_cached(
        num_str, normalized_case, normalized_gender, animate
    )


@functools.lru_cache(maxsize=16384)
def _inflect_numeral_string_cached(
    num_str: str,
    case: str,
    gender: str | None = None,
    animate: bool | None = None,
) -> str:
    try:
        value = int(num_str)
    except ValueError:
        return num_str
    case = resolve_primary_case(case)
    num2words_case = resolve_num2words_case(case, default="")
    if num2words_case:
        kwargs: dict[str, Any] = {"case": num2words_case}
        try:
            if gender == "plur":
                kwargs["plural"] = True
            elif gender in CARDINAL_GENDER_TO_NUM2WORDS:
                kwargs["gender"] = CARDINAL_GENDER_TO_NUM2WORDS[gender]
            if animate is not None:
                kwargs["animate"] = animate
            return num2words.num2words(value, lang="ru", **kwargs)
        except Exception as exc:
            warn_once(
                logger,
                f"num2words-gendered:{value}",
                "num2words failed for %r (kwargs=%s): %s",
                value,
                kwargs,
                exc,
            )
    try:
        words = num2words.num2words(value, lang="ru").split()
    except Exception as exc:
        warn_once(logger, f"num2words:{value}", "num2words failed for %r: %s", value, exc)
        return num_str
    if case == "nomn" and gender is None:
        return " ".join(words)
    def get_magnitude_gender(word_str: str) -> str | None:
        return MAGNITUDE_GENDERS.get(first_parse_required(word_str).normal_form)

    def magnitude_takes_plural(word_str: str) -> bool:
        """Whether the magnitude noun agrees in the plural with its multiplier.

        In an oblique case the whole phrase inflects, so the magnitude follows
        its own group: ``1000`` stays singular (``одной тысячи``) while ``2000``
        goes plural (``двух тысяч``). Without this the noun keeps the singular
        of the requested case and produces ``двух тысячи``.
        """
        scale = MAGNITUDE_SCALES.get(first_parse_required(word_str).normal_form)
        if scale is None:
            return False
        return noun_number_form((value // scale) % 1000) != "one"

    inflected_words: list[str] = []
    for index, word in enumerate(words):
        parsed = parse_word(word)
        p = parsed[0] if parsed else None
        if not p:
            inflected_words.append(word)
            continue
        current_gender = gender
        is_magnitude_self = get_magnitude_gender(word) is not None
        if not is_magnitude_self and index + 1 < len(words):
            mag_gender = get_magnitude_gender(words[index + 1])
            if mag_gender:
                current_gender = mag_gender
        if is_magnitude_self:
            current_gender = None
            if case == "nomn":
                inflected_words.append(word)
                continue
            if case == "accs" and word.lower() != "тысяча":
                inflected_words.append(word)
                continue
        tags = {case}
        if current_gender:
            tags.add(current_gender)
        if is_magnitude_self and magnitude_takes_plural(word):
            tags.add("plur")
        inflected = p.inflect(tags)
        if inflected:
            inflected_words.append(inflected.word)
        else:
            if current_gender:
                inflected_case = p.inflect({case})
                if inflected_case:
                    inflected_words.append(inflected_case.word)
                    continue
            inflected_words.append(word)
    return " ".join(inflected_words)


inflect_numeral_string.cache_clear = _inflect_numeral_string_cached.cache_clear  # type: ignore[attr-defined]
inflect_numeral_string.cache_info = _inflect_numeral_string_cached.cache_info  # type: ignore[attr-defined]


def get_target_tags_for_number(
    num: int, case: str, noun_gender: str | None = None
) -> set[str]:
    del noun_gender
    form = noun_number_form(num)
    if case == "nomn":
        return (
            {"nomn", "sing"}
            if form == "one"
            else {"gent", "sing"} if form == "few" else {"gent", "plur"}
        )
    if case == "accs":
        return (
            {"accs", "sing"}
            if form == "one"
            else {"gent", "sing"} if form == "few" else {"gent", "plur"}
        )
    if num >= 1000 and num % 1000 == 0:
        # Число оканчивается словом-разрядом, и оно само управляет родительным
        # множественного: «одной тысячей человек», а не «тысячей человеками».
        return {"gent", "plur"}
    return {case, "sing"} if form == "one" else {case, "plur"}


def _get_preposition_before_number(tokens: list[str], idx: int) -> tuple[str, str] | None:
    max_prep_len = min(3, idx)
    for prep_len in range(max_prep_len, 1, -1):
        start = idx - prep_len
        prep_tokens = [normalize_context_token(token) for token in tokens[start:idx]]
        if not all(prep_tokens) or any(
            token in NUMERAL_CONTEXT_BARRIERS for token in prep_tokens
        ):
            continue
        if any(
            first_parse_required(token).tag.POS in MORPHOLOGICAL_CONTEXT_BARRIER_POS
            for token in prep_tokens
        ):
            continue
        phrase = " ".join(prep_tokens)
        if phrase in PREP_CASE:
            return phrase, PREP_CASE[phrase]
    for i in range(idx - 1, max(-1, idx - 3), -1):
        word_left = normalize_context_token(tokens[i])
        if word_left == "чем" or word_left in NUMERAL_CONTEXT_BARRIERS:
            break
        parsed_left = first_parse_required(word_left)
        if parsed_left.tag.POS in MORPHOLOGICAL_CONTEXT_BARRIER_POS:
            break
        # Производный предлог разбирается как существительное, но барьером не
        # служит: «в течение ближайших 30 лет».
        if word_left in PREP_CASE:
            return word_left, PREP_CASE[word_left]
        # Имя или местоимение между предлогом и числом забирает управление
        # себе: «У меня 350 казаков», «в городе 12 школ» — число именительное.
        # Временное слово — обстоятельство, а партитивная вершина сама
        # управляет числом справа; сквозь них предлог виден: «до мая 1500
        # солдат не досчитавшись», «до исхода 14 [века]».
        if parsed_left.tag.POS == "NPRO" or (
            is_case_reliable_noun(parsed_left)
            and parsed_left.normal_form not in _TIME_CONTEXT_LEMMAS
            and parsed_left.normal_form not in _PARTITIVE_BOUNDARY_LEMMAS
        ):
            break
    return None


def _is_counting_group(tokens: Sequence[str], idx: int, visible_length: int) -> bool:
    """Whether the integer at ``idx`` and the word after it form a counting group.

    A quantitative group is a syntactic island: «в городе 12 лет», «на глубине
    200 м», «в Киеве 3177 человек». The written counted word tells the group
    apart from a genuinely oblique quantity, because a counting group puts it
    into the form the *nominative* numeral requires («лет», «человек», «м»),
    while an oblique quantity agrees with the numeral instead («в 12 городах»,
    «с 200 метрами»). Only a preposition or a verb can govern such a group; a
    neighbouring noun or adjective is modified by it, so it must not push its
    own case in — that produced «в городе двенадцати лет» and «на глубине
    двухстах метрах».
    """
    if idx + 1 >= visible_length:
        return False
    parsed_num = parse_integer_token(tokens[idx])
    if parsed_num is not None:
        # The form a nominative numeral demands of the counted word.
        required = canonicalize_grammemes(
            get_target_tags_for_number(int(parsed_num[1]), "nomn")
        )
    elif DECIMAL_TOKEN_PATTERN.search(tokens[idx]):
        # A decimal quantity always demands the genitive singular of its unit
        # («три целых две десятых гигагерца»), whatever the case of the numeral.
        required = canonicalize_grammemes(frozenset({"gent", "sing"}))
    else:
        return False
    counted_index = idx + 1
    if (
        tokens[counted_index] in {",", "."}
        and counted_index + 2 < visible_length
        and tokens[counted_index + 1].isdigit()
    ):
        # A decimal tail is part of the number, not the counted word: «на
        # частоте 3,2 ГГц» counts gigahertz exactly like «на частоте 50 Гц».
        counted_index += 2
    counted_raw = tokens[counted_index].strip(PUNCT_STRIP)
    counted = counted_raw.lower()
    if not counted:
        return False
    # The unit lookup keeps the source case: «В» is a volt while «в» is a
    # preposition, so lowercasing first would lose the unit and let the
    # preposition govern the measurement.
    if is_unit_token(counted_raw) or is_unit_token(counted):
        # A unit symbol is not inflected, so it cannot report government either;
        # its bare presence means the numeral counts something.
        return True
    return any(
        is_case_reliable_noun(parse)
        and required.issubset(canonicalize_grammemes(parse.tag.grammemes))
        for parse in parse_word(counted)
    )


#: «умножить на 5», «разделить на 5»: правый операнд не управляется контекстом.
_ARITHMETIC_OPERATOR_VERBS = frozenset({"умножить", "разделить"})
#: «5 × 11», «5 умножить на 11»: левый операнд тоже стоит сам за себя.
_MULTIPLICATION_MARKERS = frozenset({"×", "умножить"})
#: Слова-вершины, после которых «2560 на 1440» — размер, а не отношение.
_DIMENSION_HEADS = frozenset(
    {
        "размер",
        "размером",
        "разрешение",
        "габарит",
        "габаритами",
        "ширина",
        "высота",
    }
)
#: Буквы температурных шкал после знака градуса: Цельсий, Фаренгейт, Кельвин.
_TEMPERATURE_SCALE_SYMBOLS = frozenset({"с", "c", "f", "к", "k"})
#: Составные сравнения: их правая часть требует родительного.
_COMPARISON_PHRASES = frozenset({"больше или равно", "меньше или равно"})
#: Единицы, при которых «равно» задаёт дательный: «равен 45°», «равен 45 мин».
#: Сравнение идёт с поверхностной формой токена, поэтому словарные «градус»,
#: «минута», «секунда» тут были мертвы: справа от числа стоит «градусам», а не
#: «градус». Сокращения живут: они и есть своя поверхностная форма. Полную
#: форму разбирает правило существительного справа — «равен 45 градусам» решает
#: `oblique-noun-on-the-right`, и решает верно.
_ANGLE_AND_DEGREE_UNITS = frozenset({"°", "мин", "сек"})
#: Формы «быть равным», после которых измерение стоит в дательном.
_EQUALITY_PREDICATES = frozenset({"равен", "равна", "равно"})
#: «до нашей эры», «до Рождества Христова» — это эра, а не ориентир расстояния.
_ERA_MARKER_WORDS = frozenset({"нашей", "н", "нэ", "р", "рождества"})
#: Ориентир, от которого отмеряют расстояние: «в 200 м от дома».
_LANDMARK_MARKERS = frozenset({"от", "до"})
#: Спортивный счёт: «выиграли 3-1» — оба числа именительные. «Сыграть» ведёт
#: себя так же («сыграли 1:1»), и без него запись читалась «одного — одного»:
#: у числа 1 форма винительного одушевлённого совпадает с родительным.
_SCORE_VERBS = frozenset({"выиграть", "победить", "сыграть"})
#: Слово «счёт» перед числами тоже называет счёт, а не считает их: «со счётом
#: 3:2» — «три — два», и падеж предлога при «счётом» к числам не переходит.
_SCORE_NOUNS = frozenset({"счёт", "счет"})
#: Предлоги, требующие предложного падежа независимо от разбора вершины.
_LOCATIVE_PREPOSITIONS = frozenset({"в", "во", "о", "об", "при"})
#: Обозначения-ярлыки перед числом: «ISO 100», «f/2.8».
_LABEL_PREFIX_TOKENS = frozenset({"iso", "f"})
#: Вершины нумерации: «том 5», «номер 7» — число остаётся именительным.
_NUMBERING_HEAD_TOKENS = frozenset({"том", "номер"})
#: Итожащие частицы перед числом: «а всего 30 000» — не родительный от «весь».
_TOTALIZING_PARTICLES = frozenset({"всего", "итого"})


def _rule_operand_after_arithmetic_verb(ctx: NumeralContext) -> str | None:
    """Правый операнд арифметики независим: «умножить на пять», не «на пяти»."""
    if (
        ctx.idx > 1
        and ctx.word(-1) == "на"
        and ctx.word(-2) in _ARITHMETIC_OPERATOR_VERBS
    ):
        return "nomn"
    return None


def _rule_operand_before_multiplication(ctx: NumeralContext) -> str | None:
    """Левый операнд умножения тоже независим: «девять умножить на одиннадцать»."""
    if (
        ctx.idx + 2 < ctx.visible_length
        and ctx.word(1) in _MULTIPLICATION_MARKERS
        and ctx.word(2) == "на"
    ):
        return "nomn"
    return None


def _rule_ratio_left_operand(ctx: NumeralContext) -> str | None:
    """Левая часть отношения не наследует падеж контекста.

    «в масштабе 1 к пятидесяти» → «один к пятидесяти», а не «одном».
    """
    if (
        ctx.idx + 2 < ctx.visible_length
        and ctx.word(1) == "к"
        and is_integer_token(ctx.raw(2))
    ):
        return "nomn"
    return None


def _rule_dimension_first_coordinate(ctx: NumeralContext) -> str | None:
    """Первая координата размера — приложение-ярлык: «разрешение 2560 на 1440».

    Голое «число на число» без слова-вершины остаётся во власти обычных правил.
    """
    if not (
        ctx.idx + 2 < ctx.visible_length
        and ctx.word(1) == "на"
        and is_integer_token(ctx.raw(2))
    ):
        return None
    for back in range(-1, max(-5, -ctx.idx - 1), -1):
        if any(char in ctx.raw(back) for char in ".!?;:"):
            break
        if ctx.word(back) in _DIMENSION_HEADS:
            return "nomn"
    return None


def _rule_temperature_equality(ctx: NumeralContext) -> str | None:
    """«равно 177 °C» → дательный: «равно ста семидесяти семи градусам Цельсия».

    Обычные уравнения сохраняют именительные операнды.
    """
    if (
        ctx.idx > 0
        and ctx.word(-1) == "равно"
        and ctx.idx + 2 < ctx.visible_length
        and ctx.word(1) == "°"
        and ctx.word(2) in _TEMPERATURE_SCALE_SYMBOLS
    ):
        return "datv"
    return None


def _rule_comparison_or_equal(ctx: NumeralContext) -> str | None:
    """«больше или равно 5» → «больше или равно пяти»."""
    if ctx.idx >= 3:
        comparison = " ".join(ctx.word(offset) for offset in (-3, -2, -1))
        if comparison in _COMPARISON_PHRASES:
            return "gent"
    return None


def _rule_equality_before_degree_unit(ctx: NumeralContext) -> str | None:
    """«интервал равен 45 мин»: «равен» задаёт дательный через несколько слов.

    Работает по поверхностной форме, поэтому область правила — знак градуса и
    сокращения («°», «мин», «сек»). Развёрнутую единицу оно и не должно ловить:
    «равен 45 градусам» решает `oblique-noun-on-the-right` по разбору соседа.
    """
    if ctx.idx >= ctx.visible_length - 1:
        return None
    if ctx.word(1) not in _ANGLE_AND_DEGREE_UNITS:
        return None
    for back in range(-1, max(-7, -ctx.idx - 1), -1):
        if ctx.word(back) in _EQUALITY_PREDICATES:
            return "datv"
        if any(char in ctx.raw(back) for char in ".!?;:"):
            break
    return None


def _rule_power_exponent(ctx: NumeralContext) -> str | None:
    """«в степени 3» → «в степени три»: показатель степени не склоняется."""
    if ctx.idx > 1 and ctx.word(-1) == "степени" and ctx.word(-2) == "в":
        return "nomn"
    return None


def _numeric_group_offsets(ctx: NumeralContext) -> tuple[int, int]:
    """Смещения краёв числовой группы: одиночного числа или диапазона «10-20».

    Управление относится ко всей группе, а не к тому её члену, о котором сейчас
    спрашивают: у «в 10-20 км от города» и предлог, и единица с ориентиром
    стоят по краям диапазона, а не рядом с каждой границей.
    """
    if (
        ctx.idx + 2 < ctx.visible_length
        and ctx.raw(1) in DASH_TOKENS
        and is_integer_token(ctx.raw(2))
    ):
        return 0, 2
    if ctx.idx >= 2 and ctx.raw(-1) in DASH_TOKENS and is_integer_token(ctx.raw(-2)):
        return -2, 0
    return 0, 0


def _rule_distance_from_landmark(ctx: NumeralContext) -> str | None:
    """«в 200 м от дома» → «в двухстах метрах от дома».

    Символ единицы не имеет своего падежа, поэтому управление в фразе никто не
    сообщает и «в» иначе прочиталось бы винительным.

    Диапазон разбирается той же конструкцией: «в 10-20 км от города» — это одно
    расстояние до ориентира, и предложный получают обе границы. Раньше правило
    искало единицу вплотную за числом и до правой границы не доставало.
    """
    left, right = _numeric_group_offsets(ctx)
    if ctx.idx + left <= 0 or ctx.word(left - 1) != "в":
        return None
    unit_offset = right + 1
    if ctx.idx + unit_offset >= ctx.visible_length:
        return None
    unit_word = ctx.raw(unit_offset).lower().strip(PUNCT_STRIP)
    landmark_offset = unit_offset + 1
    is_unit = is_unit_token(unit_word)
    if not is_unit and ctx.raw(landmark_offset) == ".":
        # Точка сокращения — отдельный токен: «в 75 в. от Казани».
        is_unit = is_unit_token(f"{unit_word}.")
        landmark_offset += 1
    if not (
        is_unit
        and ctx.idx + landmark_offset < ctx.visible_length
        and ctx.word(landmark_offset) in _LANDMARK_MARKERS
    ):
        return None
    era_follows = (
        ctx.idx + landmark_offset + 1 < ctx.visible_length
        and ctx.word(landmark_offset + 1) in _ERA_MARKER_WORDS
    )
    if not era_follows:
        return "loct"
    return None


#: Падежи, которые вершина справа действительно навязывает сочинённому ряду.
#: Родительного здесь нет намеренно: он у существительного при числительном
#: обычный счётный («три участника»), и падежа числу не сообщает.
_SERIES_HEAD_CASES = frozenset({"datv", "ablt", "loct"})
#: Соединители сочинённого ряда чисел.
_SERIES_COORDINATORS = frozenset({"и", "или"})
#: Предел длины ряда при поиске вершины. Просмотр делается один раз на ряд, но
#: у документа-выброса и один проход должен быть ограничен.
_SERIES_SCAN_LIMIT = 512
#: Сколько токенов за последним членом смотреть на вершину: между рядом и
#: вершиной стоит согласованное определение («3 и 5 крупными заводами»).
_SERIES_HEAD_SCAN_WIDTH = 6
#: Знаки, обрывающие поиск вершины ряда. Закрывающая скобка здесь потому,
#: что за ней идёт уже другая синтагма — в корпусе это библиографическая
#: сноска, за которой начинается новое предложение.
_SERIES_HEAD_BARRIER_CHARS = ".!?;:)]}»"


def _is_series_continuation(ctx: NumeralContext) -> bool:
    """Число — не первый член ряда: слева уже стоит его сосед.

    Проверка постоянная по времени и нужна, чтобы просмотр вправо делался один
    раз на ряд: остальные члены получают падеж от первого через памятку.
    """
    if ctx.idx < 2:
        return False
    previous = ctx.raw(-1)
    if previous.endswith(",") and is_integer_token(previous.rstrip(",")):
        return True
    word = ctx.word(-1)
    if previous == "," or word in _SERIES_COORDINATORS:
        neighbour = ctx.raw(-2).rstrip(",")
        return is_integer_token(neighbour) or _rendered_numeral_case(neighbour) is not None
    return False


def _series_head_offset(ctx: NumeralContext) -> int | None:
    """Смещение слова сразу за последним членом ряда; `None` — ряда нет."""
    offset = 0
    members = 1
    while members < _SERIES_SCAN_LIMIT:
        member = ctx.raw(offset)
        if not member:
            return None
        if member.endswith(","):
            next_offset = offset + 1
        elif ctx.word(offset + 1) in _SERIES_COORDINATORS or ctx.raw(offset + 1) == ",":
            next_offset = offset + 2
        else:
            break
        if not is_integer_token(ctx.raw(next_offset).rstrip(",")):
            break
        offset = next_offset
        members += 1
    if members < 2:
        return None
    return offset + 1


def _rule_coordinated_series_head(ctx: NumeralContext) -> str | None:
    """Общая вершина справа задаёт падеж всему сочинённому ряду.

    «Премии присудили 3, 5 и 7 участникам» — дательный у всех членов, а не
    именительный: вершина у ряда одна, и падеж она сообщает всему ряду. Раньше
    её не видел никто: первый член решался без взгляда за ряд, а остальные
    наследовали его падеж.

    Просмотр вправо делается один раз на ряд — для первого его члена; остальные
    получают тот же падеж через `coordinated-first-number` и памятку решений,
    поэтому разрешение ряда остаётся линейным.
    """
    if _is_series_continuation(ctx):
        return None
    head_offset = _series_head_offset(ctx)
    if head_offset is None:
        return None
    limit = min(ctx.visible_length - ctx.idx, head_offset + _SERIES_HEAD_SCAN_WIDTH)
    for offset in range(head_offset, limit):
        raw = ctx.raw(offset)
        if any(char in raw for char in _SERIES_HEAD_BARRIER_CHARS):
            # Точка, двоеточие, точка с запятой и закрывающая скобка обрывают
            # группу: за ними вершина этого ряда не стоит. Проверка идёт по
            # исходному токену, потому что «)» после снятия пунктуации пуст и
            # иначе просмотр уходил бы в следующее предложение.
            break
        token = raw.strip(PUNCT_STRIP)
        if not token:
            continue
        best = first_parse_required(token)
        if best.tag.POS in {"VERB", "INFN", "PREP", "CONJ"} and ctx.word(offset) != "и":
            # Предлог вводит свою группу: существительное за ним принадлежит
            # ему, а не ряду («… 441). Вопреки Нестору …»). Союз «и» —
            # исключение: он соединяет последние члены самого ряда.
            # Основное чтение решает раньше именного омонима: у «после» есть
            # разбор «посол» в предложном, и без этого порядка предлог стал бы
            # вершиной ряда.
            break
        if token[:1].isupper():
            # Заглавная у вершины означает либо имя собственное, либо начало
            # нового предложения после потерянной точки: «Паскаль, 1623, 1662,
            # Паскалю был предложен вопрос». Ни то, ни другое падежа ряду не
            # сообщает — исчисляемая вершина строчная.
            break
        if best.tag.POS != "NOUN":
            # Вершиной ряда становится только слово, которое существительным и
            # читается: у наречия «уже» есть разбор «уж» в предложном, и по
            # нему годы жизни «Гретри, 1742, 1813,» получали предложный падеж.
            # Согласованное определение вершину не отменяет, поэтому просмотр
            # продолжается — его обрывают знаки и глагол выше.
            continue
        p_noun = select_parse(parse_word(token), pos="NOUN")
        if p_noun is not None and is_case_reliable_noun(p_noun):
            head_case = "loct" if "loc2" in p_noun.tag else p_noun.tag.case
            return head_case if head_case in _SERIES_HEAD_CASES else None
    return None


def _rendered_numeral_case(raw: str) -> str | None:
    """Падеж уже развёрнутого в слова числительного; не числительное — None.

    Обход слева направо переписывает числа словами, и следующий член
    сочинённого ряда видит слева не «25», а «двадцати пяти» — падеж читается
    прямо с формы.
    """
    word = normalize_context_token(raw)
    if not word or is_integer_token(word):
        return None
    parsed = first_parse_required(word)
    if parsed.tag.POS == "NUMR" and parsed.tag.case is not None:
        return parsed.tag.case
    return None


def _rule_measurement_continuation(ctx: NumeralContext) -> str | None:
    """Младшая часть измерения повторяет падеж старшей: «между 2 ч 30 мин».

    «42° 30 мин», «5 м 30 см», «2 ч 30 мин» — одно измерение из двух частей, и
    заданный слева косвенный падеж распространяется на обе. Признак — единица
    сразу после числа и измерение непосредственно слева: без правой единицы это
    уже отдельное количество («в 1905 году 3 солдата»), а знак препинания между
    частями разрывает измерение («ширина 5 м, длина 30 см»).
    """
    if ctx.idx < 2 or not is_unit_token(ctx.raw(1)):
        return None
    left_unit = ctx.raw(-1)
    if not left_unit or not (left_unit[-1].isalpha() or left_unit[-1] == "°"):
        return None
    if not is_unit_token(left_unit):
        # Старшая единица к этому моменту уже развёрнута в слово («часами»),
        # поэтому годится и существительное — но только само название единицы:
        # любое другое слово слева означает не измерение, а счётную группу
        # («из трёх оледенений 453 миллиона лет назад»).
        parsed = ctx.parse(-1)
        if parsed is None or parsed.normal_form not in ALL_UNITS:
            return None
    leading = ctx.raw(-2)
    case = _rendered_numeral_case(leading)
    if case is None and is_integer_token(leading):
        case = dependency_case(ctx, ctx.idx - 2)
    if case is None or case == "nomn":
        # Именительный — то же, что решение по умолчанию: правило молчит, чтобы
        # не заслонять правила ниже.
        return None
    return case


def _rule_coordinated_first_number(ctx: NumeralContext) -> str | None:
    """Следующее число сочинения берёт падеж первого: «с 5 и 7 книгами».

    Первый член ряда к этому моменту уже развёрнут в слова, поэтому кроме
    цифровых токенов распознаются и словесные числительные («из двадцати пяти
    пехотных, 9 кавалерийских…»). Перечисление через запятую наследует падеж
    только внутри своего ряда: надёжное существительное обрывает поиск, чтобы
    не пересечь границу клаузы («в 1905 году, 3 солдата…»).
    """
    if ctx.idx < 2:
        return None
    prev = ctx.raw(-1)
    if prev == "и":
        for back in range(-2, max(-6, -ctx.idx - 1), -1):
            raw = ctx.raw(back)
            if any(char in raw for char in ".!?;:"):
                break
            if is_integer_token(raw.rstrip(",")):
                return dependency_case(ctx, ctx.idx + back)
            rendered = _rendered_numeral_case(raw)
            if rendered is not None:
                return rendered
        return None
    if prev == "," and is_integer_token(ctx.raw(-2)):
        return dependency_case(ctx, ctx.idx - 2)
    if prev.endswith(",") and is_integer_token(prev.rstrip(",")):
        return dependency_case(ctx, ctx.idx - 1)
    if prev.endswith(","):
        for back in range(-1, max(-4, -ctx.idx - 1), -1):
            raw = ctx.raw(back).rstrip(",")
            if is_integer_token(raw):
                return dependency_case(ctx, ctx.idx + back)
            rendered = _rendered_numeral_case(raw)
            if rendered is not None:
                return rendered
            word = normalize_context_token(raw)
            if word and is_case_reliable_noun(first_parse_required(word)):
                break
    return None


def _rule_range_right_boundary(ctx: NumeralContext) -> str | None:
    """Правая граница диапазона повторяет падеж левой: «с 5-7 книгами»."""
    if ctx.idx > 1 and ctx.raw(-1) in DASH_TOKENS and is_integer_token(ctx.raw(-2)):
        return dependency_case(ctx, ctx.idx - 2)
    return None


def _rule_fresh_quantity_after_dash(ctx: NumeralContext) -> str | None:
    """Тире вместо опущенного сказуемого начинает новую величину.

    «первый канал — 2 Мбит/с»: падеж прилагательного перед тире (особенно
    неоднозначного «второй») наследовать нельзя.
    """
    if ctx.idx > 0 and ctx.raw(-1) in DASH_TOKENS:
        return "nomn"
    return None


def _rule_range_start_governed_by_left(ctx: NumeralContext) -> str | None:
    """Левая граница диапазона управляется словом перед ней: «в 3-5 квартирах»."""
    if not (ctx.is_range_start and ctx.idx > 0):
        return None
    prev_token = ctx.raw(-1).strip(".,!?;:")
    if not prev_token:
        return None
    p_prev = first_parse_required(prev_token)
    if p_prev.tag.POS == "VERB" and p_prev.normal_form in _SCORE_VERBS:
        return "nomn"
    if p_prev.tag.POS == "NOUN" and p_prev.normal_form in _SCORE_NOUNS:
        return "nomn"
    prev_case = "loct" if "loc2" in p_prev.tag else p_prev.tag.case
    if not prev_case:
        return None
    if is_case_reliable_noun(p_prev):
        # Ярлычная вершина метит номерами весь диапазон: «на страницах
        # 91—92» — обе границы именительные, как и одиночный номер. Но
        # счётная группа за правой границей — количество: «в комнатах
        # 5-7 окон» считает окна, а не нумерует их.
        if p_prev.normal_form in LABEL_NOUN_LEMMAS and not (
            ctx.idx + 2 < ctx.visible_length
            and _is_counting_group(ctx.tokens, ctx.idx + 2, ctx.visible_length)
        ):
            return "nomn"
        if p_prev.normal_form in GENITIVE_QUANTITY_GOVERNORS:
            return "gent"
        if (
            p_prev.tag.case == "gent"
            and p_prev.tag.number == "plur"
            and ctx.word(-2) not in PREP_CASE
        ):
            # Обратный приблизительный счёт: существительное в родительном
            # множественном перед числом — считаемое, а не управляющее
            # («лет 25—30», «вёрст 30—40», «цена билетов 100—200 рублей»), и
            # число при нём именительное. Одиночное число в той же
            # конструкции уже читается так; диапазон отличался только тем, что
            # это правило принимало падеж считаемого за управление. Предлог
            # слева объясняет родительный сам («до пяти рублей»), и тогда
            # признак не работает.
            return "nomn"
        if ctx.idx > 1:
            prev_prev = ctx.word(-2)
            if prev_prev in _LOCATIVE_PREPOSITIONS:
                return "loct"
            if prev_prev in PREP_CASE:
                # Падеж существительного объяснён его собственным предлогом
                # («до реки»), и если диапазон образует счётную группу
                # («130—140 верст»), он — самостоятельное количество.
                if ctx.idx + 2 < ctx.visible_length and _is_counting_group(
                    ctx.tokens, ctx.idx + 2, ctx.visible_length
                ):
                    return None
                return PREP_CASE[prev_prev]
        return prev_case
    if p_prev.tag.POS in {"ADJF", "PRTF"}:
        return prev_case
    return None


def _rule_label_prefix(ctx: NumeralContext) -> str | None:
    """Обозначение-ярлык перед числом не склоняет его: «ISO 100», «f/2.8»."""
    if ctx.idx > 0 and ctx.word(-1) in _LABEL_PREFIX_TOKENS:
        return "nomn"
    return None


def _rule_numbering_head(ctx: NumeralContext) -> str | None:
    """«том 5», «номер 7»: число называет объект, а не считает его.

    Выглядит дублем `label-noun-head` — оба слова есть и в `LABEL_NOUN_LEMMAS`,
    — но дубль только «номер». У «том» первый разбор pymorphy — это «тот»
    (ADJF, предложный, из «о том»), `is_case_reliable_noun` даёт False, и до
    морфологического правила очередь не доходит. Снятие проверено: «Смотрите
    том 5» читается «том пяти», и на корпусе расходится одна книга из семи.
    Правило держится на поверхностной форме именно поэтому.
    """
    if ctx.idx > 0 and ctx.word(-1) in _NUMBERING_HEAD_TOKENS:
        return "nomn"
    return None


def _rule_label_noun_head(ctx: NumeralContext) -> str | None:
    """Существительное-ярлык слева оставляет число именительным: «рейс 213»."""
    left_noun = ctx.parse(-1)
    if left_noun is None:
        return None
    if is_case_reliable_noun(left_noun) and left_noun.normal_form in LABEL_NOUN_LEMMAS:
        return "nomn"
    return None


def _rule_genitive_quantity_governor(ctx: NumeralContext) -> str | None:
    """Вершина количества требует родительного: «более 100 человек»."""
    left_noun = ctx.parse(-1)
    if left_noun is None:
        return None
    if (
        is_case_reliable_noun(left_noun)
        and left_noun.normal_form in GENITIVE_QUANTITY_GOVERNORS
        and left_noun.tag.case in {"nomn", "gent"}
    ):
        return "gent"
    return None


def _rule_locative_quantity_head(ctx: NumeralContext) -> str | None:
    """«в возрасте 25 лет» → «в возрасте двадцати пяти лет».

    Предлог помечает существительное, а не количество, поэтому предложный падеж
    вершины до числа не доходит.
    """
    if ctx.idx <= 1:
        return None
    left_noun = ctx.parse(-1)
    if left_noun is None:
        return None
    if (
        is_case_reliable_noun(left_noun)
        and left_noun.normal_form in LOCATIVE_GENITIVE_QUANTITY_HEADS
        and (left_noun.tag.case == "loct" or "loc2" in left_noun.tag)
        and ctx.word(-2) in {"в", "во"}
    ):
        return "gent"
    return None


def _rule_measure_parameter_head(ctx: NumeralContext) -> str | None:
    """Измерение после слова-параметра — приложение в именительном.

    «при температуре 660 градусов Цельсия», «со скоростью 60 километров в час».
    Требование счётной группы держит правило на настоящих измерениях: справа
    обязана стоять единица или считаемое слово в нужной форме.
    """
    left_noun = ctx.parse(-1)
    if left_noun is None:
        return None
    if (
        is_case_reliable_noun(left_noun)
        and left_noun.normal_form in MEASURE_PARAMETER_HEADS
        and _is_counting_group(ctx.tokens, ctx.idx, ctx.visible_length)
    ):
        return "nomn"
    return None


def _rule_oblique_noun_before_bare_number(ctx: NumeralContext) -> str | None:
    """Косвенное существительное рядом сильнее неоднозначного предлога вдали.

    «на частоте 3,2» и «при напряжении 1,15» — предложный, а те же предлоги
    перед числом без существительного остаются во власти контекста.

    Субстантивированное прилагательное исключено: «в среднем», «в целом», «в
    общем» — наречные обороты, они ничем не управляют, но каждый разбирается как
    прилагательное, в отличие от настоящей вершины измерения вроде «частоте».

    Целое число наследует падеж, только когда за ним не начинается новая
    именная группа: перед существительным целое — приложение-ярлык («на
    частоте 3 передатчик работает» — «частоте три»), а перед наречием или
    глаголом фраза числом и закончилась («в начале 9 уже видим…»). Дробь
    всегда сама величина («на частоте 3,2»).
    """
    if ctx.idx <= 1:
        return None
    if not DECIMAL_TOKEN_PATTERN.search(ctx.token):
        next_word = ctx.word(1)
        if next_word and first_parse_required(next_word).tag.POS in {
            "NOUN",
            "ADJF",
            "PRTF",
        }:
            return None
    left_noun = ctx.parse(-1)
    if left_noun is None:
        return None
    if (
        is_case_reliable_noun(left_noun)
        and not _is_counting_group(ctx.tokens, ctx.idx, ctx.visible_length)
        and not any("ADJF" in candidate.tag for candidate in parse_word(ctx.word(-1)))
        and (
            left_noun.tag.case in {"gent", "datv", "ablt", "loct"}
            or "loc2" in left_noun.tag
        )
        and ctx.idx + 1 < ctx.visible_length
        and ctx.word(1)
        and ctx.word(-2) in {"в", "во", "на", "о", "об", "при"}
    ):
        return "loct" if "loc2" in left_noun.tag else left_noun.tag.case
    return None


def _rule_preposition_before_number(ctx: NumeralContext) -> str | None:
    """Предлог перед числом: «с 5 по 10», «в 1995 году», «по 5 рублей».

    Ветка одна, потому что все её случаи решают один вопрос — какой падеж
    требует предлог, — и разные предлоги отвечают на него по-разному, глядя
    вправо.
    """
    prep_match = _get_preposition_before_number(ctx.tokens, ctx.idx)
    if prep_match is None:
        return None
    word_left, prep_case = prep_match
    if word_left in {"с", "со"}:
        for offset in range(1, min(ctx.visible_length - ctx.idx, 5)):
            if ctx.raw(offset).lower() in {"до", "по"}:
                return "gent"
            right_parse = first_parse_required(ctx.raw(offset))
            if is_case_reliable_noun(right_parse):
                if right_parse.tag.case == "ablt":
                    return "ablt"
                break
    if word_left in {"в", "на"}:
        # Инверсия приблизительного количества: «верстах в 40» — число в
        # предложном падеже вершины слева, фраза им и заканчивается.
        if ctx.word(-1) in {"в", "во"}:
            inverted_head = ctx.parse(-2)
            next_raw = ctx.raw(1)
            if (
                inverted_head is not None
                and is_case_reliable_noun(inverted_head)
                and (inverted_head.tag.case == "loct" or "loc2" in inverted_head.tag)
                and (not next_raw or not any(ch.isalnum() for ch in next_raw))
            ):
                return "loct"
        # Счётная группа сразу после числа — самостоятельное количество:
        # «в 2 часа», «в 5 групп» — винительный, не поиск вершины справа.
        if _is_counting_group(ctx.tokens, ctx.idx, ctx.visible_length):
            return "accs"
        for offset in range(1, min(ctx.visible_length - ctx.idx, 6)):
            raw = ctx.raw(offset)
            if any(char in raw for char in ".!?;:,"):
                break
            p = first_parse_required(raw)
            if is_case_reliable_noun(p):
                if p.tag.case == "loct" or "loc2" in p.tag:
                    return "loct"
                is_loc = p.inflect({"loct"})
                is_acc = p.inflect({"accs"})
                word_curr = raw.lower()
                if is_loc and is_loc.word == word_curr:
                    return "loct"
                if is_acc and is_acc.word == word_curr:
                    return "accs"
            if "VERB" in p.tag or "INFN" in p.tag:
                break
        for offset in range(1, min(ctx.visible_length - ctx.idx, 4)):
            p = first_parse_required(ctx.raw(offset))
            if p.normal_form in _TIME_CONTEXT_LEMMAS:
                if is_integer_token(ctx.token):
                    parsed_num = parse_integer_token(ctx.token)
                    if parsed_num is None:
                        return "loct"
                    _, unsigned = parsed_num
                    val = int(unsigned)
                    return "loct" if 1000 <= val <= 2100 else "accs"
                return "loct"
        return "accs"
    if word_left == "по":
        if is_integer_token(ctx.token):
            parsed_num = parse_integer_token(ctx.token)
            if parsed_num is None:
                return "datv"
            _, unsigned = parsed_num
            val = int(unsigned)
            if val % 10 == 1 and val % 100 != 11:
                return "datv"
            return "accs"
        return "datv"
    return prep_case


def _rule_passive_participle_predicate(ctx: NumeralContext) -> str | None:
    """Краткое страдательное причастие — сказуемое, а не источник управления.

    «перечислены 3 причины»: подлежащее в именительном.
    """
    for i in range(ctx.idx - 1, max(ctx.left_scan_start - 1, ctx.idx - 3), -1):
        p = first_parse_required(ctx.tokens[i])
        if p.tag.POS == "PRTS" and "pssv" in p.tag:
            return "nomn"
        if p.tag.POS in {"NOUN", "ADJF", "PRTF"}:
            break
    return None


def _rule_adjective_agreement(ctx: NumeralContext) -> str | None:
    """Прилагательное слева задаёт падеж, если справа нет счётной группы.

    «с двумя основными задачами». Существительное между прилагательным и числом
    отменяет правило: тогда прилагательное относится к нему, а не к числу.
    Запятая — граница однородного ряда: определение перед ней относится к
    предыдущему члену («до трёх тысяч убитыми, 8 знамен»). Итожащие частицы
    («всего», «итого») разбираются как родительный от «весь», но числом не
    управляют. Счётная группа справа отменяет только согласуемые падежи:
    прилагательное в однозначно косвенном падеже («начальствовал отборными
    1000 чел.») не может быть определением именительной группы и управляет.
    """
    counting_group = _is_counting_group(ctx.tokens, ctx.idx, ctx.visible_length)
    blocked_by_noun = False
    local_left_scan_start = ctx.left_scan_start
    for i in range(ctx.idx - 1, max(ctx.left_scan_start - 1, ctx.idx - 3), -1):
        if "," in ctx.tokens[i]:
            local_left_scan_start = i + 1
            break
        p = first_parse_required(ctx.tokens[i])
        if p.tag.POS in MORPHOLOGICAL_CONTEXT_BARRIER_POS:
            local_left_scan_start = i + 1
            break
        if p.tag.POS == "NOUN":
            blocked_by_noun = True
            break
    for i in range(max(local_left_scan_start, ctx.idx - 2), ctx.idx):
        token_word = ctx.tokens[i].lower()
        if token_word in _TOTALIZING_PARTICLES:
            continue
        p = first_parse_required(ctx.tokens[i])
        if blocked_by_noun and p.tag.POS in {"ADJF", "PRTF"}:
            continue
        if p.tag.POS in {"ADJF", "PRTF"} and p.tag.case:
            if counting_group and p.tag.case not in {"datv", "ablt", "loct"}:
                return None
            return p.tag.case
    return None


def _rule_verb_government(ctx: NumeralContext) -> str | None:
    """Глагол слева управляет числом: «заплатили одну тысячу».

    Полные причастия («ожидаемый», «требуемый») — определения к следующему
    существительному, а не источники управления; их разбирает правило
    прилагательных, и число остаётся в падеже сказуемого.
    """
    for i in range(ctx.idx - 1, max(ctx.left_scan_start - 1, ctx.idx - 5), -1):
        word_left = ctx.tokens[i].lower().strip(".,!?;:")
        parsed_left = parse_word(word_left)
        top_verbs = top_scoring_verb_parses(parsed_left)
        for candidate in top_verbs:
            if candidate.normal_form in VERB_CASE:
                return VERB_CASE[candidate.normal_form]
        # pymorphy помечает переходные глаголы грамемой ``tran``, поэтому обычному
        # прямому объекту список глаголов не нужен. Глаголы, требующие другого
        # падежа, перечислены в VERB_CASE выше и уже разобраны. Винительный меняет
        # чтение только у числа, последняя группа которого кончается на 1
        # («заплатили одну тысячу»); ``inanimate_cardinal_case`` оставляет
        # остальные окончания такими же, как в именительном. Непереходное чтение
        # среди равновероятных блокирует винительный: «пришли» — это и «прийти»,
        # и повелительное от «прислать», и управляет только второе.
        if top_verbs and all("tran" in candidate.tag for candidate in top_verbs):
            # Прямое дополнение не бывает в дательном, творительном или
            # предложном: «закончили дело 2700 пленными» — «пленными» показывает,
            # что число не объект глагола, и падеж задаёт правило справа.
            if ctx.idx < ctx.visible_length - 1:
                word_right = ctx.raw(1).lower().strip(".,!?;:")
                if word_right:
                    p_right = first_parse_required(word_right)
                    if is_case_reliable_noun(p_right) and (
                        p_right.tag.case in {"datv", "ablt", "loct"}
                        or "loc2" in p_right.tag
                    ):
                        return None
            return "accs"
        if any(char in ctx.tokens[i] for char in ".!?"):
            break
    return None


def _rule_entity_keyword_default(ctx: NumeralContext) -> str | None:
    """Ключевое слово справа задаёт падеж по типу сущности: «дом 5», «рейс 213».

    Правило и следующее разбирают одного и того же соседа справа и проверяют
    одно и то же условие косвенности. Второй разбор берётся из `lru_cache`
    в `parse_word` за ~190 нс, поэтому слияние ради скорости смысла не имеет.

    Если справа стоит существительное в косвенном падеже, оно сильнее: там
    управление, а не ярлык.
    """
    if ctx.idx >= ctx.visible_length - 1:
        return None
    word_right = ctx.raw(1).lower().strip(".,!?;:")
    if not word_right:
        return None
    p_right = first_parse_required(word_right)
    noun_case = p_right.tag.case
    if is_case_reliable_noun(p_right) and (
        noun_case in {"gent", "datv", "ablt", "loct"} or "loc2" in p_right.tag
    ):
        return None
    for entity_type, keywords in ENTITY_KEYWORDS.items():
        if p_right.normal_form in keywords or word_right in keywords:
            return ENTITY_DEFAULT_CASE[entity_type]
    return None


def _rule_oblique_noun_on_the_right(ctx: NumeralContext) -> str | None:
    """Существительное справа в косвенном падеже управляет числом.

    «5 книгами» → «пятью книгами».
    """
    if ctx.idx >= ctx.visible_length - 1:
        return None
    word_right = ctx.raw(1).lower().strip(".,!?;:")
    if not word_right:
        return None
    p_right = first_parse_required(word_right)
    if not is_case_reliable_noun(p_right):
        return None
    noun_case = p_right.tag.case
    if noun_case in {"datv", "ablt", "loct"} or "loc2" in p_right.tag:
        return "loct" if noun_case == "loct" or "loc2" in p_right.tag else noun_case
    return None


#: Порядок — контракт: верхнее правило заслоняет нижние, и это единственная
#: документация приоритетов. Список получен механическим переносом ветвей
#: `get_numeral_case` сверху вниз, порядок сохранён буква в букву.
CASE_RULES: tuple[CaseRule, ...] = (
    CaseRule("operand-after-arithmetic-verb", _rule_operand_after_arithmetic_verb),
    CaseRule("operand-before-multiplication", _rule_operand_before_multiplication),
    CaseRule("ratio-left-operand", _rule_ratio_left_operand),
    CaseRule("dimension-first-coordinate", _rule_dimension_first_coordinate),
    CaseRule("temperature-equality", _rule_temperature_equality),
    CaseRule("comparison-or-equal", _rule_comparison_or_equal),
    CaseRule("equality-before-degree-unit", _rule_equality_before_degree_unit),
    CaseRule("power-exponent", _rule_power_exponent),
    CaseRule("distance-from-landmark", _rule_distance_from_landmark),
    CaseRule("measurement-continuation", _rule_measurement_continuation),
    CaseRule("coordinated-first-number", _rule_coordinated_first_number),
    CaseRule("range-right-boundary", _rule_range_right_boundary),
    CaseRule("fresh-quantity-after-dash", _rule_fresh_quantity_after_dash),
    CaseRule("range-start-governed-by-left", _rule_range_start_governed_by_left),
    CaseRule("label-prefix", _rule_label_prefix),
    CaseRule("numbering-head", _rule_numbering_head),
    CaseRule("label-noun-head", _rule_label_noun_head),
    CaseRule("genitive-quantity-governor", _rule_genitive_quantity_governor),
    CaseRule("locative-quantity-head", _rule_locative_quantity_head),
    CaseRule("measure-parameter-head", _rule_measure_parameter_head),
    CaseRule("oblique-noun-before-bare-number", _rule_oblique_noun_before_bare_number),
    CaseRule("coordinated-series-head", _rule_coordinated_series_head),
    CaseRule("preposition-before-number", _rule_preposition_before_number),
    CaseRule("passive-participle-predicate", _rule_passive_participle_predicate),
    CaseRule("adjective-agreement", _rule_adjective_agreement),
    CaseRule("verb-government", _rule_verb_government),
    CaseRule("entity-keyword-default", _rule_entity_keyword_default),
    CaseRule("oblique-noun-on-the-right", _rule_oblique_noun_on_the_right),
)


#: Тот же список, развёрнутый в функции: по нему идёт горячий цикл.
_CASE_DECIDERS = deciders(CASE_RULES)


def _case_for(ctx: NumeralContext) -> str:
    """Падеж числа в готовом контексте.

    Ничего не сработало — голое число стоит предикатом и остаётся именительным.
    Дательный слева («Мне уже 40.») его за собой не тянет.
    """
    return resolve_case(_CASE_DECIDERS, ctx) or "nomn"


def _case_for_ex(ctx: NumeralContext) -> tuple[str, bool]:
    """То же плюс признак «падеж назвало правило, а не решение по умолчанию».

    Именительный по умолчанию — не свидетельство, а признание, что контекст
    молчит. Потребителю бывает важно отличить его от именительного, который
    правило действительно вывело.
    """
    decision = resolve_case(_CASE_DECIDERS, ctx)
    return (decision or "nomn"), decision is not None


def get_numeral_case(
    tokens: list[str],
    idx: int,
    *,
    _context: _NumeralTokenContext | None = None,
    _visible_length: int | None = None,
) -> str:
    if _context is None:
        _context = _build_numeral_token_context(tokens)
    visible_length = len(tokens) if _visible_length is None else min(_visible_length, len(tokens))
    return _case_for(
        NumeralContext(
            tokens, idx, visible_length, _context.left_scan_starts, decisions=_context.decisions
        )
    )


def get_numeral_case_ex(
    tokens: list[str],
    idx: int,
    *,
    _context: _NumeralTokenContext | None = None,
    _visible_length: int | None = None,
) -> tuple[str, bool]:
    """`get_numeral_case` плюс признак явного сигнала в контексте."""
    if _context is None:
        _context = _build_numeral_token_context(tokens)
    visible_length = len(tokens) if _visible_length is None else min(_visible_length, len(tokens))
    return _case_for_ex(
        NumeralContext(
            tokens, idx, visible_length, _context.left_scan_starts, decisions=_context.decisions
        )
    )
