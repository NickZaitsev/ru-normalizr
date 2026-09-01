from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import num2words

from .._log_once import warn_once
from .._morph import first_parse_required, parse_word, select_parse, word_is_known
from ..abbreviation_context import should_keep_terminal_abbreviation_dot
from ..ordinal_utils import render_ordinal, render_ordinal_from_noun_parse
from ..preprocess_utils import NEGATIVE_NUMBER_PLACEHOLDER
from ..text_context import (
    PUNCT_STRIP,
    normalize_context_token,
    simple_tokenize,
    tokenize_with_spans,
)
from ..text_scan import compile_scan, first_non_whitespace_index
from ._constants import (
    CURRENCY_SYMBOLS,
    DAY_PART_LEMMAS,
    DIGIT_PATTERN,
    MAX_CLOCK_HOUR,
    NUMBER_LABEL_LEMMAS,
    NUMERIC_UNIT_RANGE_PATTERN,
    POST_NUMERAL_ABBREVIATION_PATTERN,
    POST_NUMERAL_ABBREVIATION_REPLACEMENTS,
    PREP_CASE,
    TIME_WORDS,
    UNITS_DATA,
    UnitDescriptor,
    resolve_unit_form,
    resolve_unit_info,
)
from ._helpers import (
    _build_numeral_token_context,
    _NumeralTokenContext,
    build_number_token,
    get_numeral_case,
    get_target_tags_for_number,
    inanimate_cardinal_case,
    inflect_numeral_string,
    inflect_unit_lemma,
    is_case_reliable_noun,
    is_coordinate_marker,
    noun_number_form,
    parse_integer_token,
    paucal_accusative_case,
    safe_inflect,
    should_consume_abbreviation_dot,
    should_keep_tokenized_decimal_unit_dot,
)
from .unit_expressions import match_unit_tokens
from .unit_rendering import render_unit_expression

logger = logging.getLogger(__name__)

_MULTIPLIER_LEMMAS = frozenset({"тысяча", "миллион", "миллиард", "триллион"})
_CURRENCY_SYMBOL_UNITS = CURRENCY_SYMBOLS
_NUMERIC_NOUN_RANGE_PATTERN = compile_scan(
    r"(?<![\w.,])(?P<left>\d+)-(?P<right>\d+)"
    r"(?P<space>\s+)(?P<noun>[^\W\d_]+)",
    re.UNICODE,
)


def _resolve_range_unit_info(unit_raw: str):
    unit_lower = unit_raw.lower().strip(".")
    direct = resolve_unit_info(unit_raw)
    if direct is not None:
        return direct

    parts = [part for part in unit_lower.split() if part]
    if len(parts) < 2:
        return None

    noun_parse = next(
        (
            candidate
            for candidate in parse_word(parts[-1])
            if "NOUN" in candidate.tag
        ),
        None,
    )
    if noun_parse is None:
        return None

    if len(parts) == 2:
        head_parse = next(
            (
                candidate
                for candidate in parse_word(parts[0])
                if candidate.tag.POS in {"ADJF", "PRTF"}
            ),
            None,
        )
        if head_parse is None:
            return None
        lemma = f"{head_parse.normal_form} {noun_parse.normal_form}"
    else:
        first_parse = next(
            (
                candidate
                for candidate in parse_word(parts[0])
                if candidate.tag.POS in {"ADJF", "PRTF"}
            ),
            None,
        )
        second_parse = next(
            (
                candidate
                for candidate in parse_word(parts[1])
                if candidate.tag.POS in {"ADJF", "PRTF"}
            ),
            None,
        )
        if first_parse is None or second_parse is None:
            return None
        lemma = (
            f"{first_parse.normal_form} {second_parse.normal_form}"
            f" {noun_parse.normal_form}"
        )

    for info in UNITS_DATA.values():
        if info.lemma == lemma:
            return info
    return None


def _surface_in_paradigm(token: str, descriptor) -> bool:
    """Check whether the token is one of the unit's fixed paradigm forms.

    A non-empty paradigm alone is not enough: «человек» carries a single
    counted-form override, and accepting every inflected form of the lemma
    through it would hijack the ordinary counted noun «человека».
    """
    surface = token.lower().strip(".")
    return any(
        form == surface for _, _, form in descriptor.morphology.paradigm
    )


def _animate_counted_noun(tokens: list[str], index: int) -> bool:
    """Check whether the token at ``index`` counts people («чел.», «человек»)."""
    if index >= len(tokens):
        return False
    token = tokens[index]
    info = resolve_unit_info(token)
    if info is not None:
        return info.lemma == "человек"
    clean = token.lower().strip(PUNCT_STRIP)
    if not clean:
        return False
    parsed = select_parse(clean, pos="NOUN")
    return parsed is not None and "anim" in parsed.tag


_ROUBLE_UNIT_LEMMAS = frozenset({"рубль", "гривна"})


def _money_amount_precedes(tokens: list[str], index: int) -> bool:
    """Check whether tokens before ``index`` end with «<число> р[уб].»."""
    j = index - 1
    while j >= 0 and tokens[j] == ".":
        j -= 1
    if j <= 0:
        return False
    word = tokens[j].strip(PUNCT_STRIP)
    info = resolve_unit_info(word) or resolve_unit_info(f"{word}.")
    if info is None or info.lemma not in _ROUBLE_UNIT_LEMMAS:
        return False
    j -= 1
    while j >= 0 and tokens[j] == ".":
        j -= 1
    return j >= 0 and tokens[j].strip(PUNCT_STRIP).isdigit()


def _last_nonempty_index(chunks: list[str]) -> int:
    """Индекс последнего непустого куска вывода, ``-1`` если такого нет."""
    for index in range(len(chunks) - 1, -1, -1):
        if chunks[index]:
            return index
    return -1


def _space_before_trailing_dash(out: list[str], dash_index: int) -> None:
    """Отбить пробелом тире, которым заканчивается уже собранный кусок вывода.

    Тире может лежать как внутри куска («слово—»), так и отдельным куском: в
    первом случае пробел вставляется внутрь строки, во втором — новым элементом
    перед ней. Пробел ставится только если слева от тире слово или число, иначе
    отбивать нечего.
    """
    chunk = out[dash_index]
    if len(chunk) > 1:
        if chunk[-2].isalnum():
            out[dash_index] = f"{chunk[:-1]} {chunk[-1]}"
        return
    previous_index = _last_nonempty_index(out[:dash_index])
    if previous_index >= 0 and out[previous_index][-1].isalnum():
        out.insert(dash_index, " ")


def _splice_segments(
    text: str,
    spans: list[tuple[int, int]],
    segments: list[tuple[int, int, str | None]],
) -> str:
    """Rebuild the text from token segments, keeping untouched spans verbatim.

    Only the tokens a rule actually rewrote are replaced; the characters
    between tokens — hyphens, brackets, quotes, line breaks — never pass
    through a tokenizer round-trip, so «ген.-майор», «м(оей)» or «!..» in an
    untouched part of the sentence survive unchanged. A space is inserted at a
    splice boundary only when the replacement would otherwise glue to an
    adjacent word character.
    """
    def needs_space(left: str, right: str) -> bool:
        # A dash reads as a standalone word and a bare asterisk is a footnote
        # marker; neither may glue onto a rewritten numeral.
        return (left.isalnum() or left in "—*") and (
            right.isalnum() or right in "—*"
        )

    out: list[str] = []
    cursor = 0
    for index, (first, last, replacement) in enumerate(segments):
        if (
            replacement is None
            and text[spans[first][0] : spans[last - 1][1]] in {"-", "–", "—"}
            and index > 0
            and segments[index - 1][2] is not None
            and index + 1 < len(segments)
            and segments[index + 1][2] is not None
        ):
            # A range dash between two rewritten numbers: «2-3 ошибки» becomes
            # «две — три ошибки», never the glued «две-три».
            replacement = "—"
        start = spans[first][0]
        end = spans[last - 1][1]
        gap = text[cursor:start]
        out.append(gap)
        if replacement is None:
            out.append(text[start:end])
        else:
            if replacement and not gap and out:
                previous_index = _last_nonempty_index(out)
                previous_chunk = out[previous_index] if previous_index >= 0 else ""
                if previous_chunk and needs_space(previous_chunk[-1], replacement[0]):
                    if previous_chunk[-1] == "—":
                        # Тире отбивается с двух сторон или ни с одной: пробел
                        # справа появляется только потому, что справа переписано
                        # число, поэтому и слева его надо поставить — иначе
                        # получается «слово— два миллиона», чего в исходнике не
                        # было. Тире, у которого справа ничего не переписывали,
                        # в эту ветку не попадает и остаётся как в источнике.
                        _space_before_trailing_dash(out, previous_index)
                    out.append(" ")
            out.append(replacement)
            if (
                replacement
                and end < len(text)
                and needs_space(replacement[-1], text[end])
            ):
                out.append(" ")
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


#: Отрезок исходного текста: первый токен, следующий за последним, замена.
#: `None` оставляет символы отрезка как есть, поэтому текст между токенами
#: никогда не собирается заново.
Segment = tuple[int, int, str | None]

#: Что вернул обработчик: отрезки и сколько токенов он забрал.
Outcome = tuple[list[Segment], int]


def _is_word_token(token: str) -> bool:
    return bool(re.fullmatch(r"[^\W\d_]+", token, re.UNICODE))


def _is_ambiguous_preposition_token(token: str) -> bool:
    clean = token.lower().strip(PUNCT_STRIP)
    return bool(clean) and " " not in clean and clean in PREP_CASE


def _could_be_prepositional_object(token: str) -> bool:
    """Check whether a token can be governed by the homographic preposition.

    «220 в сети» keeps the preposition reading because a noun follows, but
    an adverb, a verb or a conjunction cannot be its object — «220 В
    постоянно» is the volt symbol followed by an adverb.
    """
    clean = token.lower().strip(PUNCT_STRIP)
    if not clean:
        return False
    if clean[0].isdigit():
        return True
    return select_parse(clean, pos={"NOUN", "ADJF", "PRTF", "NPRO", "NUMR"}) is not None


def _should_skip_unit_candidate(
    tokens: list[str], start_index: int, token_span: int, unit_raw: str
) -> bool:
    chunk = tokens[start_index : start_index + token_span]
    if unit_raw[:1].isupper() and unit_raw.lower() != unit_raw:
        follow = start_index + token_span
        if follow < len(tokens) and tokens[follow].strip() == ".":
            follow += 1
        if follow < len(tokens) and tokens[follow].strip() == ":":
            # Заглавное сокращение перед двоеточием — отсылка («13 См.:
            # с. 22»), а не повреждённый регистр символа единицы.
            return True
    if (
        token_span == 1
        and unit_raw == unit_raw.strip(PUNCT_STRIP)
        and _is_ambiguous_preposition_token(unit_raw)
        and start_index + token_span < len(tokens)
    ):
        next_token = tokens[start_index + token_span].strip(PUNCT_STRIP)
        if next_token and _could_be_prepositional_object(next_token):
            return True
    return (
        token_span > 1
        and all(_is_word_token(token) for token in chunk)
        and any(_is_ambiguous_preposition_token(token) for token in chunk[1:])
    )


def _extract_unit_candidate(
    tokens: list[str], start_index: int
) -> tuple[str, str, int] | None:
    match = match_unit_tokens(tokens, start_index)
    if match is None or _should_skip_unit_candidate(
        tokens, start_index, match.consumed_tokens, match.source
    ):
        return None
    return match.alias.casefold().strip("."), match.source, match.consumed_tokens


def _counted_noun_across_range(
    tokens: list[str], index: int
) -> tuple[str | None, bool] | None:
    """Gender and animacy of the noun counted by a range's left endpoint.

    In "2 — 3 книги" the left numeral has no noun next to it, yet it agrees
    with the noun that follows the right endpoint ("две — три книги"). The
    lookahead is bounded to the dash, the right endpoint and an optional
    modifier, so it stays constant-time.
    """
    if index + 3 >= len(tokens):
        return None
    if tokens[index + 1].strip(PUNCT_STRIP) not in {"—", "–", "-"}:
        return None
    if not tokens[index + 2].strip(PUNCT_STRIP).isdigit():
        return None
    for offset in (3, 4):
        if index + offset >= len(tokens):
            break
        candidate = tokens[index + offset].lower().strip(PUNCT_STRIP)
        if not candidate or _is_ambiguous_preposition_token(candidate):
            break
        # A modifier is checked first: a substantivized adjective such as
        # "рабочих" also parses as an animate noun, and taking it for the
        # counted noun would read "2 — 3 рабочих дня" as counting people.
        modifier = select_parse(candidate, pos={"ADJF", "PRTF"})
        if modifier is not None:
            # Определение обязано согласоваться со счётной формой правой
            # границы: «2 — 3 своих сочинения», но «91—92 своего сочинения» —
            # «своего» единственного числа принадлежит другой синтагме.
            right_value = int(tokens[index + 2].strip(PUNCT_STRIP))
            expected_number = (
                "sing" if noun_number_form(right_value) == "one" else "plur"
            )
            if modifier.tag.number is not None and expected_number not in modifier.tag:
                return None
            continue
        p_noun = select_parse(candidate, pos="NOUN")
        if p_noun is not None:
            return p_noun.tag.gender, "anim" in p_noun.tag
        break
    return None


def _is_redundant_unit_token(
    tokens: list[str], token_index: int, expected_lemma: str
) -> bool:
    if token_index >= len(tokens):
        return False
    token_lower = tokens[token_index].lower().strip(PUNCT_STRIP)
    if not token_lower:
        return False
    parsed = parse_word(token_lower)
    if not parsed:
        return False
    candidate = parsed[0]
    if "NOUN" not in candidate.tag or candidate.normal_form != expected_lemma:
        return False
    # Дублирующее слово стоит в счётной форме и со строчной буквы; заглавная
    # открывает новое предложение: «принято 32 000 человек. Люди поступили…»
    # — «Люди» не дубль единицы, а подлежащее следующей клаузы.
    if tokens[token_index].lstrip(PUNCT_STRIP)[:1].isupper():
        return False
    return candidate.tag.case == "gent"


@dataclass(frozen=True, slots=True)
class _NumberSite:
    """Число в тексте и всё, что известно о нём до выбора обработчика.

    Обработчики читают отсюда, а не из замыканий: падеж и черновое чтение числа
    считаются один раз, а каждый обработчик, нашедший своё существительное,
    пересчитывает чтение под его род и одушевлённость.
    """

    tokens: list[str]
    idx: int
    token: str
    clean_token: str
    value: int
    is_negative: bool
    case: str
    num_words: str
    token_context: _NumeralTokenContext

    @property
    def length(self) -> int:
        return len(self.tokens)

    def rendered(self, case: str, gender: str | None, animate: bool) -> str:
        """Чтение числа в заданной форме вместе с его знаком и обёрткой."""
        return build_number_token(
            self.token,
            self.clean_token,
            inflect_numeral_string(self.clean_token, case, gender, animate),
            self.is_negative,
        )


@dataclass(frozen=True, slots=True)
class _UnitAtSite:
    """Единица измерения справа от числа — то, что от неё осталось после разбора.

    `unit_info` равен `None`, если единицы там нет: тогда сосед справа проверяется
    как считаемое существительное. Остальные поля нужны обоим случаям, поэтому
    разбор делается один раз: `alias` мог быть переписан слиянием знака градуса
    или псевдонимом из реестра, и считаемое существительное видит уже его.
    """

    alias: str
    noun_token: str
    token_span: int
    unit_raw: str
    unit_info: UnitDescriptor | None


def _resolve_unit_at(site: _NumberSite) -> _UnitAtSite:
    """Разобрать соседа справа как единицу измерения."""
    tokens = site.tokens
    i = site.idx
    noun_token = tokens[i + 1]
    alias = noun_token.lower().strip(PUNCT_STRIP)
    unit_candidate = _extract_unit_candidate(tokens, i + 1)
    unit_token_span = 1
    unit_raw = noun_token
    if alias == "°" and i + 2 < len(tokens):
        # A temperature scale letter joins the degree sign only when the
        # pair is a registered symbol: «°C», «°К». Anything else after a
        # degree sign is a separate word — a preposition («30° с
        # уклоном»), a hemisphere marker («42° с. ш.») or a wrong-case
        # spelling — and merging it left a bare «°» in the output.
        degree_suffix = tokens[i + 2].strip(PUNCT_STRIP)
        merged = f"°{degree_suffix}"
        if (
            degree_suffix
            and resolve_unit_info(merged) is not None
            and not is_coordinate_marker(tokens, i + 2)
        ):
            alias = merged.lower()
            noun_token = f"{noun_token}{tokens[i + 2]}"
            unit_raw = noun_token
            unit_token_span = 2
    elif unit_candidate:
        alias, unit_raw, unit_token_span = unit_candidate

    if _should_skip_unit_candidate(tokens, i + 1, unit_token_span, unit_raw):
        unit_info = None
    else:
        unit_info = resolve_unit_info(unit_raw)
        if unit_info is None and unit_token_span == 1:
            resolved_form = resolve_unit_form(unit_raw)
            if resolved_form is not None and (
                _surface_in_paradigm(unit_raw, resolved_form)
                or resolved_form.morphology.indeclinable
            ):
                unit_info = resolved_form
        if (
            unit_info is not None
            and unit_info.lemma == "тонна"
            and unit_raw.strip(PUNCT_STRIP).rstrip(".").lower() == "т"
            and _animate_counted_noun(tokens, i + 1 + unit_token_span)
        ):
            # Тонны измеряют массу неодушевлённого груза; «100 т. чел.»
            # — это «сто тысяч человек», а не тонны людей.
            unit_info = resolve_unit_info("тыс.")
        if (
            unit_info is not None
            and unit_info.lemma == "век"
            and isinstance(site.value, int)
            and site.value > 21
        ):
            # Веков больше двадцати одного не бывает: «в 75 в. от
            # Казани» — это вёрсты, дореволюционная мера расстояния.
            unit_info = resolve_unit_info("верста")
        if (
            unit_info is None
            and unit_token_span == 1
            and unit_raw.strip(PUNCT_STRIP) == "к"
            and i + 2 < len(tokens)
            and tokens[i + 2] == "."
            and _money_amount_precedes(tokens, i)
        ):
            # «1 р. 92 к.» — денежная цепочка: «к.» после суммы в
            # рублях означает копейки. Без рублей слева «к» остаётся
            # предлогом («шёл к 92 дому»).
            unit_info = resolve_unit_info("коп.")
    return _UnitAtSite(alias, noun_token, unit_token_span, unit_raw, unit_info)


def _unit_case_at_site(site: _NumberSite, unit: _UnitAtSite, info: UnitDescriptor) -> str:
    """Падеж числа перед единицей: год после «в» и несклоняемая единица особые."""
    case = site.case
    if (
        1000 <= site.value <= 2100
        and site.idx > 0
        and normalize_context_token(site.tokens[site.idx - 1]) == "в"
    ):
        case = "accs"
    if info.morphology.indeclinable and unit.alias.strip(".") == info.lemma:
        # Несклоняемая единица падеж не сообщает, поэтому контекст читается без
        # неё: всё, что правее числа, для этого решения не существует.
        case = get_numeral_case(
            site.tokens,
            site.idx,
            _context=site.token_context,
            _visible_length=site.idx + 1,
        )
    return case


def _counted_one_form_agrees(site: _NumberSite, noun_word: str) -> bool:
    """Согласуется ли существительное с числом на 1 (кроме 11).

    Такое число требует единственного числа в падеже самого числа:
    «двадцать один дом», «с девяноста одним сочинением». «на страницах 91
    своего сочинения» — «сочинения» стоит в родительном при именительном
    числе, значит оно не считается, а принадлежит другой синтагме.
    Слово вне словаря форм не доказывает — считаем согласованным.
    """
    if not word_is_known(noun_word):
        return True
    expected = {site.case, "nomn" if site.case == "accs" else site.case}
    if site.case == "nomn":
        expected.add("accs")
    for parse in parse_word(noun_word):
        if "NOUN" not in parse.tag or "sing" not in parse.tag:
            continue
        if parse.tag.case in expected:
            return True
    return False


def _handle_adjective_and_noun(site: _NumberSite) -> Outcome | None:
    """Число + прилагательное + существительное: «2 основные задачи».

    Согласование ведёт существительное через прилагательное, поэтому число
    пересчитывается под его род и одушевлённость.
    """
    i = site.idx
    if i + 2 >= site.length:
        return None
    adj_token = site.tokens[i + 1]
    noun_token = site.tokens[i + 2]
    clean_adj = adj_token.lower().strip(PUNCT_STRIP)
    clean_noun = noun_token.lower().strip(PUNCT_STRIP)
    p_adj = select_parse(clean_adj, pos={"ADJF", "PRTF"})
    # Слово вне словаря («2 прочныя ступени», дореформенная орфография)
    # между числом и существительным читается как его определение:
    # согласование всё равно ведёт существительное.
    if p_adj is None and (
        not clean_adj.isalpha() or "," in adj_token or word_is_known(clean_adj)
    ):
        return None
    p_noun = (
        None
        if _is_ambiguous_preposition_token(clean_noun)
        else select_parse(clean_noun, pos="NOUN")
    )
    if p_noun is None or resolve_unit_info(adj_token) is not None:
        return None
    if noun_number_form(site.value) == "one" and not _counted_one_form_agrees(
        site, clean_noun
    ):
        return None
    is_anim = "anim" in p_noun.tag
    num_words = site.rendered(
        paucal_accusative_case(site.value, site.case, animate=is_anim),
        p_noun.tag.gender,
        is_anim,
    )
    return [(i, i + 1, num_words), (i + 1, i + 3, None)], 3


def _handle_money_multiplier(
    site: _NumberSite, unit: _UnitAtSite, info: UnitDescriptor, case: str
) -> Outcome | None:
    """Денежная сумма с множителем: «5 млн ₽» → «пять миллионов рублей»."""
    i = site.idx
    if info.category != "money":
        return None
    if unit.alias not in _CURRENCY_SYMBOL_UNITS or i + 2 >= site.length:
        return None
    multiplier_token = site.tokens[i + 2]
    multiplier_lower = multiplier_token.lower().strip(PUNCT_STRIP)
    p_multiplier = first_parse_required(multiplier_lower)
    if "NOUN" not in p_multiplier.tag or p_multiplier.normal_form not in _MULTIPLIER_LEMMAS:
        return None
    num_words = site.rendered(
        inanimate_cardinal_case(site.value, case),
        p_multiplier.tag.gender or "masc",
        False,
    )
    consumed = 4 if _is_redundant_unit_token(site.tokens, i + 3, info.lemma) else 3
    replacement = (
        f"{num_words} {multiplier_token} {inflect_unit_lemma(info, {'gent', 'plur'})}"
    )
    return [(i, i + consumed, replacement)], consumed


def _render_counted_unit(site: _NumberSite, info: UnitDescriptor, case: str) -> str:
    """Единица в форме, которую требует число: «два метра», «пять метров»."""
    if info.lemma == "человек" and case in {"nomn", "accs"}:
        unit_form = noun_number_form(site.value)
        # Bare 2–4 before an animate noun use the genitive numeral,
        # but the counted noun itself stays in the accusative
        # singular: "вижу двух человек".
        inflected_unit = (
            "человек"
            if case == "accs" and unit_form == "few"
            else ("человека" if unit_form == "few" else "человек")
        )
        return inflected_unit + (f" {info.suffix}" if info.suffix else "")
    return render_unit_expression(
        info,
        get_target_tags_for_number(site.value, case, info.gender),
        paucal=noun_number_form(site.value) == "few",
    )


def _handle_unit(
    site: _NumberSite, unit: _UnitAtSite, info: UnitDescriptor, case: str
) -> Outcome:
    """Число с единицей измерения: «5 кг», «30 °C», «2 тыс. км»."""
    tokens = site.tokens
    i = site.idx
    num_words = site.rendered(
        inanimate_cardinal_case(site.value, case), info.gender, False
    )
    full_unit = _render_counted_unit(site, info, case)
    match_unit = (
        re.search(re.escape(unit.alias), unit.noun_token, re.IGNORECASE)
        if unit.token_span == 1
        else None
    )
    if match_unit:
        full_unit = (
            unit.noun_token[: match_unit.start()]
            + full_unit
            + unit.noun_token[match_unit.end() :]
        )
    preserve_unit_dot = unit.unit_raw.endswith(".") and not should_consume_abbreviation_dot(
        tokens, i + unit.token_span
    )
    if preserve_unit_dot and should_keep_tokenized_decimal_unit_dot(
        tokens, i + 1 + unit.token_span
    ):
        full_unit += "."

    step = 1 + unit.token_span
    if unit.token_span == 1 and unit.alias.startswith("°") and len(unit.alias) == 2:
        step = 3
    if i + step < len(tokens) and should_consume_abbreviation_dot(tokens, i + step):
        step += 1
    if _is_redundant_unit_token(tokens, i + step, info.lemma):
        step += 1
    if info.lemma in _MULTIPLIER_LEMMAS and i + step < len(tokens):
        nn_match = match_unit_tokens(tokens, i + step)
        if nn_match is not None:
            nn_inflected = render_unit_expression(nn_match.descriptor, {"gent", "plur"})
            nn_consumed = nn_match.consumed_tokens
            # Не съедать точку сокращения, закрывающую предложение.
            last_index = i + step + nn_consumed - 1
            if tokens[last_index] == "." and not should_consume_abbreviation_dot(
                tokens, last_index
            ):
                nn_consumed -= 1
            consumed = step + nn_consumed
            return (
                [(i, i + consumed, f"{num_words} {full_unit} {nn_inflected}")],
                consumed,
            )
    return [(i, i + step, f"{num_words} {full_unit}")], step


def _dependent_genitive_follows(tokens: list[str], index: int) -> bool:
    """Справа от слова стоит зависимый родительный: «до 5 дня болезни».

    Такая группа делает существительное вершиной именной группы, а не частью
    суток при часе, и число в ней читается порядковым.
    """
    if index >= len(tokens):
        return False
    candidate = tokens[index].lower().strip(PUNCT_STRIP)
    if not candidate or not candidate.isalpha():
        return False
    parse = first_parse_required(candidate)
    return "NOUN" in parse.tag and parse.tag.case == "gent"


def _ordinal_for_mismatched_noun(
    site: _NumberSite, alias: str, p_noun
) -> Outcome | None:
    """Существительное не в счётной форме — число читается порядковым.

    «12 числа», «на 27 неделю», «в 9 часу»: количественное чтение требовало бы
    родительного множественного («двенадцать чисел»), а автор согласовал
    единственное число существительного с числом как с порядковым. Ярлычные
    конструкции («глава 5 книги», «№ 12 журнала») отсекает сосед слева.
    """
    i = site.idx
    if site.is_negative or noun_number_form(site.value) == "one":
        return None
    tag = p_noun.tag
    if "sing" not in tag or tag.case is None or "Fixd" in tag:
        return None
    # Форму сообщает только доминирующее существительное: «рядом» — наречие,
    # его принудительный разбор «ряд» в творительном формы не доказывает.
    if not is_case_reliable_noun(first_parse_required(alias)):
        return None
    if tag.case == "nomn":
        # Именительное — подлежащее следующей клаузы: «В 1990 команда…».
        return None
    if tag.case in {"gent", "accs"} and noun_number_form(site.value) == "few":
        # Счётная форма паукальных совпадает с родительным единственного:
        # «три числа», «вижу двух человек» — количественное чтение верно.
        return None
    if (
        tag.case == "gent"
        and p_noun.normal_form in DAY_PART_LEMMAS
        and 0 < site.value <= MAX_CLOCK_HOUR
        and not _dependent_genitive_follows(site.tokens, i + 2)
    ):
        # «в 10 утра», «около 11 вечера» — час, а не число месяца: часть суток
        # управляет родительным сама, а «десятого утра» — не время суток.
        # Только родительный: «на 3 день пути» — винительный, там порядковое.
        return None
    if tag.case == "gent" and site.value > 31:
        # Родительный единственного после большого числа — счётный эллипсис
        # неисчисляемого («15 000 пехоты»); порядковым в родительном читается
        # только число месяца.
        return None
    if any(
        "NOUN" in c.tag and c.tag.case == "gent" and "plur" in c.tag
        for c in parse_word(alias)
    ):
        # Омоформ счётной формы: «10 рот» — «рот» разбирается и как
        # винительный «рта», и как родительный множественного «роты», а
        # родительный множественного и есть счётная форма — чтение
        # количественное.
        return None
    if i > 0:
        left_raw = site.tokens[i - 1]
        if left_raw == "." and i > 1:
            prev = site.tokens[i - 2]
            if prev.isalpha() and len(prev) <= 3:
                # «в д. 5», «на стр. 5» — сокращение-ярлык перед номером.
                return None
            # Точка конца предложения контекста слева не даёт.
            left_raw = ""
        if "№" in left_raw:
            return None
        left = left_raw.lower().strip(PUNCT_STRIP)
        if left and is_case_reliable_noun(first_parse_required(left)):
            return None
    ordinal = render_ordinal_from_noun_parse(site.value, p_noun)
    prefix = site.token[: len(site.token) - len(site.token.lstrip(PUNCT_STRIP))]
    suffix = site.token[len(site.token.rstrip(PUNCT_STRIP)) :]
    return [(i, i + 1, f"{prefix}{ordinal}{suffix}"), (i + 1, i + 2, None)], 2


def _paucal_group_is_genitive(site: _NumberSite, alias: str) -> bool:
    """Существительное во множественном там, где счётная форма единственная.

    Число на 2—4 требует родительного ЕДИНСТВЕННОГО: «девяносто четыре
    женщины». Множественное («локоны волос 94 женщин») счётной формой быть не
    может — вся группа стоит в родительном при существительном слева, и
    числительное склоняется вместе с ней.
    """
    if noun_number_form(site.value) != "few" or site.case == "gent":
        return False
    if not word_is_known(alias):
        return False
    parses = parse_word(alias)
    if any("NOUN" in p.tag and p.tag.case == "gent" and "sing" in p.tag for p in parses):
        return False
    if not any(
        "NOUN" in p.tag and p.tag.case == "gent" and "plur" in p.tag for p in parses
    ):
        return False
    # Вершина слева и делает группу несогласованным определением: без неё
    # («прошло 22 суток») родительный числительного взяться неоткуда.
    if site.idx == 0:
        return False
    left = site.tokens[site.idx - 1].lower().strip(PUNCT_STRIP)
    if not left or not left.isalpha():
        return False
    p_left = first_parse_required(left)
    # «Бронепоезд номер 73 войск НКВД»: слева не вершина счётной группы, а
    # слово-ярлык, и число при нём — имя, а не количество.
    if p_left.normal_form in NUMBER_LABEL_LEMMAS:
        return False
    return is_case_reliable_noun(p_left)


def _handle_counted_noun(site: _NumberSite, unit: _UnitAtSite) -> Outcome | None:
    """Число + считаемое существительное: «5 книг», «вижу двух человек»."""
    i = site.idx
    p_noun = (
        None
        if _is_ambiguous_preposition_token(unit.alias)
        else select_parse(unit.alias, pos="NOUN")
    )
    if p_noun is None:
        return None
    mismatch = _ordinal_for_mismatched_noun(site, unit.alias, p_noun)
    if mismatch is not None:
        return mismatch
    if noun_number_form(site.value) == "one" and not _counted_one_form_agrees(
        site, unit.alias
    ):
        return None
    noun_token = unit.noun_token
    is_anim = "anim" in p_noun.tag
    # Счётный оборот читает числительное неодушевлённым: «по два бургомистра»
    # (распределительное «по» не знает одушевлённого винительного) и
    # «четыре человека детей боярских» (классификатор с родительным
    # приложением). Без этих признаков одушевлённый винительный обычный:
    # «вижу двух человек».
    if (
        is_anim
        and site.case == "accs"
        and noun_number_form(site.value) == "few"
        and p_noun.tag.case == "gent"
        and p_noun.tag.number == "sing"
    ):
        prev_word = site.tokens[i - 1].lower().strip(PUNCT_STRIP) if i > 0 else ""
        apposition = None
        if i + 2 < site.length:
            appos_word = site.tokens[i + 2].lower().strip(PUNCT_STRIP)
            if appos_word:
                apposition = first_parse_required(appos_word)
        if prev_word in {"по"} or (
            apposition is not None
            and apposition.tag.case == "gent"
            and apposition.tag.number == "plur"
        ):
            is_anim = False
    counted_case = "gent" if _paucal_group_is_genitive(site, unit.alias) else site.case
    num_words = site.rendered(
        paucal_accusative_case(site.value, counted_case, animate=is_anim),
        TIME_WORDS.get(unit.alias, p_noun.tag.gender),
        is_anim,
    )
    counted_noun = noun_token
    if site.case == "accs" and is_anim and site.value in {2, 3, 4}:
        if p_noun.normal_form == "человек":
            inflected_noun = "человек"
        else:
            inflected_noun = safe_inflect(
                p_noun, {"gent", "plur"}, fallback_word=unit.alias
            )
        counted_noun = re.sub(
            re.escape(unit.alias),
            inflected_noun,
            noun_token,
            count=1,
            flags=re.IGNORECASE,
        )
    return (
        [
            (i, i + 1, num_words),
            (i + 1, i + 2, None if counted_noun == noun_token else counted_noun),
        ],
        2,
    )


def _handle_token_on_the_right(site: _NumberSite) -> Outcome | None:
    """Сосед справа: единица измерения или считаемое существительное.

    Обработчик один, потому что разбор соседа общий: слияние знака градуса и
    псевдоним из реестра единиц переписывают токен, и считаемое существительное
    проверяется уже по переписанному — иначе «13 См.:» и «100 т. чел.» читаются
    иначе, чем читались.
    """
    if site.idx + 1 >= site.length:
        return None
    unit = _resolve_unit_at(site)
    info = unit.unit_info
    if info is None:
        return _handle_counted_noun(site, unit)
    case = _unit_case_at_site(site, unit, info)
    return _handle_money_multiplier(site, unit, info, case) or _handle_unit(
        site, unit, info, case
    )


def _handle_coordinated_ordinal(site: _NumberSite) -> Outcome | None:
    """Число, сочинённое с порядковым, читается порядковым: «главе восьмой и 9».

    Однородные члены — слова одного разряда, поэтому падеж, род и число
    задаёт порядковое слева от союза.
    """
    i = site.idx
    if i < 2 or site.is_negative or site.tokens[i - 1].lower() != "и":
        return None
    left = site.tokens[i - 2].lower().strip(PUNCT_STRIP)
    if not left:
        return None
    anum_parses = [
        candidate
        for candidate in parse_word(left)
        if "Anum" in candidate.tag and candidate.tag.case is not None
    ]
    if not anum_parses or "Anum" not in first_parse_required(left).tag:
        return None
    p_left = anum_parses[0]
    if i >= 3:
        # Форма порядкового многозначна («восьмой» — женские косвенные или
        # мужской именительный); её уточняет определяемое существительное:
        # «главе восьмой и 9» ↔ «том восьмой и 9».
        head = site.tokens[i - 3].lower().strip(PUNCT_STRIP)
        p_head = select_parse(head, pos="NOUN") if head else None
        if p_head is not None and p_head.tag.gender:
            head_case = "loct" if "loc2" in p_head.tag else p_head.tag.case
            agreeing = [
                candidate
                for candidate in anum_parses
                if candidate.tag.gender == p_head.tag.gender
            ]
            if agreeing:
                p_left = next(
                    (c for c in agreeing if c.tag.case == head_case), agreeing[0]
                )
    case = "loct" if "loc2" in p_left.tag else p_left.tag.case
    ordinal = render_ordinal(
        site.value,
        case=case,
        gender=p_left.tag.gender,
        plural="plur" in p_left.tag,
        inanimate="anim" not in p_left.tag,
    )
    return [(i, i + 1, ordinal)], 1


#: Порядок — контракт: первый обработчик, узнавший свою конструкцию, забирает
#: токены. Прилагательное впереди, потому что «2 основные задачи» иначе разберётся
#: как число со считаемым существительным «основные».
_CARDINAL_HANDLERS = (
    _handle_coordinated_ordinal,
    _handle_adjective_and_noun,
    _handle_token_on_the_right,
)


def _number_site(
    tokens: list[str], idx: int, token_context: _NumeralTokenContext
) -> _NumberSite | None:
    """Собрать всё, что известно о числе до выбора обработчика; `None` — не число."""
    token = tokens[idx]
    first_char = token[:1]
    is_numeric_candidate = first_char.isnumeric() or first_char == NEGATIVE_NUMBER_PLACEHOLDER
    if not is_numeric_candidate and first_char in PUNCT_STRIP:
        stripped_candidate = token.strip(PUNCT_STRIP)
        is_numeric_candidate = bool(stripped_candidate) and (
            stripped_candidate[0].isnumeric()
            or stripped_candidate.startswith(NEGATIVE_NUMBER_PLACEHOLDER)
        )
    if not is_numeric_candidate:
        return None
    parsed_num = parse_integer_token(token)
    if parsed_num is None:
        return None

    is_negative, clean_token = parsed_num
    val = int(clean_token)
    case = get_numeral_case(tokens, idx, _context=token_context)
    # Without a counted noun the animacy of the accusative is unknown, and
    # pymorphy answers with the animate form ("двух"). A numeral standing on
    # its own is read as inanimate ("займёт два — три рабочих дня"); every
    # handler below that does find its noun recomputes the case with the real
    # animacy.
    range_agreement = _counted_noun_across_range(tokens, idx)
    if range_agreement is not None:
        range_gender, range_anim = range_agreement
        inflected_num = inflect_numeral_string(
            clean_token,
            paucal_accusative_case(val, case, animate=range_anim),
            range_gender,
            range_anim,
        )
    else:
        inflected_num = inflect_numeral_string(clean_token, inanimate_cardinal_case(val, case))
    return _NumberSite(
        tokens=tokens,
        idx=idx,
        token=token,
        clean_token=clean_token,
        value=val,
        is_negative=is_negative,
        case=case,
        num_words=build_number_token(token, clean_token, inflected_num, is_negative),
        token_context=token_context,
    )


def normalize_cardinal_numerals(text: str) -> str:
    tokens, spans = tokenize_with_spans(text)
    token_context = _build_numeral_token_context(tokens)
    segments: list[Segment] = []

    i = 0
    while i < len(tokens):
        site = _number_site(tokens, i, token_context)
        if site is None:
            segments.append((i, i + 1, None))
            i += 1
            continue
        for handler in _CARDINAL_HANDLERS:
            outcome = handler(site)
            if outcome is not None:
                handled, consumed = outcome
                segments.extend(handled)
                i += consumed
                break
        else:
            # Число само по себе: читается и занимает один токен.
            segments.append((i, i + 1, site.num_words))
            i += 1
    return _splice_segments(text, spans, segments)



def normalize_numeric_unit_ranges(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        left = match.group("left")
        right = match.group("right")
        unit_raw = match.group("unit")
        unit_info = _resolve_range_unit_info(unit_raw)
        if not unit_info:
            return match.group(0)
        context = text[max(0, match.start() - 40) : match.start()]
        tokens_left = simple_tokenize(context)
        context_after = text[match.end() : match.end() + 40]
        following_case: str | None = None
        for token in simple_tokenize(context_after)[:5]:
            clean_token = token.strip(".,!?;:()[]{}")
            if not clean_token:
                continue
            if any(char in token for char in ".!?;:"):
                break
            p_noun = select_parse(parse_word(clean_token), pos="NOUN")
            if p_noun is not None and is_case_reliable_noun(p_noun):
                noun_case = "loct" if "loc2" in p_noun.tag else p_noun.tag.case
                if noun_case in {"gent", "datv", "ablt", "loct"}:
                    following_case = noun_case
                break
            p_token = select_parse(parse_word(clean_token), pos={"VERB", "INFN"})
            if p_token is not None:
                break
        case = following_case or get_numeral_case(
            [*tokens_left, left], len(tokens_left)
        )
        u_gender = unit_info.gender
        u_suffix = unit_info.suffix

        def numeral_for_range(value_text: str) -> str:
            value = int(value_text)
            target_case = paucal_accusative_case(value, case, animate=False)
            return inflect_numeral_string(value_text, target_case, u_gender, False)

        right_value = int(right)
        unit_words = inflect_unit_lemma(
            unit_info,
            get_target_tags_for_number(right_value, case, u_gender),
            paucal=noun_number_form(right_value) == "few",
        )
        if u_suffix:
            unit_words += f" {u_suffix}"
        result = f"{numeral_for_range(left)} — {numeral_for_range(right)} {unit_words}"
        if match.group("udot") and should_keep_terminal_abbreviation_dot(
            text, match.end()
        ):
            # Точка сокращения («40—50 тыс.») поглощается вместе с ним; точка,
            # закрывающая предложение, остаётся.
            result += "."
        return result

    normalized = NUMERIC_UNIT_RANGE_PATTERN.sub(repl, text)

    def normalize_noun_range(match: re.Match[str]) -> str:
        noun = match.group("noun")
        p_noun = select_parse(parse_word(noun), pos="NOUN")
        if p_noun is None or not is_case_reliable_noun(p_noun):
            return match.group(0)

        noun_case = "loct" if "loc2" in p_noun.tag else p_noun.tag.case
        # Only a noun in an oblique case governs the range and needs this rule
        # ("обмен 3-5 квартирами"). A nominative or genitive noun is the
        # ordinary counted noun, and the range then belongs to the year stage
        # and the main cardinal pass, which read the whole sentence context.
        if noun_case not in {"datv", "ablt", "loct"}:
            return match.group(0)
        case = noun_case
        gender = p_noun.tag.gender
        left_words = inflect_numeral_string(match.group("left"), case, gender, False)
        right_words = inflect_numeral_string(match.group("right"), case, gender, False)
        return f"{left_words} — {right_words}{match.group('space')}{noun}"

    return _NUMERIC_NOUN_RANGE_PATTERN.sub(normalize_noun_range, normalized)


def normalize_remaining_post_numeral_abbreviations(text: str) -> str:
    def preserve_sentence_boundary(
        match: re.Match[str], replacement: str, source_text: str
    ) -> str:
        next_index, _ = first_non_whitespace_index(source_text, match.end())
        if next_index >= len(source_text):
            return f"{replacement}."
        next_char = source_text[next_index]
        if next_char in "\n.!?…":
            return f"{replacement}."
        return replacement

    def replace_abbreviation(match: re.Match[str]) -> str:
        key = " ".join(match.group(0).casefold().split())
        replacement = POST_NUMERAL_ABBREVIATION_REPLACEMENTS[key]
        return preserve_sentence_boundary(match, replacement, text)

    return POST_NUMERAL_ABBREVIATION_PATTERN.sub(replace_abbreviation, text)


def normalize_all_digits_everywhere(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        try:
            return num2words.num2words(int(match.group(0)), lang="ru")
        except Exception as exc:
            warn_once(
                logger,
                f"num2words-digits:{match.group(0)}",
                "num2words failed for %r: %s",
                match.group(0),
                exc,
            )
            return match.group(0)

    return DIGIT_PATTERN.sub(repl, text)
