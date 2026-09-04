from __future__ import annotations

import logging
import re

import num2words

from .._log_once import warn_once
from .._morph import (
    canonicalize_case,
    first_parse_required,
    parse_word,
    select_parse,
)
from ..text_context import simple_tokenize
from ..text_scan import compile_scan
from ._constants import (
    FRACTION_PATTERN,
    UNIT_TOKEN_FRAGMENT,
    resolve_unit_form,
    resolve_unit_info,
)
from ._helpers import (
    get_numeral_case,
    get_target_tags_for_number,
    inflect_numeral_string,
    noun_number_form,
    safe_inflect,
)
from .unit_registry import UnitDescriptor
from .unit_rendering import render_unit_expression

logger = logging.getLogger(__name__)

# Помимо первообразных предлогов родительный падеж задают отымённые
# («ценой краткой борьбы», «путём проб»): это закрытый грамматический класс.
# Дореформенные написания («цѣною», «отъ») входят в те же альтернативы.
GENITIVE_FRACTION_CONTEXT_PATTERN = compile_scan(
    r"\b(съ?|со|отъ?|до|изъ?|безъ?|у|ц[еѣ]ной|ц[еѣ]ною|путём|путемъ?|посредствомъ?)\s+$"
)
DATIVE_FRACTION_CONTEXT_PATTERN = compile_scan(r"\b(к|по)\s+$")
ACCUSATIVE_FRACTION_CONTEXT_PATTERN = compile_scan(r"\b(в|на|через)\s+$")
PREPOSITIONAL_FRACTION_CONTEXT_PATTERN = compile_scan(r"\b(о|об|при)\s+$")
FRACTION_UNIT_PATTERN = compile_scan(
    rf"(?<![\d,])(?P<num>\d+)/(?P<denom>\d+)(?P<space>\s+)"
    rf"(?P<unit>{UNIT_TOKEN_FRAGMENT})(?!\w)"
)
FRACTION_COMPOUND_UNIT_PATTERN = compile_scan(
    r"(?<![\d,])(?P<num>\d+)/(?P<denom>\d+)(?P<space>\s+)"
    r"(?P<unit>ч\.\s*л\.)(?!\w)",
    re.IGNORECASE,
)
PRESSURE_RATIO_PATTERN = compile_scan(
    r"(?<!\w)(?:(?P<prep>с|со|до)\s+)?"
    r"(?P<left>\d{2,3})\s*/\s*(?P<right>\d{2,3})",
    re.IGNORECASE,
)
# Смешанная дробь: целая часть и простая дробь через пробел («1 1/3 гривны»);
# следом может стоять единица измерения («1 1/2 коп.», «2 1/2°»). Точка
# сокращения поглощается только перед строчной буквой — в конце предложения
# она остаётся точкой.
MIXED_FRACTION_PATTERN = compile_scan(
    rf"(?<![\d,./])(?P<int>\d+)\s+(?P<num>\d+)/(?P<denom>\d+)(?![\d,/])"
    rf"(?:(?P<uspace>\s*)(?P<unit>{UNIT_TOKEN_FRAGMENT})(?:\.(?=\s+[а-яё]))?(?!\w))?"
)
# Дробь-определение перед словом: «½-пудовой» — морфологическое «полу-»,
# а не числительное с наращением.
HALF_ATTRIBUTE_PATTERN = compile_scan(r"(?<![\d,./])1/2-(?=[а-яёА-ЯЁ])")
# Косая черта после раскрытого «№» — разделитель частей шифра, читается
# словом «дробь», а не дробью: «под номером 72 дробь 288».
REFERENCE_SLASH_PATTERN = compile_scan(
    r"(?<!\w)(?P<head>номер(?:ом|у|а|е)?)\s+(?P<left>\d+)\s*/\s*(?P<right>\d+)(?![\d/])",
    re.IGNORECASE,
)
# Однобуквенные «единицы», совпадающие с предлогами: «1/8 с дробями» — это
# предлог «с», а не секунды. Предложное чтение признаётся только когда
# следующее слово стоит в падеже, которым предлог управляет («с дробями» —
# творительный); «1/8 с при нагреве» остаётся секундами.
_PREPOSITION_HOMOGRAPH_GOVERNED_CASES = {
    "с": frozenset({"ablt", "gent"}),
    "в": frozenset({"accs", "loct"}),
    "у": frozenset({"gent"}),
    "к": frozenset({"datv"}),
}
_NEXT_WORD_PATTERN = compile_scan(r"\s+([а-яёА-ЯЁ]+)")


def normalize_fractions(text: str) -> str:
    def pressure_ratio_repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 80) : match.start()]
        if not re.search(r"\bдавлен\w*", left_context, re.IGNORECASE):
            return match.group(0)
        prep = match.group("prep")
        rendered_prep = "со" if prep and prep.casefold() == "с" else prep
        prefix = f"{rendered_prep} " if rendered_prep else ""
        return f"{prefix}{match.group('left')} на {match.group('right')}"

    text = PRESSURE_RATIO_PATTERN.sub(pressure_ratio_repl, text)

    def reference_slash_repl(match: re.Match[str]) -> str:
        try:
            left = num2words.num2words(int(match.group("left")), lang="ru")
            right = num2words.num2words(int(match.group("right")), lang="ru")
        except Exception as exc:
            warn_once(
                logger,
                f"num2words-reference-slash:{match.group(0)}",
                "num2words failed for reference %r: %s",
                match.group(0),
                exc,
            )
            return match.group(0)
        return f"{match.group('head')} {left} дробь {right}"

    text = REFERENCE_SLASH_PATTERN.sub(reference_slash_repl, text)
    text = HALF_ATTRIBUTE_PATTERN.sub("полу", text)

    def fraction_case(start: int) -> str:
        # 16 символов покрывают самый длинный управляющий предлог
        # («посредством ») вместе с границей слова.
        context = text[max(0, start - 16) : start].lower()
        case = "nomn"
        if GENITIVE_FRACTION_CONTEXT_PATTERN.search(context):
            case = "gent"
        elif DATIVE_FRACTION_CONTEXT_PATTERN.search(context):
            case = "datv"
        elif ACCUSATIVE_FRACTION_CONTEXT_PATTERN.search(context):
            case = "accs"
        elif PREPOSITIONAL_FRACTION_CONTEXT_PATTERN.search(context):
            case = "loct"
        else:
            context_tokens = simple_tokenize(text[max(0, start - 40) : start] + " 0")
            if context_tokens:
                governed_case = get_numeral_case(
                    context_tokens, len(context_tokens) - 1
                )
                if governed_case != "nomn":
                    case = governed_case
        return canonicalize_case(case)

    def render_fraction(num: int, denom: int, case: str) -> str | None:
        numerator_gender = (
            "femn"
            if num % 10 in {1, 2} and num % 100 not in {11, 12}
            else None
        )
        num_text = inflect_numeral_string(
            str(num), case, numerator_gender, animate=False
        )
        if not num_text:
            return None
        if numerator_gender is not None:
            words = num_text.split()
            selected = select_parse(
                words[-1], pos={"NUMR", "ADJF"}, preferred_grammemes={"Anum"}
            )
            if selected is not None:
                target_tags = {case, numerator_gender}
                if num % 10 == 1:
                    target_tags.add("sing")
                words[-1] = safe_inflect(
                    selected,
                    target_tags,
                    fallback_word=words[-1],
                )
                num_text = " ".join(words)
        try:
            denom_text = num2words.num2words(denom, lang="ru", to="ordinal")
        except Exception as exc:
            warn_once(
                logger,
                f"num2words-denominator:{denom}",
                "num2words failed for denominator %r: %s",
                denom,
                exc,
            )
            return None
        words = denom_text.split()
        if len(words) > 1:
            first_denominator_word = first_parse_required(words[0])
            if first_denominator_word.tag.POS == "NUMR":
                inflected_first = first_denominator_word.inflect({"gent"})
                if inflected_first is not None:
                    words[0] = inflected_first.word
        is_sing_1 = num % 10 == 1 and num % 100 != 11
        # Существительное «треть» согласуется с числителем как счётное слово,
        # и его формы есть только для числителей на 1—4: «одна треть», «две
        # трети». От пяти русский переходит на адъективную парадигму — «пять
        # третьих», — поэтому такие числители идут общим путём ниже.
        noun_third_numerator = num % 10 in {1, 2, 3, 4} and num % 100 not in {
            11,
            12,
            13,
            14,
        }
        if denom == 3 and case in {"nomn", "accs"} and noun_third_numerator:
            # In the nominative/accusative Russian uses the noun fraction
            # "треть": "две трети". Oblique cases retain the adjectival
            # paradigm already used by the public fraction contract.
            return f"{num_text} {'треть' if is_sing_1 else 'трети'}"
        p = first_parse_required(words[-1])
        magnitude_numerator = num >= 1000 and num % 1000 == 0
        inflected = p.inflect(
            {case, "femn", "sing"}
            if is_sing_1
            else (
                {"gent", "plur"}
                if case in ["nomn", "accs"] or magnitude_numerator
                else {case, "plur"}
            )
        )
        if inflected:
            words[-1] = inflected.word
        return f"{num_text} {' '.join(words)}"

    def counted_noun_gender(end: int) -> str | None:
        next_word = _NEXT_WORD_PATTERN.match(text, end)
        if next_word is None:
            return None
        parsed = select_parse(next_word.group(1).lower(), pos="NOUN")
        return parsed.tag.gender if parsed is not None else None

    def preposition_reading(unit_raw: str, source: str, end: int) -> bool:
        """Однобуквенная «единица» на деле читается как предлог."""
        governed_cases = _PREPOSITION_HOMOGRAPH_GOVERNED_CASES.get(
            unit_raw.casefold().strip(".")
        )
        if governed_cases is None:
            return False
        next_word = _NEXT_WORD_PATTERN.match(source, end)
        if next_word is None:
            return False
        # Только доминирующий разбор: у «при» и «ровно» есть
        # мусорные именные разборы с нулевой вероятностью.
        parses = parse_word(next_word.group(1).lower())
        return bool(
            parses
            and parses[0].tag.POS in {"NOUN", "NPRO", "ADJF", "PRTF"}
            and parses[0].tag.case in governed_cases
        )

    def render_half_unit(
        int_val: int, case: str, unit_info: UnitDescriptor
    ) -> str | None:
        """«1 1/2 коп.» — «полторы копейки», «2 1/2°» — «два с половиной градуса»."""
        gender = unit_info.gender
        if int_val == 1:
            if case in {"nomn", "accs"}:
                numeral = "полторы" if gender == "femn" else "полтора"
                noun = render_unit_expression(unit_info, {"gent", "sing"})
            else:
                numeral = "полутора"
                noun = render_unit_expression(unit_info, {case, "plur"})
            return f"{numeral} {noun}"
        int_words = inflect_numeral_string(str(int_val), case, gender, animate=False)
        if not int_words:
            return None
        noun = render_unit_expression(
            unit_info,
            get_target_tags_for_number(int_val, case, gender),
            paucal=noun_number_form(int_val) == "few",
        )
        return f"{int_words} с половиной {noun}"

    def render_half_word(int_val: int, case: str, end: int) -> str | None:
        """«1 1/2» — «полтора», «N 1/2» — «N с половиной»."""
        if int_val == 1:
            parsed = select_parse("полтора", pos="NUMR")
            if parsed is None:
                return None
            if canonicalize_case(case) in {"nomn", "accs"}:
                return "полтора"
            inflected = parsed.inflect({canonicalize_case(case)})
            return inflected.word if inflected is not None else None
        # Целая часть согласуется со считаемым существительным:
        # «2½ ложки» — «две с половиной ложки».
        int_words = inflect_numeral_string(
            str(int_val), case, counted_noun_gender(end), animate=False
        )
        if not int_words:
            return None
        return f"{int_words} с половиной"

    def mixed_fraction_repl(match: re.Match[str]) -> str:
        int_val = int(match.group("int"))
        num = int(match.group("num"))
        denom = int(match.group("denom"))
        case = fraction_case(match.start())
        unit_raw = match.group("unit")
        unit_info = None
        tail = ""
        if unit_raw is not None:
            if not preposition_reading(unit_raw, match.string, match.end()):
                unit_info = resolve_unit_info(unit_raw) or resolve_unit_form(unit_raw)
            if unit_info is None:
                # Вернуть хвост дословно, включая возможную точку сокращения.
                tail = match.string[match.end("denom") : match.end()]
        if num == 1 and denom == 2:
            if unit_info is not None:
                # Распределительное «по» управляет винительным:
                # «по 1 1/2 коп.» — «по полторы копейки».
                half_case = (
                    "accs"
                    if case == "datv"
                    and re.search(r"\bпо\s+$", text[max(0, match.start() - 8) : match.start()].lower())
                    else case
                )
                rendered_half = render_half_unit(int_val, half_case, unit_info)
            else:
                rendered_half = render_half_word(int_val, case, match.end("denom"))
            if rendered_half is None:
                return match.group(0)
            return f"{rendered_half}{tail}"
        fraction_words = render_fraction(num, denom, case)
        if fraction_words is None:
            return match.group(0)
        int_words = inflect_numeral_string(str(int_val), case, "femn", animate=False)
        if not int_words:
            return match.group(0)
        p_cel = first_parse_required("целая")
        tags_cel = (
            {case, "femn", "sing"}
            if int_val % 10 == 1 and int_val % 100 != 11
            else (
                {"gent", "plur"} if case in {"nomn", "accs"} else {case, "plur"}
            )
        )
        cel_words = safe_inflect(p_cel, tags_cel, fallback_word="целых")
        if unit_info is not None:
            # Дробь управляет родительным единственного: «три четвёртых золотника».
            noun = render_unit_expression(
                unit_info, {"gent", "sing", unit_info.gender}
            )
            return f"{int_words} {cel_words} {fraction_words} {noun}"
        return f"{int_words} {cel_words} {fraction_words}{tail}"

    def with_unit_repl(match: re.Match[str]) -> str:
        unit_raw = match.group("unit")
        if preposition_reading(unit_raw, match.string, match.end()):
            return match.group(0)
        unit_info = resolve_unit_info(unit_raw) or resolve_unit_form(unit_raw)
        if unit_info is None:
            return match.group(0)
        rendered_fraction = render_fraction(
            int(match.group("num")),
            int(match.group("denom")),
            fraction_case(match.start()),
        )
        if rendered_fraction is None:
            return match.group(0)
        return (
            f"{rendered_fraction} "
            f"{render_unit_expression(unit_info, {'gent', 'sing', unit_info.gender})}"
        )

    def with_compound_unit_repl(match: re.Match[str]) -> str:
        unit_raw = match.group("unit").replace(" ", "")
        unit_info = resolve_unit_info(unit_raw)
        if unit_info is None:
            return match.group(0)
        rendered_fraction = render_fraction(
            int(match.group("num")),
            int(match.group("denom")),
            fraction_case(match.start()),
        )
        if rendered_fraction is None:
            return match.group(0)
        return (
            f"{rendered_fraction} "
            f"{render_unit_expression(unit_info, {'gent', 'sing', unit_info.gender})}"
        )

    normalized = MIXED_FRACTION_PATTERN.sub(mixed_fraction_repl, text)
    normalized = FRACTION_COMPOUND_UNIT_PATTERN.sub(
        with_compound_unit_repl, normalized
    )
    normalized = FRACTION_UNIT_PATTERN.sub(with_unit_repl, normalized)

    def repl(match: re.Match[str]) -> str:
        rendered = render_fraction(
            int(match.group(1)), int(match.group(2)), fraction_case(match.start())
        )
        return rendered if rendered is not None else match.group(0)

    return FRACTION_PATTERN.sub(repl, normalized)
