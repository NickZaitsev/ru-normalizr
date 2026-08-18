from __future__ import annotations

import functools
import logging
import math
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
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
        "сумма",
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
        if (
            first_parse_required(word_left).tag.POS
            in MORPHOLOGICAL_CONTEXT_BARRIER_POS
        ):
            break
        if word_left in PREP_CASE:
            return word_left, PREP_CASE[word_left]
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
    is_range_start = (
        idx < visible_length - 1 and tokens[idx + 1] in {"-", "–", "—"}
    )
    left_scan_start = _context.left_scan_starts[idx]

    if (
        idx > 1
        and normalize_context_token(tokens[idx - 1]) == "на"
        and normalize_context_token(tokens[idx - 2]) in {"умножить", "разделить"}
    ):
        return "nomn"
    if (
        idx + 2 < visible_length
        and normalize_context_token(tokens[idx + 1]) in {"×", "умножить"}
        and normalize_context_token(tokens[idx + 2]) == "на"
    ):
        return "nomn"
    if (
        idx + 2 < visible_length
        and normalize_context_token(tokens[idx + 1]) == "к"
        and is_integer_token(tokens[idx + 2])
    ):
        # The left operand of a ratio is independent of a preceding context:
        # "в масштабе 1 к пятидесяти" keeps "один", not the locative form
        # inherited from "в масштабе".
        return "nomn"
    if (
        idx + 2 < visible_length
        and normalize_context_token(tokens[idx + 1]) == "на"
        and is_integer_token(tokens[idx + 2])
    ):
        # In a resolution/dimension construction the first coordinate is a
        # label-like nominative: "разрешение 2560 на 1440 пикселей".  A bare
        # "число на число" remains governed by the ordinary context rules.
        for back in range(idx - 1, max(-1, idx - 5), -1):
            if any(char in tokens[back] for char in ".!?;:"):
                break
            if normalize_context_token(tokens[back]) in {
                "размер",
                "размером",
                "разрешение",
                "габарит",
                "габаритами",
                "ширина",
                "высота",
            }:
                return "nomn"
    if (
        idx > 0
        and normalize_context_token(tokens[idx - 1]) == "равно"
        and idx + 2 < visible_length
        and normalize_context_token(tokens[idx + 1]) == "°"
        and normalize_context_token(tokens[idx + 2]) in {"с", "c", "f", "к", "k"}
    ):
        # Temperature equality uses the dative: "равно ста семидесяти семи
        # градусам Цельсия". Plain equations keep their established
        # nominative operands.
        return "datv"
    if idx >= 3:
        comparison = " ".join(
            normalize_context_token(token) for token in tokens[idx - 3 : idx]
        )
        if comparison in {"больше или равно", "меньше или равно"}:
            return "gent"
    if idx < visible_length - 1:
        next_unit = normalize_context_token(tokens[idx + 1])
        if next_unit in {"°", "градус", "мин", "минута", "сек", "секунда"}:
            for back in range(idx - 1, max(-1, idx - 7), -1):
                previous = normalize_context_token(tokens[back])
                if previous in {"равен", "равна", "равно"}:
                    return "datv"
                if any(char in tokens[back] for char in ".!?;:"):
                    break
    if (
        idx > 1
        and normalize_context_token(tokens[idx - 1]) == "степени"
        and normalize_context_token(tokens[idx - 2]) == "в"
    ):
        return "nomn"

    if (
        idx > 0
        and normalize_context_token(tokens[idx - 1]) == "в"
        and idx + 2 < visible_length
        and is_unit_token(tokens[idx + 1].lower().strip(PUNCT_STRIP))
        and normalize_context_token(tokens[idx + 2]) in {"от", "до"}
    ):
        # A distance measured off a landmark is locative: «в 200 м от дома» →
        # «в двухстах метрах от дома». A unit symbol carries no case of its own,
        # so nothing else in the phrase reports the government and «в» would
        # otherwise fall back to its accusative reading.
        return "loct"

    if idx > 1 and tokens[idx - 1] == "и":
        for back in range(idx - 2, max(-1, idx - 6), -1):
            if any(char in tokens[back] for char in ".!?;:"):
                break
            if is_integer_token(tokens[back]):
                return get_numeral_case(
                    tokens, back, _context=_context, _visible_length=visible_length
                )
    if idx > 1 and tokens[idx - 1] in {"-", "–", "—"} and is_integer_token(tokens[idx - 2]):
        return get_numeral_case(
            tokens, idx - 2, _context=_context, _visible_length=visible_length
        )
    if idx > 0 and tokens[idx - 1] in {"-", "–", "—"}:
        # An em dash after an elided subject/predicate starts a fresh quantity:
        # "первый канал — 2 Мбит/с". Do not inherit an accidental pymorphy
        # case from the adjective before the dash (notably ambiguous "второй").
        return "nomn"

    if is_range_start and idx > 0:
        prev_token = tokens[idx - 1].strip(".,!?;:")
        if prev_token:
            p_prev = first_parse_required(prev_token)
            if p_prev.tag.POS == "VERB" and p_prev.normal_form in {
                "выиграть",
                "победить",
            }:
                return "nomn"
            prev_case = "loct" if "loc2" in p_prev.tag else p_prev.tag.case
            if prev_case:
                if is_case_reliable_noun(p_prev):
                    if idx > 1:
                        prev_prev = normalize_context_token(tokens[idx - 2])
                        if prev_prev in {"в", "во", "о", "об", "при"}:
                            return "loct"
                        if prev_prev in PREP_CASE:
                            return PREP_CASE[prev_prev]
                    return prev_case
                if p_prev.tag.POS in {"ADJF", "PRTF"}:
                    return prev_case

    if idx > 0:
        immediate_left = normalize_context_token(tokens[idx - 1])
        if immediate_left:
            if immediate_left in {"iso", "f"}:
                return "nomn"
            if immediate_left in {"том", "номер"}:
                return "nomn"
            left_noun = first_parse_required(immediate_left)
            if (
                is_case_reliable_noun(left_noun)
                and left_noun.normal_form in LABEL_NOUN_LEMMAS
            ):
                return "nomn"
            if (
                is_case_reliable_noun(left_noun)
                and left_noun.normal_form in GENITIVE_QUANTITY_GOVERNORS
                and left_noun.tag.case in {"nomn", "gent"}
            ):
                return "gent"
            # A relational quantity noun inside the «в …» frame takes a genitive
            # complement: «в возрасте двадцати пяти лет». The preposition marks
            # the noun, not the quantity, so its own locative never reaches the
            # number.
            if (
                is_case_reliable_noun(left_noun)
                and left_noun.normal_form in LOCATIVE_GENITIVE_QUANTITY_HEADS
                and (left_noun.tag.case == "loct" or "loc2" in left_noun.tag)
                and idx > 1
                and normalize_context_token(tokens[idx - 2]) in {"в", "во"}
            ):
                return "gent"
            # A parameter noun is named by the measurement that follows it, so
            # the measurement is an apposition in the nominative: «при
            # температуре шестьсот шестьдесят градусов Цельсия», «со скоростью
            # шестьдесят километров в час». Requiring a counting group keeps
            # this to real measurements: a unit or a counted word in the form
            # the nominative numeral demands has to follow.
            if (
                is_case_reliable_noun(left_noun)
                and left_noun.normal_form in MEASURE_PARAMETER_HEADS
                and _is_counting_group(tokens, idx, visible_length)
            ):
                return "nomn"
            # An oblique noun immediately before a decimal or a bare number is
            # a stronger local signal than an ambiguous preposition farther to
            # the left: "на частоте 3,2" and "при напряжении 1,15" are
            # locative, while the same prepositions before a numeral without a
            # noun remain context-dependent.
            #
            # A substantivized adjective is excluded: "в среднем", "в целом" and
            # "в общем" are adverbial phrases that govern nothing, and every one
            # of them still parses as an adjective, unlike a real measurement
            # noun such as "частоте".
            if (
                is_case_reliable_noun(left_noun)
                and not _is_counting_group(tokens, idx, visible_length)
                and not any(
                    "ADJF" in candidate.tag for candidate in parse_word(immediate_left)
                )
                and (
                    left_noun.tag.case in {"gent", "datv", "ablt", "loct"}
                    or "loc2" in left_noun.tag
                )
                and idx + 1 < visible_length
                and normalize_context_token(tokens[idx + 1])
                and idx > 1
                and normalize_context_token(tokens[idx - 2])
                in {"в", "во", "на", "о", "об", "при"}
            ):
                return "loct" if "loc2" in left_noun.tag else left_noun.tag.case

    # In a coordinated quantity the second noun governs both numerals:
    # "управление 3 и 5 заводами".  Do not use a genitive noun here: it is the
    # ordinary counted-noun construction ("три и пять книг"), not government.
    if idx + 2 < visible_length and normalize_context_token(tokens[idx + 1]) == "и":
        for j in range(idx + 2, min(visible_length, idx + 6)):
            token = tokens[j].strip(".,!?;:()[]{}")
            if not token:
                continue
            if any(char in tokens[j] for char in ".!?;:"):
                break
            parsed = parse_word(token)
            p_noun = select_parse(parsed, pos="NOUN")
            if p_noun is not None and is_case_reliable_noun(p_noun):
                noun_case = "loct" if "loc2" in p_noun.tag else p_noun.tag.case
                if noun_case in {"datv", "ablt", "loct"}:
                    return noun_case
                break
            p = first_parse_required(token)
            if p.tag.POS in {"VERB", "INFN"}:
                break

    prep_match = _get_preposition_before_number(tokens, idx)
    if prep_match is not None:
        word_left, prep_case = prep_match
        if word_left in {"с", "со"}:
            for k in range(idx + 1, min(visible_length, idx + 5)):
                if tokens[k].lower() in {"до", "по"}:
                    return "gent"
                right_parse = first_parse_required(tokens[k])
                if is_case_reliable_noun(right_parse):
                    if right_parse.tag.case == "ablt":
                        return "ablt"
                    break
        if word_left in {"в", "на"}:
            for j in range(idx + 1, min(visible_length, idx + 6)):
                if any(char in tokens[j] for char in ".!?;:,"):
                    break
                p = first_parse_required(tokens[j])
                if is_case_reliable_noun(p):
                    if p.tag.case == "loct" or "loc2" in p.tag:
                        return "loct"
                    is_loc = p.inflect({"loct"})
                    is_acc = p.inflect({"accs"})
                    word_curr = tokens[j].lower()
                    if is_loc and is_loc.word == word_curr:
                        return "loct"
                    if is_acc and is_acc.word == word_curr:
                        return "accs"
                if "VERB" in p.tag or "INFN" in p.tag:
                    break
            for j in range(idx + 1, min(visible_length, idx + 4)):
                p = first_parse_required(tokens[j])
                word_norm = p.normal_form
                if word_norm in _TIME_CONTEXT_LEMMAS:
                    if is_integer_token(tokens[idx]):
                        parsed_num = parse_integer_token(tokens[idx])
                        if parsed_num is None:
                            return "loct"
                        _, unsigned = parsed_num
                        val = int(unsigned)
                        return "loct" if 1000 <= val <= 2100 else "accs"
                    return "loct"
            return "accs"
        if word_left == "по":
            if is_integer_token(tokens[idx]):
                parsed_num = parse_integer_token(tokens[idx])
                if parsed_num is None:
                    return "datv"
                _, unsigned = parsed_num
                val = int(unsigned)
                if val % 10 == 1 and val % 100 != 11:
                    return "datv"
                return "accs"
            return "datv"
        return prep_case

    blocked_by_noun = False
    local_left_scan_start = left_scan_start
    for i in range(idx - 1, max(left_scan_start - 1, idx - 3), -1):
        p = first_parse_required(tokens[i])
        if p.tag.POS in MORPHOLOGICAL_CONTEXT_BARRIER_POS:
            local_left_scan_start = i + 1
            break
        if p.tag.POS == "NOUN":
            blocked_by_noun = True
            break

    # A short passive participle is a predicate, not a government source for a
    # following numeral: "перечислены 3 причины" has a nominative subject.
    for i in range(idx - 1, max(left_scan_start - 1, idx - 3), -1):
        p = first_parse_required(tokens[i])
        if p.tag.POS == "PRTS" and "pssv" in p.tag:
            return "nomn"
        if p.tag.POS in {"NOUN", "ADJF", "PRTF"}:
            break

    if not _is_counting_group(tokens, idx, visible_length):
        for i in range(max(local_left_scan_start, idx - 2), idx):
            p = first_parse_required(tokens[i])
            if blocked_by_noun and p.tag.POS in {"ADJF", "PRTF"}:
                continue
            if p.tag.POS in {"ADJF", "PRTF"} and p.tag.case:
                return p.tag.case

    for i in range(idx - 1, max(left_scan_start - 1, idx - 5), -1):
        word_left = tokens[i].lower().strip(".,!?;:")
        parsed_left = parse_word(word_left)
        # Full participles ("ожидаемый", "требуемый") are attributive modifiers of
        # a following noun, not governors of the numeral's case; leave them to the
        # adjective scan so the numeral stays in its predicate (nominative) case.
        top_verbs = top_scoring_verb_parses(parsed_left)
        for candidate in top_verbs:
            if candidate.normal_form in VERB_CASE:
                return VERB_CASE[candidate.normal_form]
        # pymorphy marks transitive verbs with ``tran``, so an ordinary direct
        # object needs no verb allow-list. Verbs that govern another case are
        # listed in VERB_CASE above and are already resolved. The accusative
        # only changes the rendered numeral when its last group ends in 1
        # ("заплатили одну тысячу"); ``inanimate_cardinal_case`` keeps every
        # other ending identical to the nominative. An intransitive reading among
        # the equally likely ones blocks the accusative: "пришли" is both
        # "прийти" and the imperative of "прислать", and only the latter governs.
        if top_verbs and all("tran" in candidate.tag for candidate in top_verbs):
            return "accs"
        if any(char in tokens[i] for char in ".!?"):
            break

    if idx < visible_length - 1:
        word_right = tokens[idx + 1].lower().strip(".,!?;:")
        if word_right:
            p_right = first_parse_required(word_right)
            noun_case = p_right.tag.case
            if not (
                is_case_reliable_noun(p_right)
                and (noun_case in {"gent", "datv", "ablt", "loct"} or "loc2" in p_right.tag)
            ):
                for entity_type, keywords in ENTITY_KEYWORDS.items():
                    if p_right.normal_form in keywords or word_right in keywords:
                        return ENTITY_DEFAULT_CASE[entity_type]

    if idx < visible_length - 1:
        word_right = tokens[idx + 1].lower().strip(".,!?;:")
        if word_right:
            p_right = first_parse_required(word_right)
            if is_case_reliable_noun(p_right):
                noun_case = p_right.tag.case
                if noun_case in {"datv", "ablt", "loct"} or "loc2" in p_right.tag:
                    return "loct" if noun_case == "loct" or "loc2" in p_right.tag else noun_case

    # Nothing else governs the numeral: a bare number is a predicate and stays
    # nominative. A dative on the left ("Мне уже 40.") does not pull it along.
    return "nomn"


