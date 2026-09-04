from __future__ import annotations

import re

from ._morph import word_is_known
from .abbreviation_context import (
    ends_with_plain_word,
    normalize_birth_year_abbreviations,
    normalize_mass_gram_abbreviations,
)
from .constants import CLEANUP_REPLACEMENTS, UNICODE_FRACTIONS

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
# «!..» и «?..» — законные формы многоточия после знака, а не опечатка.
DOUBLE_DOT_TYPO_PATTERN = compile_scan(r"(?<![.!?…])\.\.(?!\.)")
DOT_SPACE_DOT_TYPO_PATTERN = compile_scan(r"(?<!\.)\.[ \t]+\.(?!\.)")
COMMA_DOT_TYPO_PATTERN = compile_scan(r",\.")
# A glued bracket with a bare number inside is a footnote reference and keeps
# its shape for the footnote-removal stage; anything else is a typo.
MISSING_SPACE_BEFORE_PAREN_PATTERN = compile_scan(
    r"(?<=[А-Яа-яЁёѢѣІіѲѳѴѵ])\((?!\d+(?:[-–—]\d+)?\))"
)
#: Буквенный уточнитель марки, приклеенный к числу: «Pz.38(t)», «Sd.Kfz.251(D)».
#: Ограничение в три буквы держит правило на суффиксах кода и не задевает ни
#: сносок с числом внутри, ни арифметики со скобкой.
MISSING_SPACE_BEFORE_LETTER_PAREN_AFTER_DIGIT_PATTERN = compile_scan(
    r"(?<=\d)\((?=[A-Za-zА-Яа-яЁё]{1,3}\))"
)
#: Перенос слова по строке: дефис в конце строки склеивает части одного слова.
#: Продолжение переноса всегда строчное, поэтому заглавная справа исключается —
#: это разорванное составное имя («Санктъ-\nПетербургъ»), а не перенос.
WRAPPED_WORD_HYPHEN_PATTERN = compile_scan(
    r"(?P<left>[A-Za-zА-Яа-яЁёѢѣІіѲѳѴѵ]+)-[ \t]*\n[ \t]*"
    r"(?P<right>[a-zа-яёѣіѳѵ]+)"
)

#: Угловые минуты и секунды после градусов: «42°30'15"». Штрихи набирают и
#: апострофом с кавычкой, и типографскими знаками. Признак — предшествующий
#: знак градуса: без него «5'10"» — футы с дюймами, а не дуговая мера.
ARC_MINUTE_PATTERN = compile_scan(
    r"(?<=\d)°[ \t]*(?P<minutes>\d{1,2})['’′]"
    r"(?:[ \t]*(?P<seconds>\d{1,2})[\"”″])?"
)

_PAREN_INNER_WORD_PATTERN = compile_scan(r"([а-яёѣіѳѵ]+)\)")
_WORD_INTERNAL_PAREN_LETTERS = frozenset(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    "ѢѣІіѲѳѴѵ"
)


def insert_missing_space_before_paren(text: str) -> str:
    """Отбить пробелом скобку, приклеенную к слову опечаткой.

    Скобка внутри слова — редакторское раскрытие («м(оей)», «государ(ыни)»):
    если фрагмент перед скобкой вместе с буквами внутри неё образует
    словарное слово, скобка остаётся приклеенной. Иначе это опечатка
    («слова(пояснение)») и перед скобкой ставится пробел. Паттерн заякорен
    на «(»; буквенный фрагмент слева добирается вручную и только на
    совпадениях — линейность скана сохраняется.

    Отдельным проходом отбивается буквенный уточнитель марки после числа
    («Pz.38(t)»): слева цифра, поэтому словарная проверка к нему неприменима.
    """

    def repl(match: re.Match[str]) -> str:
        inner = _PAREN_INNER_WORD_PATTERN.match(text, match.end())
        if inner is not None:
            pos = match.start()
            start = pos
            while start and text[start - 1] in _WORD_INTERNAL_PAREN_LETTERS:
                start -= 1
            if word_is_known(text[start:pos] + inner.group(1)):
                return match.group(0)
        return " ("

    text = MISSING_SPACE_BEFORE_PAREN_PATTERN.sub(repl, text)
    return MISSING_SPACE_BEFORE_LETTER_PAREN_AFTER_DIGIT_PATTERN.sub(" (", text)


MULTI_SPACE_PATTERN = compile_scan(r"[ \t]{2,}")
SPACE_BEFORE_CLOSE_BRACKET_PATTERN = compile_scan(r"[ \t]+([\)\]\}])")
SPACE_AFTER_OPEN_BRACKET_PATTERN = compile_scan(r"([\(\[\{])[ \t]+")
TRAILING_SPACE_BEFORE_NEWLINE_PATTERN = compile_scan(r"[ \t]+\n")
LEADING_SPACE_AFTER_NEWLINE_PATTERN = compile_scan(r"\n[ \t]+")
EXCESSIVE_LINEBREAKS_PATTERN = compile_scan(r"\n{2,}")
DECORATIVE_SEPARATOR_PATTERN = compile_scan(
    r"(?:(?<=^)|(?<=\n))[ \t]*(?:[*=_~+#\-\xad\u2010-\u2015][ \t]*){3,}(?:(?=$)|(?=\n))"
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
    r"(?P<prefix>^|[(\[{«√]|(?<!\d)\s)"
    r"(?P<sign>[−-]\s*|[—–―])(?P<number>\d+(?:[.,]\d+)?)"
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
ELLIPSIS_SPACE_BEFORE_PATTERN = compile_scan(r"[ \t]+(?=…)")
ELLIPSIS_SPACE_AFTER_PATTERN = compile_scan(r"(?<=…)(?=[^\s.,;:!?…)\]}\"])\S")
# A run such as "С.Ш.А." is a dotted acronym, not three sentence ends. The
# fixed-width negative lookbehind keeps the spacing pass linear.
SENTENCE_SPACE_AFTER_PATTERN = compile_scan(
    r'(?<=[.!?…])(?<![A-ZА-ЯЁ]\.)'
    r'(?=["(«„“]?[A-ZА-ЯЁ])'
)
LINEBREAK_RUN_PATTERN = compile_scan(r"\n(?:[ \t]*\n)*[ \t]*")
LEGACY_LINE_START_PATTERN = compile_scan(r'(?:["«„“]\s*)?[А-ЯЁA-Z0-9]')
PAGE_ABBREVIATION_PATTERN = compile_scan(r"\b[сp]\.\s*(?=\d)", re.IGNORECASE)
PAGE_FULL_ABBREVIATION_PATTERN = compile_scan(r"\bстр\.\s*(?=\d)", re.IGNORECASE)
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
AGE_RANGE_PATTERN = compile_scan(
    r"(?<!\w)(?P<left>\d+)\s*[—–-]\s*(?P<right>\d+)\s+"
    r"(?P<unit>лет|года|год)(?!\w)",
    re.IGNORECASE,
)
LEGAL_CODE_GENITIVE_EXPANSIONS = {
    "ук": "уголовного кодекса российской федерации",
    "ак": "арбитражного кодекса российской федерации",
}
#: Граница справа обязательна: без неё безточечное «нэ» ловит начало обычного
#: слова — «Нэнси» читалось «нашей эрынси», а «нэпа» — «нашей эрыпа».
ERA_ABBREVIATION_PATTERN = compile_scan(
    r"(?<!\w)(?P<abbr>до\s+н\.?\s*э\.?|н\.?\s*э\.?)(?![^\W\d_])(?P<tail>\s*)",
    re.IGNORECASE,
)
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


#: Точка, приклеенная к числу справа: «Pz.38», «кн.2», «Fig.3», «т.е.2». Слева
#: обязателен буквенный отрезок с начала токена — так правило берёт и вторую
#: ступень кода («Sd.Kfz.251»), перед которой тоже стоит точка, и не влезает в
#: середину слова. Цифра слева от точки исключена самим требованием буквы,
#: поэтому дроби («3,14»), версии («1.2.3») и разряды («1.000») целы.
ABBREVIATION_DOT_BEFORE_DIGIT_PATTERN = compile_scan(
    r"(?<!\w)(?P<abbr>[A-Za-zА-Яа-яЁёѢѣІіѲѳѴѵ]+)\.(?=\d)"
)


def space_abbreviation_dot_before_digit(text: str) -> str:
    """Отбить пробелом число, приклеенное к точке сокращения.

    Без пробела число остаётся внутри токена, и следующие стадии выдают
    склеенное «пз.тридцать восемь». Точка сокращения не граница предложения,
    поэтому число читается со строчной.
    """
    return ABBREVIATION_DOT_BEFORE_DIGIT_PATTERN.sub(r"\g<abbr>. ", text)


def left_context(text: str, pos: int, window: int) -> str:
    """Не больше `window` знаков текста слева от `pos`.

    Размер окна на каждой площадке подобран под своё правило и сам является
    частью правила: расширить окно значит поймать чужое подлежащее.
    """
    return text[max(0, pos - window) : pos]


def normalize_age_ranges(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        context = left_context(text, match.start(), 64)
        # Only a group of people named before the range makes "6–12 лет" an age
        # span that has to be read as "от … до …". After "возраст" the numbers
        # are the value of that attribute and stay a plain range ("возраст
        # десять — двадцать лет"), which is also how every other range in the
        # text is read.
        if not re.search(r"\bдет(?:и|ей|ям|ях)\b", context, re.IGNORECASE):
            return match.group(0)
        return (
            f"от {match.group('left')} до {match.group('right')} "
            f"{match.group('unit')}"
        )

    return AGE_RANGE_PATTERN.sub(repl, text)


def normalize_explicit_dashes(text: str) -> str:
    if "–" not in text and "―" not in text:
        return text
    return text.translate(EXPLICIT_DASH_TRANSLATION)


def normalize_spaced_ascii_hyphens(text: str) -> str:
    return ASCII_DASH_SPACE_PATTERN.sub(" — ", text)


def protect_negative_numbers(text: str) -> str:
    """Пометить унарный минус перед числом служебным символом.

    Дефис, отбитый пробелом от числа после запятой, точки с запятой или
    двоеточия, — авторское тире («, - пишет он, - 13 апреля»), а не минус.
    Тире, приклеенное к цифре, — минус, набранный тире («к утру было —2°»);
    после знака корня — тоже минус («√–1» — мнимая единица, а не «корень из — один»);
    диапазоны («91—92») сюда не попадают: перед знаком там цифра, а не пробел.

    Отбитый пробелами с двух сторон дефис в прозе — тире («он сказал - 5
    человек ушли»). Минус так набирают только там, где слева стоит открывающая
    скобка, знак равенства или начало строки: в остальных позициях знак
    отделён от числа авторским пробелом, а не относится к нему.
    """

    def repl(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        sign = match.group("sign")
        number = match.group("number")
        if sign[-1].isspace():
            before = text[: match.start("sign")].rstrip()
            if before.endswith((",", ";", ":")):
                return match.group(0)
            if prefix.isspace() and before and before[-1] not in "(=[{«":
                return match.group(0)
        return f"{prefix}{NEGATIVE_NUMBER_PLACEHOLDER}{number}"

    return UNARY_MINUS_NUMBER_PATTERN.sub(repl, text)


def normalize_unary_plus_numbers(text: str) -> str:
    """Read a plus glued to a number as a unary positive sign."""

    return UNARY_PLUS_NUMBER_PATTERN.sub(
        lambda match: f"{match.group('prefix')}плюс {match.group('number')}", text
    )


def expand_arc_minutes(text: str) -> str:
    """«42°30'15"» -> «42° 30 мин 15 сек».

    Штрих сам по себе для синтеза бесполезен, а сокращения единиц дальше по
    конвейеру согласуются с падежом градусов как части одного измерения.
    """

    def repl(match: re.Match[str]) -> str:
        seconds = match.group("seconds")
        tail = f" {seconds} сек" if seconds else ""
        return f"° {match.group('minutes')} мин{tail}"

    return ARC_MINUTE_PATTERN.sub(repl, text)


def join_hyphenated_line_breaks(text: str) -> str:
    """Склеить слово, разорванное переносом на конце строки.

    Разделить перенос от настоящего дефиса составного слова можно морфологией:
    у переноса словарю известна слитная форма («гра-\\nфическим» ->
    «графическим»), у составного слова — дефисная («по-\\nрусски» ->
    «по-русски»). Когда словарь не знает ни одной формы (дореформенная
    орфография, редкие слова), части склеиваются: висячий дефис для синтеза
    всегда ошибка, а перенос строки — самая частая его причина. Исключение —
    когда обе части сами по себе полноценные слова: тогда дефис поставил автор.
    """

    def repl(match: re.Match[str]) -> str:
        left = match.group("left")
        right = match.group("right")
        joined = f"{left}{right}"
        if word_is_known(joined.lower()):
            return joined
        hyphenated = f"{left}-{right}"
        if word_is_known(hyphenated.lower()):
            return hyphenated
        if word_is_known(left.lower()) and word_is_known(right):
            return hyphenated
        return joined

    return WRAPPED_WORD_HYPHEN_PATTERN.sub(repl, text)


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


#: Обе функции ниже — цепочки `str.replace`, и это осознанно. Замена на
#: `str.translate` с таблицей выглядит как «один проход вместо шестнадцати», но
#: `translate` делает поиск в словаре на каждый символ строки, тогда как
#: `str.replace` с односимвольной иглой сводится к memchr и на промахе возвращает
#: исходный объект. Замер на 250 000 знаков (все семь корпусов, 2026-08-18):
#: чистка 1,4–2,1 мс циклом против 2,1–18,4 мс через `translate`, дроби
#: 1,0–1,7 мс против 1,4–17,5 мс. Подробности —
#: docs/SPEED_OBSERVATIONS.md, раздел «str.translate против цепочки replace».
def normalize_unicode_fractions(text: str) -> str:
    for char, replacement in UNICODE_FRACTIONS.items():
        if char not in text:
            continue
        # «2½» — смешанная дробь: без пробела замена склеила бы её в «21/2».
        text = re.sub(rf"(?<=\d){char}", f" {replacement}", text)
        text = text.replace(char, replacement)
    return text


def apply_cleanup_replacements(text: str) -> str:
    # Порядок важен: в `CLEANUP_REPLACEMENTS` многосимвольные ключи стоят раньше
    # односимвольных, иначе «−−» дало бы «—» вместо «--».
    for old, new in CLEANUP_REPLACEMENTS:
        text = text.replace(old, new)
    return text


#: После этих символов точка в конце строки не ставится: терминаторы, запятая,
#: разделители, кавычка — и тире любого начертания. Строка, оборванная тире,
#: закончена автором, «—.» неграмматично. Стадия идёт до нормализации тире
#: в `apply_cleanup_replacements`, поэтому здесь нужны все варианты знака.
LINE_END_KEEPS_NO_DOT = frozenset("\n.!?…,:;\"'") | frozenset("-–—―‐‑−")


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
            and previous not in LINE_END_KEEPS_NO_DOT
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


#: Знаки, после которых точка в «1.500» — разделитель разрядов: валюта и доли.
_THOUSANDS_UNIT_SYMBOLS = frozenset("₽$€£¥%‰")

#: Слова величины. Это не единицы измерения, в реестре единиц их нет, поэтому
#: они перечислены здесь.
_THOUSANDS_MAGNITUDE_WORDS = frozenset({"руб", "долл", "евро", "тыс", "млн", "млрд"})

#: Односимвольные обозначения, совпадающие со служебными словами, исключены из
#: проверки: «с» — секунда, но «версия 1.500 с изменениями» не «1500 секунд».
#: Цена — «1.500 В» не будет склеено, и это дешевле ложного склеивания в прозе.
_FUNCTION_WORD_HOMOGRAPHS = frozenset({"с", "в", "а", "у", "к", "о", "и", "я"})

#: Кандидат на разделитель разрядов вместе со следующим за ним токеном. Сам
#: токен проверяется по реестру единиц в колбэке, а не перечисляется в
#: алтернации: иначе новая единица в реестре молча не попадала бы сюда, а
#: алтернация из 479 алиасов стояла бы в lookahead'е.
THOUSANDS_BEFORE_UNIT_PATTERN = compile_scan(
    r"(?<!\d)(?P<number>\d{1,3}\.\d{3})(?=\s*(?P<unit>[₽$€£¥%‰]|\w+))"
)

#: Запятая — штатный десятичный знак, поэтому разрядной она признаётся только
#: при нулевом «хвосте»: дробная часть «000» не бывает осмысленной десятичной
#: записью («10,000 чел.» — десять тысяч человек, не «десять целых»).
COMMA_THOUSANDS_BEFORE_UNIT_PATTERN = compile_scan(
    r"(?<![\d.,])(?P<number>\d{1,3},000)(?=\s*(?P<unit>[₽$€£¥%‰]|\w+))"
)
#: Две и более групп по три цифры через запятую — однозначно разрядная
#: группировка: «1,234,567».
COMMA_GROUPED_NUMBER_PATTERN = compile_scan(
    r"(?<![\d.,])(\d{1,3}(?:,\d{3}){2,})(?![\d,])"
)


def _is_thousands_unit(token: str) -> bool:
    if not token:
        return False
    if token in _THOUSANDS_UNIT_SYMBOLS:
        return True
    folded = token.casefold()
    if folded in _THOUSANDS_MAGNITUDE_WORDS:
        return True
    if folded in _FUNCTION_WORD_HOMOGRAPHS:
        return False
    # Ленивый импорт разрывает цикл preprocess -> numerals -> preprocess.
    from .numerals._constants import UNIT_REGISTRY

    return UNIT_REGISTRY.resolve(token) is not None


def _join_thousands_before_unit(match: re.Match[str]) -> str:
    if not _is_thousands_unit(match.group("unit")):
        return match.group(0)
    return match.group("number").replace(".", "")


def _join_comma_thousands_before_unit(match: re.Match[str]) -> str:
    if not _is_thousands_unit(match.group("unit")):
        return match.group(0)
    return match.group("number").replace(",", "")


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
    text = COMMA_GROUPED_NUMBER_PATTERN.sub(
        lambda m: m.group(1).replace(",", ""), text
    )
    text = COMMA_THOUSANDS_BEFORE_UNIT_PATTERN.sub(
        _join_comma_thousands_before_unit, text
    )
    return THOUSANDS_BEFORE_UNIT_PATTERN.sub(_join_thousands_before_unit, text)
