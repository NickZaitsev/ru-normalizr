from __future__ import annotations

import logging
import re

from .._morph import canonicalize_case, parse_word, word_is_known
from ..constants import RU_VOWELS
from ..ordinal_utils import (
    render_ordinal,
)
from ..text_context import simple_tokenize
from ..text_scan import compile_scan
from ._constants import HYPHENATED_WORD_PATTERN
from ._helpers import get_numeral_case, inflect_numeral_string
from ._hyphen import classify_numeric_hyphen_rhs
from .numeric_suffixes import is_numeric_suffix, normalize_numeric_suffixes

logger = logging.getLogger(__name__)

HEADING_WORDS_PATTERN = (
    r"глава|главы|главе|главу|главой|главами|главах|"
    r"часть|части|частью|частях|"
    r"раздел|раздела|разделе|разделу|разделом|разделах|"
    r"том|тома|томе|томом|томах|"
    r"книга|книги|книге|книгой|книгах|"
    r"квартал|квартала|квартале|кварталу|кварталом|кварталах"
)
AMBIGUOUS_HEADING_WORDS = {
    "главы",
    "части",
    "раздела",
    "тома",
    "книги",
    "квартала",
}
HEADING_CONTEXT_CASES = {
    "в": "loct",
    "во": "loct",
    "о": "loct",
    "об": "loct",
    "обо": "loct",
    "при": "loct",
    "к": "datv",
    "ко": "datv",
    "по": "datv",
    "с": "gent",
    "со": "gent",
    "из": "gent",
    "до": "gent",
    "от": "gent",
    "у": "gent",
    "без": "gent",
    "после": "gent",
    "для": "gent",
    "около": "gent",
    "возле": "gent",
    "вокруг": "gent",
    "кроме": "gent",
    "начало": "gent",
    "конец": "gent",
    "середина": "gent",
    "см": "accs",
    "смотри": "accs",
}
SINGULAR_HEADING_WORDS_PATTERN = (
    r"глава|главы|главе|главу|главой|"
    r"часть|части|частью|"
    r"раздел|раздела|разделе|разделу|"
    r"книга|книги|книге|книгой|"
    r"квартал|квартала|квартале|кварталу|кварталом"
)
HEADING_RANGE_PATTERN = compile_scan(
    rf"\b(?P<head>{HEADING_WORDS_PATTERN})\s+(?P<left>\d+)\s*[–—-]\s*(?P<right>\d+)\b",
    re.IGNORECASE | re.UNICODE,
)
HEADING_SINGLE_PATTERN = compile_scan(
    rf"\b(?P<head>{SINGULAR_HEADING_WORDS_PATTERN})\s+(?P<number>\d+)\b",
    re.IGNORECASE | re.UNICODE,
)
ABBREVIATED_HEADING_RANGE_PATTERN = compile_scan(
    r"\b(?P<head>гл)\.\s*(?P<left>\d+)\s*[–—-]\s*(?P<right>\d+)\b",
    re.IGNORECASE | re.UNICODE,
)
ABBREVIATED_HEADING_PATTERN = compile_scan(
    r"\b(?P<head>гл)\.\s*(?P<number>\d+)\b",
    re.IGNORECASE | re.UNICODE,
)
COMPOUND_ADJECTIVE_STEMS = (
    "комнатн",
    "тонн",
    "местн",
    "ступенчат",
    "этажн",
    "кратн",
    "дневн",
    "часов",
    "летн",
)
COMPOUND_ADJECTIVE_PATTERN = compile_scan(
    rf"(?<!\d)(?P<num>\d+)(?:\s*[-–—]?\s*(?P<suffix>и|х))?\s+(?P<adj>(?:{'|'.join(COMPOUND_ADJECTIVE_STEMS)})[а-яё]+)\b",
    re.IGNORECASE | re.UNICODE,
)
PERCENT_COMPOUND_ADJECTIVE_PATTERN = compile_scan(
    r"(?<!\d)(?P<num>\d+)\s*%\s*[-–—]?\s*(?P<suffix>н(?:ый|ая|ое|ые|ого|ой|ому|ым|ом|ую|ых|ыми))\b",
    re.IGNORECASE | re.UNICODE,
)


def _ordinal_words(num: int, case: str, gender: str | None) -> str:
    return render_ordinal(num, case=case, gender=gender)


#: Согласные, после которых «с» наращивается до «со», — но только если за
#: ними идёт ещё одна согласная: стечение «ст», «вт» произнести без гласной
#: нельзя, а «во», «ше», «се» — можно.
_RANGE_PREPOSITION_CLUSTER_HEADS = frozenset("вфсзшж")


def _pick_range_preposition(first_ordinal: str) -> str:
    """«со второго», «со стотысячного», но «с восьмого», «с сотого»."""

    head = first_ordinal[:2].lower()
    if len(head) < 2 or head[0] not in _RANGE_PREPOSITION_CLUSTER_HEADS:
        return "с"
    return "с" if head[1].upper() in RU_VOWELS else "со"


def _heading_gender(head: str) -> str:
    """Род вершины рубрикации, когда её падеж по контексту не определился.

    У «главы», «части», «книги» род стабилен, а неоднозначен только падеж:
    «главы 8-9» без предлога слева `_heading_parse` разобрать не может, но
    женский род известен и там. Одушевлённый омоним («глава» как начальник)
    для рубрики невозможен, поэтому предпочитается неодушевлённый разбор —
    тот же, который `_heading_parse` уже отбирает для выбора падежа.
    """
    nouns = [candidate for candidate in parse_word(head.lower()) if "NOUN" in candidate.tag]
    inanimate = [candidate for candidate in nouns if "inan" in candidate.tag]
    for candidate in inanimate or nouns:
        if candidate.tag.gender:
            return candidate.tag.gender
    return "masc"


def _heading_parse(text: str, match_start: int, head: str):
    parsed = [candidate for candidate in parse_word(head.lower()) if "NOUN" in candidate.tag]
    if not parsed:
        return None
    inanimate = [candidate for candidate in parsed if "inan" in candidate.tag]
    candidates = inanimate if inanimate else parsed
    normalized_head = head.lower()
    if normalized_head not in AMBIGUOUS_HEADING_WORDS:
        nominative_singular = [
            candidate
            for candidate in candidates
            if ("sing" in candidate.tag and "nomn" in candidate.tag)
        ]
        if nominative_singular:
            return nominative_singular[0]
        return candidates[0]

    left_context = text[max(0, match_start - 40) : match_start]
    left_tokens = simple_tokenize(left_context)
    left_word = next(
        (token.lower() for token in reversed(left_tokens) if any(char.isalpha() for char in token)),
        "",
    )
    target_case = HEADING_CONTEXT_CASES.get(left_word)
    if target_case is None:
        return None

    for candidate in candidates:
        candidate_case = canonicalize_case(candidate.tag.case)
        if candidate_case == target_case and "sing" in candidate.tag:
            return candidate
    for candidate in candidates:
        candidate_case = canonicalize_case(candidate.tag.case)
        if candidate_case == target_case:
            return candidate
    return None


def normalize_heading_ranges(text: str) -> str:
    def render_range(head: str, noun_parse, left: int, right: int) -> str:
        gender = (
            noun_parse.tag.gender if noun_parse and noun_parse.tag.gender else None
        ) or _heading_gender(head)
        left_ordinal = _ordinal_words(left, "gent", gender)
        right_case = "accs" if gender == "femn" else "nomn"
        right_ordinal = _ordinal_words(right, right_case, gender)
        rendered_head = head
        if noun_parse:
            target_case = noun_parse.tag.case or "nomn"
            plural_head = noun_parse.inflect({target_case, "plur"})
            if plural_head:
                rendered_head = plural_head.word
                if head[:1].isupper():
                    rendered_head = rendered_head.capitalize()
        return (
            f"{rendered_head} {_pick_range_preposition(left_ordinal)} "
            f"{left_ordinal} по {right_ordinal}"
        )

    def repl(match: re.Match[str]) -> str:
        head = match.group("head")
        noun_parse = _heading_parse(text, match.start(), head)
        return render_range(head, noun_parse, int(match.group("left")), int(match.group("right")))

    def abbreviated_repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 40) : match.start()]
        left_tokens = simple_tokenize(left_context)
        left_word = next(
            (
                token.lower()
                for token in reversed(left_tokens)
                if any(char.isalpha() for char in token)
            ),
            "",
        )
        target_case = HEADING_CONTEXT_CASES.get(left_word, "nomn")
        noun_parse = next(
            (
                candidate
                for candidate in parse_word("глава")
                if "NOUN" in candidate.tag and "nomn" in candidate.tag and "inan" in candidate.tag
            ),
            None,
        )
        if noun_parse is None:
            return match.group(0)
        inflected_noun = noun_parse.inflect({target_case, "plur"})
        if inflected_noun is None:
            return match.group(0)
        left_ordinal = _ordinal_words(int(match.group("left")), "gent", "femn")
        right_ordinal = _ordinal_words(int(match.group("right")), "accs", "femn")
        return (
            f"{inflected_noun.word} {_pick_range_preposition(left_ordinal)} "
            f"{left_ordinal} по {right_ordinal}"
        )

    text = ABBREVIATED_HEADING_RANGE_PATTERN.sub(abbreviated_repl, text)
    return HEADING_RANGE_PATTERN.sub(repl, text)


def normalize_heading_numbers(text: str) -> str:
    def abbreviated_repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 40) : match.start()]
        left_tokens = simple_tokenize(left_context)
        left_word = next(
            (
                token.lower()
                for token in reversed(left_tokens)
                if any(char.isalpha() for char in token)
            ),
            "",
        )
        target_case = HEADING_CONTEXT_CASES.get(left_word, "nomn")
        noun_parse = next(
            (candidate for candidate in parse_word("глава") if "NOUN" in candidate.tag),
            None,
        )
        if noun_parse is None:
            return match.group(0)
        inflected_noun = noun_parse.inflect({target_case, "sing"})
        if inflected_noun is None:
            return match.group(0)
        ordinal = _ordinal_words(int(match.group("number")), target_case, "femn")
        return f"{inflected_noun.word} {ordinal}"

    def repl(match: re.Match[str]) -> str:
        head = match.group("head")
        noun_parse = _heading_parse(text, match.start(), head)
        if noun_parse is None:
            return match.group(0)
        gender = noun_parse.tag.gender or "masc"
        case = noun_parse.tag.case or "nomn"
        ordinal = _ordinal_words(int(match.group("number")), case, gender)
        return f"{head} {ordinal}"

    text = ABBREVIATED_HEADING_PATTERN.sub(abbreviated_repl, text)
    return HEADING_SINGLE_PATTERN.sub(repl, text)


def _compound_numeral_prefix(num_str: str) -> str:
    try:
        value = int(num_str)
    except ValueError:
        return num_str
    if value == 0:
        return "нуле"
    for scale, stem in (
        (1_000_000_000, "миллиардо"),
        (1_000_000, "миллионо"),
        (1_000, "тысяче"),
    ):
        if value >= scale:
            scale_count, remainder = divmod(value, scale)
            count_prefix = "" if scale_count == 1 else _compound_numeral_prefix(str(scale_count))
            remainder_prefix = "" if remainder == 0 else _compound_numeral_prefix(str(remainder))
            return f"{count_prefix}{stem}{remainder_prefix}"
    if value == 1:
        return "одно"
    if value == 2:
        return "двух"
    if value == 3:
        return "трёх"
    if value == 4:
        return "четырёх"
    words = inflect_numeral_string(num_str, "gent").split()
    # «девяносто» — единственная основа, которая в сложном прилагательном не
    # переходит в родительный: «девяностолетний», не «девяносталетний». В
    # составном числе она стоит не обязательно первой, поэтому правится в
    # любой позиции: «стодевяностолетний», «тысячедевяностолетний».
    words = ["девяносто" if word == "девяноста" else word for word in words]
    if value == 100:
        return "сто"
    if 100 < value < 200 and words[:1] == ["ста"]:
        words[0] = "сто"
    if value % 10 == 1 and value % 100 != 11 and words[-1:] == ["одного"]:
        words[-1] = "одно"
    return "".join(words)


def _join_compound_numeral(prefix: str, word: str) -> str:
    combined = f"{prefix}{word.lower()}"
    if word.isupper():
        return combined.upper()
    if word[:1].isupper():
        return combined.capitalize()
    return combined


def normalize_compound_numeric_adjectives(text: str) -> str:
    def numeral_can_govern_singular(value: int) -> bool:
        return value % 10 == 1 and value % 100 != 11

    def repl(match: re.Match[str]) -> str:
        adjective = match.group("adj")
        adjective_parses = [
            candidate for candidate in parse_word(adjective.lower()) if "ADJF" in candidate.tag
        ]
        if not adjective_parses:
            return match.group(0)
        value = int(match.group("num"))
        if numeral_can_govern_singular(value) or any(
            "plur" in candidate.tag for candidate in adjective_parses
        ):
            return match.group(0)
        prefix = _compound_numeral_prefix(match.group("num"))
        return _join_compound_numeral(prefix, adjective)

    def percent_repl(match: re.Match[str]) -> str:
        prefix = _compound_numeral_prefix(match.group("num"))
        suffix = match.group("suffix")
        word = f"процент{suffix.lower()}"
        if suffix.isupper():
            word = word.upper()
        elif suffix[:1].isupper():
            word = word.capitalize()
        return _join_compound_numeral(prefix, word)

    text = PERCENT_COMPOUND_ADJECTIVE_PATTERN.sub(percent_repl, text)
    return COMPOUND_ADJECTIVE_PATTERN.sub(repl, text)


#: Case endings of a numeral that authors duplicate at the start of the glued
#: word: «60-тиверстная» spells the «-ти» of «шестидесяти» twice.
_CARDINAL_INFIXES = ("тью", "ти", "ми", "мя", "ух", "ех", "ёх", "х")
#: Endings of «тысячный» written after a round number: «40000-ным войском».
_THOUSANDS_ADJECTIVE_SUFFIX_PATTERN = compile_scan(
    r"н(?:ый|ая|ое|ые|ого|ой|ому|ым|им|ом|ем|ую|ых|ыми)ъ?", re.IGNORECASE
)
RANGE_COMPOUND_ADJECTIVE_PATTERN = compile_scan(
    r"(?<![\w\d])(?P<left>\d+)\s*[–—]\s*(?P<right>\d+)-(?P<word>[а-яёА-ЯЁ]{3,})"
)
PREFIXED_ORDINAL_ADVERB_PATTERN = compile_scan(
    r"(?<![\w-])(?P<prefix>в|во)-(?P<num>\d{1,2})(?:-х)?(?=[,;:.)])",
    re.IGNORECASE,
)
EDITION_ORDINAL_PATTERN = compile_scan(
    r"\bизд\.\s*(?P<num>\d+)-е(?!\w)", re.IGNORECASE
)


#: Буквы, изъятые реформой 1918 года: у каждой ровно один современный
#: эквивалент, поэтому замена однозначна и обратима на уровне классификации.
_PRE_REFORM_LETTERS = str.maketrans({"і": "и", "ѣ": "е", "ѳ": "ф", "ѵ": "и"})


def _modern_spelling(word_lower: str) -> str:
    """Pre-reform spelling mapped to its modern form, for classification only.

    Морфология знает только современную орфографию, поэтому дореформенное
    прилагательное («фунтовыя», «лѣтній») ей неизвестно и составное числительное
    к нему не приклеивается. Написание приводится к современному лишь для
    разбора — в текст возвращается исходное слово.
    """
    spelling = word_lower.translate(_PRE_REFORM_LETTERS)
    if spelling.endswith("ъ"):
        spelling = spelling[:-1]
    if spelling.endswith("аго"):
        spelling = spelling[:-3] + "ого"
    elif spelling.endswith("яго"):
        spelling = spelling[:-3] + "его"
    elif spelling.endswith("ыя"):
        # Женский и средний род множественного числа: «полевыя» → «полевые».
        spelling = spelling[:-2] + "ые"
    elif spelling.endswith("ия") and len(spelling) > 4:
        # То же для мягкой основы: «синія» → «синие». Короткие слова исключены,
        # иначе под правило попадают существительные вроде «имя» или «выя».
        spelling = spelling[:-2] + "ие"
    return spelling


def _is_adjective_spelling(spelling: str) -> bool:
    return any("ADJF" in candidate.tag for candidate in parse_word(spelling))


def _strip_duplicated_infix(prefix: str, word: str) -> str | None:
    """Drop the numeral's case ending duplicated at the start of the word.

    The remainder must be a dictionary adjective: «минутный» after «восьми»
    starts with «ми» too, but «нутный» is not a word, so it stays intact.
    """
    word_lower = word.lower()
    for infix in _CARDINAL_INFIXES:
        if word_lower.startswith(infix) and prefix.endswith(infix):
            remainder = word[len(infix) :]
            spelling = _modern_spelling(remainder.lower())
            if (
                len(spelling) >= 4
                and word_is_known(spelling)
                and _is_adjective_spelling(spelling)
            ):
                return remainder
    return None


def normalize_range_compound_adjectives(text: str) -> str:
    """«6—7-тысячного отряда» → «шести-семитысячного отряда»."""

    def repl(match: re.Match[str]) -> str:
        word = match.group("word")
        if not _is_adjective_spelling(_modern_spelling(word.lower())):
            return match.group(0)
        left = _compound_numeral_prefix(match.group("left"))
        right = _compound_numeral_prefix(match.group("right"))
        return f"{left}-{_join_compound_numeral(right, word)}"

    return RANGE_COMPOUND_ADJECTIVE_PATTERN.sub(repl, text)


def normalize_prefixed_ordinal_adverbs(text: str) -> str:
    """«во-1, … а во-2,» → «во-первых, … а во-вторых,»."""

    def repl(match: re.Match[str]) -> str:
        try:
            adverb = render_ordinal(
                int(match.group("num")), case="gent", plural=True, inanimate=True
            )
        except (TypeError, ValueError):
            return match.group(0)
        return f"{match.group('prefix')}-{adverb}"

    return PREFIXED_ORDINAL_ADVERB_PATTERN.sub(repl, text)


def normalize_edition_ordinals(text: str) -> str:
    """«Изд. 2-е» → «издание второе»."""

    def repl(match: re.Match[str]) -> str:
        return f"издание {_ordinal_words(int(match.group('num')), 'nomn', 'neut')}"

    return EDITION_ORDINAL_PATTERN.sub(repl, text)


THOUSANDS_ABBREVIATED_ATTRIBUTE_PATTERN = compile_scan(
    r"(?<![\w\d])(?P<num>\d+)-тыс\.\s+(?P<noun>[а-яёА-ЯЁ]+)"
)


def normalize_thousands_abbreviated_attributes(text: str) -> str:
    """«15-тыс. отряд» → «пятнадцатитысячный отряд», agreeing with the noun."""

    def repl(match: re.Match[str]) -> str:
        noun = match.group("noun")
        noun_parse = next(
            (candidate for candidate in parse_word(noun) if "NOUN" in candidate.tag),
            None,
        )
        if noun_parse is None:
            return match.group(0)
        adjective_parse = next(
            (
                candidate
                for candidate in parse_word("тысячный")
                if "ADJF" in candidate.tag
            ),
            None,
        )
        if adjective_parse is None:
            return match.group(0)
        tags = {canonicalize_case(noun_parse.tag.case) or "nomn"}
        if "plur" in noun_parse.tag:
            tags.add("plur")
        else:
            tags.add("sing")
            if noun_parse.tag.gender:
                tags.add(noun_parse.tag.gender)
        inflected = adjective_parse.inflect(frozenset(tags))
        if inflected is None:
            return match.group(0)
        prefix = _compound_numeral_prefix(match.group("num"))
        return f"{_join_compound_numeral(prefix, inflected.word)} {noun}"

    return THOUSANDS_ABBREVIATED_ATTRIBUTE_PATTERN.sub(repl, text)


def normalize_hyphenated_words(
    text: str, *, include_numeric_suffixes: bool = True
) -> str:
    if include_numeric_suffixes:
        text = normalize_numeric_suffixes(text)
    text = normalize_range_compound_adjectives(text)

    def repl(match: re.Match[str]) -> str:
        num_str = match.group("num")
        infix = match.group("infix")
        word = match.group("word")
        word_lower = word.lower()
        if infix is None and is_numeric_suffix(word_lower):
            return match.group(0)
        if infix is None and classify_numeric_hyphen_rhs(word) == "unit":
            return match.group(0)
        try:
            value = int(num_str)
        except ValueError as exc:
            logger.debug("int() failed for %r: %s", num_str, exc)
            return match.group(0)
        if (
            value >= 1000
            and value % 1000 == 0
            and _THOUSANDS_ADJECTIVE_SUFFIX_PATTERN.fullmatch(word_lower)
        ):
            # «40000-ным» carries only the tail of «тысячным»: the thousands
            # live in the digits and the stem is implied.
            num_str = str(value // 1000)
            word = f"тысяч{word}"
            word_lower = word.lower()
        prefix = _compound_numeral_prefix(num_str)
        stripped = _strip_duplicated_infix(prefix, word)
        if stripped is not None:
            word = stripped
            word_lower = word.lower()
        classification_spelling = _modern_spelling(word_lower)
        word_parses = parse_word(classification_spelling)
        is_adj_like = any(
            "ADJF" in candidate.tag for candidate in word_parses
        ) or classification_spelling.endswith(
            (
                "дневный",
                "часовой",
                "минутный",
                "летний",
                "этажный",
                "тонный",
                "процентный",
                "кратный",
                "кратного",
                "кратном",
                "кратных",
            )
        )
        if is_adj_like:
            return _join_compound_numeral(prefix, word)
        if infix is not None or not any(
            "NOUN" in candidate.tag for candidate in word_parses
        ):
            return match.group(0)
        ctx_left = text[max(0, match.start() - 60) : match.start()]
        ctx_right = text[match.end() : match.end() + 60]
        tokens_left = simple_tokenize(ctx_left)
        tokens_right = simple_tokenize(ctx_right)
        case = get_numeral_case(
            [*tokens_left, num_str, *tokens_right], len(tokens_left)
        )
        num_words = inflect_numeral_string(num_str, case)
        return f"{num_words} {word}"

    return HYPHENATED_WORD_PATTERN.sub(repl, text)


def normalize_ordinals(text: str, *, capitalize_text_start: bool = False) -> str:
    return normalize_numeric_suffixes(
        text, capitalize_text_start=capitalize_text_start
    )
