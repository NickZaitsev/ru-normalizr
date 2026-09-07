from __future__ import annotations

import functools
import re

from ._morph import MorphParse, parse_word
from .text_scan import first_non_whitespace_index

BIRTH_YEAR_ABBREVIATION_PATTERN = re.compile(
    r"(?<!\w)(?P<year>\d{2,4})\s*г\.\s*р\.(?!\w)",
    re.IGNORECASE,
)
MASS_GRAM_ABBREVIATION_PATTERN = re.compile(
    r"(?P<context>\b(?:вес|масса)\b\s+)(?P<num>\d+)\s*г(?P<dot>\.)?(?!\w)",
    re.IGNORECASE,
)
_SHORT_ABBREVIATED_YEAR_TOKEN_PATTERN = re.compile(r"[А-Яа-яЁёA-Za-z]+")


def should_keep_terminal_abbreviation_dot(source_text: str, match_end: int) -> bool:
    next_index, saw_newline = first_non_whitespace_index(source_text, match_end)
    if next_index >= len(source_text):
        return True

    if saw_newline:
        return True

    next_char = source_text[next_index]
    if next_char in ".!?…" or next_char.isupper():
        return True
    if next_char in '"»”)]}':
        after_index, _ = first_non_whitespace_index(source_text, next_index + 1)
        return after_index >= len(source_text) or source_text[after_index].isupper()
    return False


def normalize_birth_year_abbreviations(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        next_index, _ = first_non_whitespace_index(text, match.end())
        keep_terminal_dot = (
            next_index >= len(text)
            or text[next_index].isupper()
            or text[next_index].isdigit()
        )
        return f"{match.group('year')} г. рождения{'.' if keep_terminal_dot else ''}"

    return BIRTH_YEAR_ABBREVIATION_PATTERN.sub(repl, text)


def normalize_mass_gram_abbreviations(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        keep_dot = bool(match.group("dot")) and should_keep_terminal_abbreviation_dot(
            text, match.end()
        )
        return f"{match.group('context')}{match.group('num')} грамм{'.' if keep_dot else ''}"

    return MASS_GRAM_ABBREVIATION_PATTERN.sub(repl, text)


#: Окно левого контекста для поиска повелительного наклонения. Инструкция
#: («Добавьте в 250 г муки…») ставит глагол в начало клаузы, поэтому дальше
#: смотреть не нужно, а фиксированное окно держит проверку линейной.
_MEASURING_INSTRUCTION_LOOKBACK = 60


def measuring_instruction_precedes(source_text: str, match_start: int) -> bool:
    """Слева в клаузе стоит глагол в повелительном наклонении.

    Это признак не словарный, а грамматический: рецепт и инструкция пишутся
    повелительным («Добавьте», «Отмерьте», «Возьмите»), а летописная запись —
    нет («Под 964 г. записано», «В 1867 г. Семёнов поместил»). Он и отличает
    массу от датировки там, где справа одинаково стоит родительный падеж.
    """
    from .text_context import normalize_context_token, simple_tokenize

    window_start = max(0, match_start - _MEASURING_INSTRUCTION_LOOKBACK)
    window = source_text[window_start:match_start]
    # Граница клаузы: глагол из предыдущего предложения этой конструкцией
    # не управляет.
    for boundary in ".!?;:":
        window = window.rpartition(boundary)[2]
    for token in simple_tokenize(window):
        word = normalize_context_token(token)
        if not word:
            continue
        if any("impr" in parse.tag for parse in parse_word(word)):
            return True
    return False


def allows_short_abbreviated_year(
    source_text: str,
    end: int,
    prep: str | None,
) -> bool:
    if prep:
        return True
    next_index, _ = first_non_whitespace_index(source_text, end)
    if next_index >= len(source_text):
        return False
    next_token_match = _SHORT_ABBREVIATED_YEAR_TOKEN_PATTERN.match(
        source_text, next_index
    )
    if next_token_match is None:
        return False
    next_token = next_token_match.group(0).lower()
    return next_token.startswith("рожд")


def has_mass_measurement_context(source_text: str, match_start: int) -> bool:
    from .text_context import normalize_context_token, simple_tokenize

    left_context = source_text[max(0, match_start - 40) : match_start]
    left_tokens = [
        normalize_context_token(token)
        for token in simple_tokenize(left_context)
        if normalize_context_token(token)
    ]
    for token in reversed(left_tokens[-3:]):
        parsed = parse_word(token)
        if not parsed:
            continue
        candidate = next(
            (item for item in parsed if "NOUN" in item.tag),
            parsed[0],
        )
        if candidate.normal_form in {"вес", "масса"}:
            return True
    return False


_ABBREVIATION_TAIL_PATTERN = re.compile(
    r"(?<![\w.])(?P<token>[A-Za-zА-Яа-яЁё]{1,10})\Z"
)
_ABBREVIATION_TAIL_MAX_LOOKBACK = 16
#: Цепочка точечных однобуквенных сокращений без пробела: «р.х.», «т.е.»,
#: «н.э.», «В.Г.». Регистр не различается: «до р.х.» — такое же сокращение, как
#: «Ю.А.». Отбитую пробелом букву («А. С.») распознаёт общий хвостовой шаблон,
#: а здесь точка перед буквой прячет её от него.
_DOTTED_LETTER_CHAIN_TAIL_PATTERN = re.compile(
    r"(?<![\w.])(?:[A-Za-zА-Яа-яЁё]\.[ \t]*)+[A-Za-zА-Яа-яЁё]\Z"
)


def _has_dictionary_continuation(token: str) -> bool:
    """Check whether the dictionary holds a longer word starting with ``token``.

    ``iterkeys`` is the only prefix lookup shared by both DAWG backends: the
    pure-Python ``dawg_python`` fallback has no ``has_keys_with_prefix``.
    """
    from ._morph import get_morph

    return next(iter(get_morph().dictionary.words.iterkeys(token)), None) is not None


_PERSON_NAME_GRAMMEMES = ("Name", "Surn", "Patr")


def _is_person_name(parse: MorphParse) -> bool:
    """Check whether a reading is a personal name, surname or patronymic."""
    return any(grammeme in parse.tag for grammeme in _PERSON_NAME_GRAMMEMES)


@functools.lru_cache(maxsize=16384)
def is_abbreviation_fragment(token: str) -> bool:
    """Check whether a short lowercase token before a dot is an abbreviation.

    A dotted single letter is an abbreviation or an initial by orthography,
    whatever its case: «Т. II», «Ю. Гагарин», «д. 5». The one-letter words that
    could stand before a real sentence end are all prepositions and
    conjunctions, which cannot end a sentence at all. «я» is the exception and
    keeps its boundary.

    Longer fragments need two disjoint signals, because pymorphy knows some
    abbreviations and guesses at the rest:

    * every reading is tagged ``Abbr`` — «стр», «руб», «ул»;
    * no dictionary reading of its own, while the dictionary does hold longer
      words that start with the token — «мкр», «пом», «примеч» are truncations
      of «микрорайон», «помещение», «примечание».

    A reading that is only a personal name does not count as a dictionary
    reading here. «генер» is known to pymorphy solely as a plural form of the
    name «генера», and a name form written in lowercase is not how a name
    appears in text — the token is a truncation of «генеральный», so the name
    readings are dropped and the continuation check decides.

    The continuation check is what keeps an unknown *whole* word out: «деплой»
    has no dictionary reading either, but nothing in the dictionary extends it,
    so it keeps its sentence boundary. A short real word that merely happens to
    end a sentence («сто», «раз», «дом») fails both signals as well.
    """

    if len(token) == 1:
        return token.lower() != "я"
    if not token.islower():
        return False
    parses = parse_word(token)
    if not parses:
        return False
    if all("Abbr" in parse.tag for parse in parses):
        return True
    known = [parse for parse in parses if getattr(parse, "is_known", False)]
    if known and not all(_is_person_name(parse) for parse in known):
        return False
    return _has_dictionary_continuation(token)


def ends_with_abbreviation(text: str, dot_index: int) -> bool:
    """Check whether the dot at ``dot_index`` closes an abbreviation or initial."""
    start = max(0, dot_index - _ABBREVIATION_TAIL_MAX_LOOKBACK)
    # Цепочку ищем только когда перед буквой стоит точка: это единственный
    # случай, который общий хвостовой шаблон пропускает, а проверка двух
    # символов дешевле сканирования на каждой границе предложения.
    if (
        dot_index >= 2
        and text[dot_index - 2] == "."
        and _DOTTED_LETTER_CHAIN_TAIL_PATTERN.search(text, start, dot_index)
    ):
        return True
    match = _ABBREVIATION_TAIL_PATTERN.search(text, start, dot_index)
    if match is None:
        return False
    return is_abbreviation_fragment(match.group("token"))


@functools.lru_cache(maxsize=4096)
def _is_plain_word(token: str) -> bool:
    """Check whether ``token`` is a full dictionary word with no abbreviation reading."""
    parses = parse_word(token)
    if not parses:
        return False
    if not any(getattr(parse, "is_known", False) for parse in parses):
        return False
    return not any("Abbr" in parse.tag for parse in parses)


def ends_with_plain_word(text: str, dot_index: int) -> bool:
    """Check whether the dot at ``dot_index`` follows an unambiguous full word.

    Deciding that a dot is stray has to be conservative: the abbreviation
    readings pymorphy offers for «пер» or «стр» are enough to leave the dot
    alone, because a wrongly kept dot only costs a redundant character while a
    wrongly dropped one destroys phrase structure.
    """
    start = max(0, dot_index - _ABBREVIATION_TAIL_MAX_LOOKBACK)
    match = _ABBREVIATION_TAIL_PATTERN.search(text, start, dot_index)
    if match is None:
        return False
    return _is_plain_word(match.group("token").lower())
