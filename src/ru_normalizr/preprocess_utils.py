from __future__ import annotations

import re

import num2words

from ._morph import word_is_known
from .abbreviation_context import (
    ends_with_plain_word,
    normalize_birth_year_abbreviations,
    normalize_mass_gram_abbreviations,
)
from .constants import CLEANUP_REPLACEMENTS, UNICODE_FRACTIONS
from .ordinal_utils import render_ordinal

# Метки препроцессинга объявлены в реестре заменителей: там же лежат диапазоны
# остальных клиентов, поэтому пересечение видно на глаз и проверяется тестом.
from .placeholders import (
    BINARY_MINUS_PLACEHOLDER,
    BINARY_PLUS_PLACEHOLDER,
    BINARY_POWER_PLACEHOLDER,
    LETTER_HYPHEN_PLACEHOLDER,
    NEGATIVE_NUMBER_PLACEHOLDER,
    UNIT_SLASH_PLACEHOLDER,
)
from .text_scan import compile_scan, first_non_whitespace_index

ASCII_DASH_SPACE_PATTERN = compile_scan(r" - ")
DOT_COMMA_PATTERN = compile_scan(r"\.,")
LETTER_HYPHEN_PATTERN = compile_scan(r"(?<=[A-Za-zА-Яа-яЁё])-(?=[A-Za-zА-Яа-яЁё])")
SLASH_FIX_PATTERN = compile_scan(r"(?<=[a-zA-Zа-яА-ЯёЁ+])/(?=[a-zA-Zа-яА-ЯёЁ+])")
UNIT_SLASH_PATTERN = compile_scan(
    r"(?<![\w/])(?P<left>[A-Za-zА-Яа-яЁёµμ]+(?:\^?[23]|[²³])?)/"
    r"(?P<right>[A-Za-zА-Яа-яЁёµμ]+(?:\^?[23]|[²³])?)(?![\w/])"
)
NUMBER_CLEANUP_PATTERN = compile_scan(
    r"(?<!\d)(?:\d{1,3}(?:[ \u00A0\u2009\u202F]\d{3})+|\d+)(?:[,\.]\d+)?(?!\d)"
)
BRACKETED_NUMERIC_PATTERN = compile_scan(r"([\[<({«])\s*([^()\[\]{}<>«»]+?)\s*([\]>)}»])")
SPACE_BEFORE_PUNCT_PATTERN = compile_scan(r"[ \t]+([,.;:!?])")
DOUBLE_DOT_TYPO_PATTERN = compile_scan(r"(?<!\.)\.\.(?!\.)")
DOT_SPACE_DOT_TYPO_PATTERN = compile_scan(r"(?<!\.)\.[ \t]+\.(?!\.)")
COMMA_DOT_TYPO_PATTERN = compile_scan(r",\.")
# A glued bracket with a bare number inside is a footnote reference and keeps
# its shape for the footnote-removal stage; anything else is a typo.
MISSING_SPACE_BEFORE_PAREN_PATTERN = compile_scan(
    r"(?<=[А-Яа-яЁё])\((?!\d+(?:[-–—]\d+)?\))"
)
MULTI_SPACE_PATTERN = compile_scan(r"[ \t]{2,}")
SPACE_BEFORE_CLOSE_BRACKET_PATTERN = compile_scan(r"[ \t]+([\)\]\}])")
SPACE_AFTER_OPEN_BRACKET_PATTERN = compile_scan(r"([\(\[\{])[ \t]+")
TRAILING_SPACE_BEFORE_NEWLINE_PATTERN = compile_scan(r"[ \t]+\n")
LEADING_SPACE_AFTER_NEWLINE_PATTERN = compile_scan(r"\n[ \t]+")
EXCESSIVE_LINEBREAKS_PATTERN = compile_scan(r"\n{2,}")
DECORATIVE_SEPARATOR_PATTERN = compile_scan(
    r"(?:(?<=^)|(?<=\n))[ \t]*(?:[*=_~+#\-\xad\u2010-\u2015][ \t]*){3,}(?:(?=$)|(?=\n))"
)
LEGACY_PARAGRAPH_BREAK_DOT_PATTERN = compile_scan(
    r"(?P<prev>[^\n.!?…,:;–\-\"'])(?P<break>\n{2,})(?=(?:[\"«„“]\s*)?[А-ЯЁA-Z0-9])"
)
LEGACY_LINEBREAK_DOT_PATTERN = compile_scan(
    r"(?P<prev>[^\n.!?…,:;–\-\"'])(?P<break>\n)(?=(?:[\"«„“]\s*)?[А-ЯЁA-Z0-9])"
)
INLINE_LINEBREAK_SPACE_PATTERN = compile_scan(
    r"(?<=[^\n])\n(?!(?:[\"«„“]\s*)?[А-ЯЁA-Z0-9])(?=[^\n])"
)
BINARY_MATH_OPERATOR_PATTERN = compile_scan(r"(?<=\d)[+−^](?=\d)")
BINARY_MATH_OPERATOR_PLACEHOLDERS = {
    "+": BINARY_PLUS_PLACEHOLDER,
    "−": BINARY_MINUS_PLACEHOLDER,
    "^": BINARY_POWER_PLACEHOLDER,
}
BINARY_MATH_OPERATOR_TRANSLATION = str.maketrans(
    {
        BINARY_PLUS_PLACEHOLDER: "+",
        BINARY_MINUS_PLACEHOLDER: "−",
        BINARY_POWER_PLACEHOLDER: "^",
    }
)
EXPLICIT_DASH_TRANSLATION = str.maketrans({"–": "—", "―": "—"})


def protect_unit_slashes(text: str) -> str:
    # Lazy import avoids a preprocess -> numerals -> preprocess import cycle.
    from .numerals.unit_expressions import resolve_unit_expression

    def repl(match: re.Match[str]) -> str:
        if resolve_unit_expression(match.group(0)) is None:
            return match.group(0)
        return (
            f"{match.group('left')}{UNIT_SLASH_PLACEHOLDER}{match.group('right')}"
        )

    return UNIT_SLASH_PATTERN.sub(repl, text)


def protect_binary_math_operators(text: str) -> str:
    return BINARY_MATH_OPERATOR_PATTERN.sub(
        lambda match: BINARY_MATH_OPERATOR_PLACEHOLDERS[match.group(0)], text
    )


def restore_binary_math_operators(text: str) -> str:
    if not any(
        placeholder in text for placeholder in BINARY_MATH_OPERATOR_PLACEHOLDERS.values()
    ):
        return text
    return text.translate(BINARY_MATH_OPERATOR_TRANSLATION)
# Дореформенное раздельное «на прим.» — это «например»; но «на прим. 5» —
# ссылка на примечание, а «на прим. пер./ред./авт.» — на редакторскую сноску.
# Правило живёт в препроцессинге: на этом этапе цифры ещё не развёрнуты в
# слова, поэтому граница «не перед цифрой» работает. Левая граница слова —
# лукбехайндом после первого символа, а не стартовой ассерцией: так движок re
# сохраняет быстрый пропуск по классу [Нн] (см. NEW_STYLE_DATE_PATTERN).
NA_PRIM_ABBREVIATION_PATTERN = compile_scan(
    r"([Нн]а)(?<!\w[Нн]а)\s+прим\.(?!\s*(?:\d|пер(?:ев)?\.|ред\.|авт\.|перевод|редактор|автор))(?!\w)"
)
# «20 н.с.» после числа дня — дата «нового стиля», а не ньютон-секунды:
# ньютон-секунды в прозе пишутся «Н·с», а день ограничен диапазоном 1–31
# (проверка диапазона — в заменителе). Наращение «-го» отдаёт число стадии
# числительных как порядковое. Класс цифр стоит первым, а левая граница —
# лукбехайндом после него: со стартовой ассерции движок re теряет быстрый
# пропуск по первому символу и проходит весь документ в 4 раза медленнее.
NEW_STYLE_DATE_PATTERN = compile_scan(
    r"(?P<day>[1-9](?<![\w.,][1-9])\d?)\s+н\.\s*с\.(?!\w)"
)
YEARS_AGO_ABBREVIATION_PATTERN = compile_scan(
    r"(?P<quantity>(?<!\w)(?:\d+(?:[.,]\d+)?|тыс(?:\.|яч[а-яё]*)?|млн\.?|"
    r"миллион[а-яё]*|млрд\.?|миллиард[а-яё]*|несколько|много)\s+)"
    r"л\.?\s*н\.(?P<tail>\s*)",
    re.UNICODE,
)
UNARY_MINUS_NUMBER_PATTERN = compile_scan(
    r"(?P<prefix>^|[(\[{«]|(?<!\d)\s)(?P<sign>[−-])(?P<space>\s*)(?P<number>\d+(?:[.,]\d+)?)"
)
UNARY_PLUS_NUMBER_PATTERN = compile_scan(
    r"(?P<prefix>^|[(\[{«=,:;]|(?<![\d\s])\s)\+(?P<number>\d+(?:[.,]\d+)?)"
)
THOUSANDS_SEPARATORS = " \u00a0\u2009\u202f"
SIGNED_COMMA_NUMBER_PATTERN = compile_scan(
    r"^[−-]?(?:\d{1,3}(?:[" + THOUSANDS_SEPARATORS + r"]\d{3})+|\d+),\d+$"
)
SIGNED_INTEGER_WITH_UNIT_PATTERN = compile_scan(
    r"^[−-]?(?:\d{1,3}(?:[" + THOUSANDS_SEPARATORS + r"]\d{3})+|\d+)(?:,\d+)?\s*"
    r"(?:[%‰°]|[₽$€£¥]|[A-Za-zА-Яа-яЁё]+(?:\s+[A-Za-zА-Яа-яЁё.]+)?)$"
)
INTEGER_LIST_PATTERN = compile_scan(r"^\d+(?:\s*,\s*\d+)+$")
INTEGER_RANGE_PATTERN = compile_scan(r"^\d+\s*[–—-]\s*\d+$")
SPACE_INSIDE_QUOTES_PATTERN = compile_scan(
    r'(^|[\s([{\-–—,;:])"\s+([^\n"]+?)\s+"(?=$|[\s)\]}\-–—,.;:!?])'
)
SPACE_AFTER_OPEN_QUOTE_PATTERN = compile_scan(
    r'(^|[\s([{\-–—,;:])"([ \t]+)(?=\S)'
)
SPACE_BEFORE_CLOSE_QUOTE_PATTERN = compile_scan(
    r'(?<=\S)([ \t]+)"(?=$|[\s)\]}\-–—,.;:!?])'
)
OPEN_SINGLE_QUOTE_PATTERN = compile_scan(
    r"(?P<prefix>^|[\s([{\-–—,;:])(?P<quote>[‘‚‛‹])(?=\S)"
)
CLOSE_SINGLE_QUOTE_PATTERN = compile_scan(
    r"(?<=\S)(?P<quote>[’›])(?=$|[\s)\]}\-–—,.;:!?])"
)
ELLIPSIS_SPACE_BEFORE_PATTERN = compile_scan(r"[ \t]+(?=…)")
ELLIPSIS_SPACE_AFTER_PATTERN = compile_scan(r"(?<=…)(?=[^\s.,;:!?…)\]}\"])\S")
# A run such as "С.Ш.А." is a dotted acronym, not three sentence ends. The
# fixed-width negative lookbehind keeps the spacing pass linear.
SENTENCE_SPACE_AFTER_PATTERN = compile_scan(
    r'(?<=[.!?…])(?<![A-ZА-ЯЁ]\.)'
    r'(?=["(«„“]?[A-ZА-ЯЁ])'
)
CYRILLIC_COMBINING_STRESS_PATTERN = compile_scan(
    r"([АЕЁИОУЫЭЮЯаеёиоуыэюя])([\u0300\u0301])"
)
ZERO_WIDTH_FORMATTING_PATTERN = compile_scan(r"[\u200B\u200C\u200D\u2060\uFEFF]")
LINEBREAK_RUN_PATTERN = compile_scan(r"\n(?:[ \t]*\n)*[ \t]*")
LEGACY_LINE_START_PATTERN = compile_scan(r'(?:["«„“]\s*)?[А-ЯЁA-Z0-9]')
QUOTE_PAIR_REPLACEMENTS = (("``", '"'), ("''", '"'), ("‘‘", '"'), ("’’", '"'), ("´´", '"'))
QUOTE_SHAPE_PATTERN = compile_scan(
    r"``|''|‘‘|’’|´´|[«»“”„‟〝〞＂]|"
    r"(?<![A-Za-zА-Яа-яЁё])[‘‚‛‹]|[’›](?![A-Za-zА-Яа-яЁё])"
)
QUOTE_VARIANT_PATTERN = compile_scan(r"[«»“”„‟〝〞＂]")
QUOTE_CANDIDATES = frozenset('"\'`´«»‘’‚‛‹›“”„‟〝〞＂')
PAGE_ABBREVIATION_PATTERN = compile_scan(r"\b[сp]\.\s*(?=\d)", re.IGNORECASE)
PAGE_FULL_ABBREVIATION_PATTERN = compile_scan(r"\bстр\.\s*(?=\d)", re.IGNORECASE)
PAGE_REFERENCE_PATTERN = compile_scan(
    r"\b(?:стр\.|с\.)\s*(?:(?P<left>\d+)\s*[–—-]\s*(?P<right>\d+)|(?P<number>\d+))",
    re.IGNORECASE,
)
ARTICLE_ABBREVIATION_PATTERN = compile_scan(r"\bст\.\s*(?=\d)", re.IGNORECASE)
FIGURE_ABBREVIATION_PATTERN = compile_scan(r"\bрис\.\s*(?=\d)", re.IGNORECASE)
TABLE_ABBREVIATION_PATTERN = compile_scan(r"\bтабл\.\s*(?=\d)", re.IGNORECASE)
REFERENCE_DIRECTIVE_PATTERN = compile_scan(
    r"\bсм\.(?P<body>\s*(?:рис\.|табл\.|стр\.)\s*\d+"
    r"(?:\s*(?:,|и)\s*(?:рис\.|табл\.|стр\.)\s*\d+)*)",
    re.IGNORECASE,
)
APPROXIMATE_ABBREVIATION_PATTERN = compile_scan(r"\bок\.\s*(?=\d)", re.IGNORECASE)
BIBLIOGRAPHIC_NUMBER_ABBREVIATIONS = (
    (compile_scan(r"(?<!\w)Т\.\s*(?=\d)"), "том "),
    (compile_scan(r"(?<!\w)Vol\.\s*(?=\d)", re.IGNORECASE), "том "),
    (compile_scan(r"(?<!\w)No\.\s*(?=\d)", re.IGNORECASE), "номер "),
)
LEGAL_ARTICLE_REFERENCE_PATTERN = compile_scan(
    r"\b(?:ст\.|статья)\s*(?P<number>\d+)\s+(?P<code>УК|АК)\s+РФ\b",
    re.IGNORECASE,
)
LEGAL_COMPLEX_REFERENCE_PATTERN = compile_scan(
    r"(?<!\w)п\.\s*(?P<point>\d+)\s+ст\.\s*(?P<article>\d+)\s+"
    r"ФЗ\s+№\s*(?P<code>\d+)(?!\w)",
    re.IGNORECASE,
)
ADMINISTRATIVE_LAW_REFERENCE_PATTERN = compile_scan(
    r"(?<!\w)(?:(?P<prep>в|во|о|об|согласно)\s+)?ч\.\s*(?P<part>\d+)\s+ст\.\s*"
    r"(?P<article>\d+(?:\.\d+)?)\s+КоАП\s+РФ(?!\w)",
    re.IGNORECASE,
)
SECTION_REFERENCE_PATTERN = compile_scan(
    r"(?<!\w)§\s*(?P<first>\d+(?:\.\d+)+)"
    r"(?:\s+и\s+§\s*(?P<second>\d+(?:\.\d+)+))?"
)
AGE_RANGE_PATTERN = compile_scan(
    r"(?<!\w)(?P<left>\d+)\s*[—–-]\s*(?P<right>\d+)\s+"
    r"(?P<unit>лет|года|год)(?!\w)",
    re.IGNORECASE,
)
ISBN_PATTERN = compile_scan(
    r"(?<!\w)(?P<prefix>ISBN)\s+(?P<groups>\d+(?:[-–—]\d+){3,4})(?!\w)",
    re.IGNORECASE,
)
LEGAL_CODE_GENITIVE_EXPANSIONS = {
    "ук": "уголовного кодекса российской федерации",
    "ак": "арбитражного кодекса российской федерации",
}
ERA_ABBREVIATION_PATTERN = compile_scan(
    r"(?<!\w)(?P<abbr>до\s+н\.?\s*э\.?|н\.?\s*э\.?)(?P<tail>\s*)",
    re.IGNORECASE,
)
def normalize_ascii_quote_pairs(text: str) -> str:
    if QUOTE_CANDIDATES.isdisjoint(text):
        return text
    if QUOTE_SHAPE_PATTERN.search(text) is None:
        text = SPACE_INSIDE_QUOTES_PATTERN.sub(r'\1"\2"', text)
        text = SPACE_AFTER_OPEN_QUOTE_PATTERN.sub(r'\1"', text)
        return SPACE_BEFORE_CLOSE_QUOTE_PATTERN.sub('"', text)
    for old, new in QUOTE_PAIR_REPLACEMENTS:
        text = text.replace(old, new)
    text = QUOTE_VARIANT_PATTERN.sub('"', text)
    text = OPEN_SINGLE_QUOTE_PATTERN.sub(r'\g<prefix>"', text)
    text = CLOSE_SINGLE_QUOTE_PATTERN.sub('"', text)
    text = SPACE_INSIDE_QUOTES_PATTERN.sub(r'\1"\2"', text)
    text = SPACE_AFTER_OPEN_QUOTE_PATTERN.sub(r'\1"', text)
    return SPACE_BEFORE_CLOSE_QUOTE_PATTERN.sub('"', text)


def normalize_punctuation_spacing(text: str) -> str:
    text = ELLIPSIS_SPACE_BEFORE_PATTERN.sub("", text)
    text = ELLIPSIS_SPACE_AFTER_PATTERN.sub(lambda m: f" {m.group(0)}", text)
    text = SENTENCE_SPACE_AFTER_PATTERN.sub(" ", text)
    # Replacements spliced into the text may leave a doubled space behind a
    # removed symbol or a padded operator, and a stray space in front of a
    # closing punctuation mark; TTS output never needs either.
    # A doubled dot is a typo for a sentence end (an ellipsis keeps its three
    # dots), and «,.» keeps only the stronger sentence mark. The spaced
    # variant «. .» collapses first, before the space-stripping below would
    # glue it into «..» and lose the sentence boundary.
    text = DOT_SPACE_DOT_TYPO_PATTERN.sub(". ", text)
    text = SPACE_BEFORE_PUNCT_PATTERN.sub(r"\1", text)
    text = DOUBLE_DOT_TYPO_PATTERN.sub(".", text)
    text = COMMA_DOT_TYPO_PATTERN.sub(".", text)
    return MULTI_SPACE_PATTERN.sub(" ", text)


def cleanup_malformed_punctuation(text: str) -> str:
    """Drop a stray dot that a full word carries in front of a comma.

    «Фраза., затем» is a typo; «Мыльников пер., рядом» is not. Collapsing the
    abbreviation dot together with the comma would delete the clause boundary
    and a TTS engine would run both halves of the sentence together, so the
    dot is only removed when the word in front of it is unambiguously whole.
    """

    def repl(match: re.Match[str]) -> str:
        if ends_with_plain_word(text, match.start()):
            return "."
        return match.group(0)

    return DOT_COMMA_PATTERN.sub(repl, text)


#: Latin letters drawn with the same glyph as a Cyrillic one. Only these can be
#: a layout slip inside a Russian word; «l», «d» or «v» have no Cyrillic twin and
#: mark a genuinely Latin token.
_LATIN_TO_CYRILLIC_HOMOGLYPHS = str.maketrans(
    {
        "A": "А",
        "B": "В",
        "C": "С",
        "E": "Е",
        "H": "Н",
        "K": "К",
        "M": "М",
        "O": "О",
        "P": "Р",
        "T": "Т",
        "X": "Х",
        "Y": "У",
        "a": "а",
        "c": "с",
        "e": "е",
        "o": "о",
        "p": "р",
        "x": "х",
        "y": "у",
    }
)
_HOMOGLYPH_LATIN_LETTERS = frozenset("ABCEHKMOPTXYacepoxy")
_HOMOGLYPH_LATIN_PATTERN = compile_scan(f"[{''.join(sorted(_HOMOGLYPH_LATIN_LETTERS))}]")
#: A word that mixes both scripts. Both lookaheads are required so the C-level
#: scan rejects ordinary words without entering the Python callback: a full pass
#: over every word of a book-sized text is otherwise the most expensive step of
#: the preprocessing stage.
_WORD_CHARS = "A-Za-zА-Яа-яЁё+"
MIXED_SCRIPT_WORD_PATTERN = compile_scan(
    rf"(?<![{_WORD_CHARS}])"
    rf"(?=[{_WORD_CHARS}]*[ABCEHKMOPTXYacepoxy])"
    rf"(?=[{_WORD_CHARS}]*[А-Яа-яЁё])"
    rf"[{_WORD_CHARS}]{{2,}}"
)


def normalize_script_homoglyphs(text: str) -> str:
    """Repair a Latin homoglyph typed inside a Russian word.

    «Bсе» is «Все» with a Latin B — a typesetting defect, not a Latin token, and
    reading it as a letter name gave «бисе». The repair only applies when every
    Latin letter of the word has a Cyrillic twin and the substituted word is in
    the dictionary, so a genuinely mixed identifier is left alone.
    """
    if _HOMOGLYPH_LATIN_PATTERN.search(text) is None:
        return text

    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        latin = [char for char in word if char.isascii() and char.isalpha()]
        if not latin or any(char not in _HOMOGLYPH_LATIN_LETTERS for char in latin):
            return word
        if not any(not char.isascii() and char.isalpha() for char in word):
            return word
        candidate = word.translate(_LATIN_TO_CYRILLIC_HOMOGLYPHS)
        if not word_is_known(candidate.replace("+", "")):
            return word
        return candidate

    return MIXED_SCRIPT_WORD_PATTERN.sub(repl, text)


def normalize_cyrillic_combining_stress_marks(text: str) -> str:
    return CYRILLIC_COMBINING_STRESS_PATTERN.sub(r"+\1", text)


def remove_zero_width_formatting(text: str) -> str:
    return ZERO_WIDTH_FORMATTING_PATTERN.sub("", text)


def normalize_era_abbreviations(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        abbr = match.group("abbr")
        tail = match.group("tail")
        expansion = "до нашей эры" if abbr.lower().startswith("до") else "нашей эры"
        next_index, _ = first_non_whitespace_index(text, match.end())
        keep_terminal_dot = False
        if abbr.rstrip().endswith("."):
            keep_terminal_dot = (
                next_index >= len(text)
                or "\n" in tail
                or (next_index < len(text) and text[next_index].isupper())
            )
            if (
                next_index < len(text)
                and text[next_index] in '"»”)]}'
                and next_index + 1 < len(text)
                and text[next_index + 1].isupper()
            ):
                keep_terminal_dot = True
        return f"{expansion}{'.' if keep_terminal_dot else ''}{tail}"

    return ERA_ABBREVIATION_PATTERN.sub(repl, text)


def normalize_numeric_abbreviations(text: str) -> str:
    def reference_directive_repl(match: re.Match[str]) -> str:
        noun_forms = {
            "рис.": "рисунок",
            "табл.": "таблицу",
            "стр.": "страницу",
        }
        body = re.sub(
            r"\b(?:рис\.|табл\.|стр\.)",
            lambda noun_match: noun_forms[noun_match.group(0).lower()],
            match.group("body"),
            flags=re.IGNORECASE,
        )
        return f"см.{body}"

    def legal_article_repl(match: re.Match[str]) -> str:
        expansion = LEGAL_CODE_GENITIVE_EXPANSIONS[match.group("code").lower()]
        return f"статья {match.group('number')} {expansion}"

    text = normalize_birth_year_abbreviations(text)
    text = normalize_mass_gram_abbreviations(text)
    text = REFERENCE_DIRECTIVE_PATTERN.sub(reference_directive_repl, text)
    text = PAGE_ABBREVIATION_PATTERN.sub("страница ", text)
    text = PAGE_FULL_ABBREVIATION_PATTERN.sub("страница ", text)
    text = ARTICLE_ABBREVIATION_PATTERN.sub("статья ", text)
    text = FIGURE_ABBREVIATION_PATTERN.sub("рисунок ", text)
    text = TABLE_ABBREVIATION_PATTERN.sub("таблица ", text)
    text = APPROXIMATE_ABBREVIATION_PATTERN.sub("около ", text)
    for pattern, replacement in BIBLIOGRAPHIC_NUMBER_ABBREVIATIONS:
        text = pattern.sub(replacement, text)
    text = LEGAL_ARTICLE_REFERENCE_PATTERN.sub(legal_article_repl, text)
    return normalize_era_abbreviations(text)


def normalize_page_references(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 24) : match.start()]
        preceding = re.search(
            r"(?:^|\s)(?P<word>на|в|во|см\.|смотри)\s*$",
            left_context,
            re.IGNORECASE,
        )
        if preceding is None:
            return match.group(0)
        directive = preceding.group("word").casefold().rstrip(".")
        if match.group("left") is not None:
            left = render_ordinal(
                int(match.group("left")), case="gent", gender="femn", inanimate=True
            )
            right = render_ordinal(
                int(match.group("right")), case="accs", gender="femn", inanimate=True
            )
            return f"страницах с {left} по {right}"
        case = "accs" if directive in {"см", "смотри"} else "loct"
        noun = "страницу" if case == "accs" else "странице"
        number = render_ordinal(
            int(match.group("number")), case=case, gender="femn", inanimate=True
        )
        return f"{noun} {number}"

    return PAGE_REFERENCE_PATTERN.sub(repl, text)


def normalize_complex_legal_references(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 32) : match.start()]
        prep_match = re.search(
            r"(?:^|\s)(?P<word>согласно|в|во|о|об|по|к|ко|из|с|со|до|от)\s*$",
            left_context,
            re.IGNORECASE,
        )
        prep = prep_match.group("word").casefold() if prep_match else ""
        if prep in {"согласно", "по", "к", "ко"}:
            point_case = "datv"
            point_word = "пункту"
        elif prep in {"в", "во", "о", "об"}:
            point_case = "loct"
            point_word = "пункте"
        elif prep in {"из", "с", "со", "до", "от"}:
            point_case = "gent"
            point_word = "пункта"
        else:
            point_case = "nomn"
            point_word = "пункт"
        point = render_ordinal(
            int(match.group("point")),
            case=point_case,
            gender="masc",
            inanimate=True,
        )
        article = render_ordinal(
            int(match.group("article")),
            case="gent",
            gender="femn",
            inanimate=True,
        )
        return (
            f"{point_word} {point} статьи {article} федерального закона "
            f"номер {match.group('code')}"
        )

    return LEGAL_COMPLEX_REFERENCE_PATTERN.sub(repl, text)


def normalize_administrative_law_references(text: str) -> str:
    def render_hierarchical_number(raw: str) -> str | None:
        words: list[str] = []
        for part in raw.split("."):
            try:
                words.append(num2words.num2words(int(part), lang="ru"))
            except (TypeError, ValueError):
                return None
        return " точка ".join(words)

    def repl(match: re.Match[str]) -> str:
        prep = match.group("prep")
        governed_part = prep is not None
        try:
            part = render_ordinal(
                int(match.group("part")),
                case="gent" if governed_part else "ablt",
                gender="femn",
                inanimate=True,
            )
        except (TypeError, ValueError):
            return match.group(0)
        article = render_hierarchical_number(match.group("article"))
        if article is None:
            return match.group(0)
        part_word = "части" if governed_part else "частью"
        prefix = f"{prep} " if prep else ""
        return (
            f"{prefix}{part_word} {part} статьи {article} Кодекса Российской Федерации "
            "об административных правонарушениях"
        )

    return ADMINISTRATIVE_LAW_REFERENCE_PATTERN.sub(repl, text)


def normalize_section_references(text: str) -> str:
    def render_hierarchical_number(raw: str) -> str | None:
        words: list[str] = []
        for part in raw.split("."):
            try:
                words.append(num2words.num2words(int(part), lang="ru"))
            except (TypeError, ValueError):
                return None
        return " точка ".join(words)

    def repl(match: re.Match[str]) -> str:
        first = render_hierarchical_number(match.group("first"))
        second_raw = match.group("second")
        second = render_hierarchical_number(second_raw) if second_raw else None
        if first is None or (second_raw is not None and second is None):
            return match.group(0)
        left_context = text[max(0, match.start() - 24) : match.start()]
        noun = "параграфах" if re.search(r"\bв\s*$", left_context) else "параграф"
        return f"{noun} {first}" + (f" и {second}" if second else "")

    return SECTION_REFERENCE_PATTERN.sub(repl, text)


def normalize_age_ranges(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        left_context = text[max(0, match.start() - 64) : match.start()]
        # Only a group of people named before the range makes "6–12 лет" an age
        # span that has to be read as "от … до …". After "возраст" the numbers
        # are the value of that attribute and stay a plain range ("возраст
        # десять — двадцать лет"), which is also how every other range in the
        # text is read.
        if not re.search(r"\bдет(?:и|ей|ям|ях)\b", left_context, re.IGNORECASE):
            return match.group(0)
        return (
            f"от {match.group('left')} до {match.group('right')} "
            f"{match.group('unit')}"
        )

    return AGE_RANGE_PATTERN.sub(repl, text)


def normalize_isbn_identifiers(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        groups = re.split(r"[-–—]", match.group("groups"))
        if len(groups) not in {4, 5}:
            return match.group(0)
        try:
            rendered = [num2words.num2words(int(group), lang="ru") for group in groups]
        except (TypeError, ValueError):
            return match.group(0)
        return f"{match.group('prefix')} {' — '.join(rendered)}"

    return ISBN_PATTERN.sub(repl, text)


def normalize_explicit_dashes(text: str) -> str:
    if "–" not in text and "―" not in text:
        return text
    return text.translate(EXPLICIT_DASH_TRANSLATION)


def normalize_spaced_ascii_hyphens(text: str) -> str:
    return ASCII_DASH_SPACE_PATTERN.sub(" — ", text)


def protect_negative_numbers(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        number = match.group("number")
        return f"{prefix}{NEGATIVE_NUMBER_PLACEHOLDER}{number}"

    return UNARY_MINUS_NUMBER_PATTERN.sub(repl, text)


def normalize_unary_plus_numbers(text: str) -> str:
    """Read a plus glued to a number as a unary positive sign."""

    return UNARY_PLUS_NUMBER_PATTERN.sub(
        lambda match: f"{match.group('prefix')}плюс {match.group('number')}", text
    )


def protect_letter_hyphens(text: str) -> str:
    return LETTER_HYPHEN_PATTERN.sub(LETTER_HYPHEN_PLACEHOLDER, text)


def restore_letter_hyphens(text: str) -> str:
    return text.replace(LETTER_HYPHEN_PLACEHOLDER, "-")


def expand_new_style_date_abbreviation(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        day = match.group("day")
        if int(day) > 31:
            # «45 н. с.» — не дата: дней больше 31 не бывает.
            return match.group(0)
        return f"{day}-го нового стиля"

    return NEW_STYLE_DATE_PATTERN.sub(repl, text)


def expand_na_prim_abbreviation(text: str) -> str:
    # «на» + «пример» склеиваются в «например» с сохранением заглавной буквы.
    return NA_PRIM_ABBREVIATION_PATTERN.sub(lambda m: m.group(1) + "пример", text)


def expand_years_ago_abbreviation(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        quantity = match.group("quantity")
        tail = match.group("tail")
        next_char_index = match.end()
        next_char = text[next_char_index] if next_char_index < len(text) else ""
        if not next_char or next_char == "\n" or next_char.isalnum():
            return f"{quantity}лет назад.{tail}"
        return f"{quantity}лет назад{tail}"

    return YEARS_AGO_ABBREVIATION_PATTERN.sub(repl, text)


def normalize_unicode_fractions(text: str) -> str:
    for char, replacement in UNICODE_FRACTIONS.items():
        text = text.replace(char, replacement)
    return text


def apply_cleanup_replacements(text: str) -> str:
    for old, new in CLEANUP_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def _insert_boundary_dot(match: re.Match[str]) -> str:
    return f"{match.group('prev')}.{match.group('break')}"


def normalize_linebreaks(text: str) -> str:
    if "\n" not in text and "\r" not in text:
        return text

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = TRAILING_SPACE_BEFORE_NEWLINE_PATTERN.sub("\n", text)

    def normalize_run(match: re.Match[str]) -> str:
        raw = match.group(0)
        break_count = raw.count("\n")
        linebreak = "\n\n" if break_count >= 2 else "\n"
        previous = text[match.start() - 1] if match.start() else ""
        has_tail = match.end() < len(text)
        next_is_legacy_start = bool(LEGACY_LINE_START_PATTERN.match(text, match.end()))
        if (
            previous
            and previous not in '\n.!?…,:;–-"\''
            and next_is_legacy_start
        ):
            return f".{linebreak}"
        if break_count == 1 and previous and has_tail and not next_is_legacy_start:
            return " "
        return linebreak

    return LINEBREAK_RUN_PATTERN.sub(normalize_run, text)


def remove_decorative_separators(text: str) -> str:
    return DECORATIVE_SEPARATOR_PATTERN.sub("", text)


def classify_bracketed_numeric_content(content: str) -> str:
    stripped = content.strip()
    if not stripped:
        return "other"

    if SIGNED_COMMA_NUMBER_PATTERN.fullmatch(stripped):
        return "numeric"

    if SIGNED_INTEGER_WITH_UNIT_PATTERN.fullmatch(stripped):
        return "numeric"

    if stripped.isdigit():
        return "reference"

    if INTEGER_RANGE_PATTERN.fullmatch(stripped):
        return "reference"

    if INTEGER_LIST_PATTERN.fullmatch(stripped):
        if stripped.count(",") == 1 and ", " not in stripped and " ," not in stripped:
            return "numeric"
        return "reference"

    if "." in stripped:
        parts = stripped.split(".")
        if all(part.isdigit() for part in parts):
            if len(parts) >= 3:
                return "reference"
            if len(parts) == 2:
                left, right = parts
                if len(left) <= 2 and len(right) <= 3:
                    return "reference"
                return "numeric"

    return "other"


def remove_numeric_footnotes(
    text: str,
    ignore_interval: tuple[int, int] | None = None,
) -> str:
    pairs = {"[": "]", "<": ">", "(": ")", "{": "}", "«": "»"}

    def repl(match: re.Match[str]) -> str:
        opener, content, closer = match.group(1), match.group(2), match.group(3)
        if pairs.get(opener) != closer:
            return match.group(0)
        stripped = content.strip()
        if classify_bracketed_numeric_content(content) == "reference":
            if ignore_interval is not None and stripped.isdigit():
                value = int(stripped)
                min_val, max_val = ignore_interval
                if min_val <= value <= max_val:
                    return match.group(0)
            return ""
        return match.group(0)

    text = BRACKETED_NUMERIC_PATTERN.sub(repl, text)
    text = SPACE_BEFORE_PUNCT_PATTERN.sub(r"\1", text)
    text = MULTI_SPACE_PATTERN.sub(" ", text)
    text = SPACE_BEFORE_CLOSE_BRACKET_PATTERN.sub(r"\1", text)
    text = SPACE_AFTER_OPEN_BRACKET_PATTERN.sub(r"\1", text)
    return normalize_linebreaks(text).strip()


def clean_numbers(text: str) -> str:
    def repl_spaces(match: re.Match[str]) -> str:
        return (
            match.group(0)
            .replace(" ", "")
            .replace("\u00a0", "")
            .replace("\u2009", "")
            .replace("\u202f", "")
        )

    text = NUMBER_CLEANUP_PATTERN.sub(repl_spaces, text)
    text = re.sub(
        r"(?<!\d)(\d{1,3}(?:\.\d{3}){2,})(?!\d)",
        lambda m: m.group(1).replace(".", ""),
        text,
    )
    text = re.sub(
        r"(?<!\d)(\d{1,3}\.\d{3})(?=,\d+)", lambda m: m.group(1).replace(".", ""), text
    )
    unit_lookahead = (
        r"(?=\s*(?:[₽$€£¥%‰]|\b(?:руб|долл|евро|тыс|млн|млрд|г|кг|т|м|км|шт)\b))"
    )
    return re.sub(
        r"(?<!\d)(\d{1,3}\.\d{3})" + unit_lookahead,
        lambda m: m.group(1).replace(".", ""),
        text,
    )
