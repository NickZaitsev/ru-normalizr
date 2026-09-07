from __future__ import annotations

import math
import re

from ._morph import (
    MorphParse,
    canonicalize_case,
    first_parse_required,
    parse_word,
    word_is_known,
)
from .abbreviation_context import should_keep_terminal_abbreviation_dot
from .abbreviation_rules import (
    ABBREVIATION_LITERAL_HINTS,
    ABBREVIATION_PATTERNS,
    ADJECTIVE_ABBREVIATION_EXPANSIONS,
    DECLINABLE_NOUN_ABBREVIATIONS,
    GEO_CLASSIFIER_ABBREVIATIONS,
    GEO_NAME_REQUIRED_ABBREVIATIONS,
    MOTION_VERB_ROOT_SUFFIXES,
    RELIEF_CONTEXT_LEMMAS,
)
from .constants import (
    ABBREV_DOTTED_PATTERN,
    ABBREV_MAX_LEN_EN,
    ABBREV_MAX_LEN_RU,
    ABBREV_MIN_LEN,
    ABBREV_SOLID_PATTERN,
    EN_DOUBLED_VOWEL_LETTER_NAMES,
    EN_LETTER_NAMES,
    KNOWN_ABBREVIATIONS,
    PERSON_INITIALS_SURNAME_PATTERN,
    PERSON_SINGLE_INITIAL_SURNAME_PATTERN,
    PERSON_SURNAME_INITIALS_PATTERN,
    PERSON_SURNAME_SINGLE_INITIAL_PATTERN,
    REAL_WORD_POS,
    RU_LETTER_NAMES,
    RU_VOWELS,
    RUSSIAN_NAME_TOKEN,
    apply_letter_vowel_mode,
    resolve_letter_name,
)
from .numerals._constants import PREP_CASE, VERB_CASE
from .numerals._helpers import safe_inflect
from .options import InitialsPauseMode, LetterVowelMode, NormalizeOptions
from .text_context import PUNCT_STRIP, simple_tokenize
from .text_scan import compile_scan, first_non_whitespace_index

_ETC_ABBREVIATION_PATTERN = compile_scan(
    r"(?<!\w)(?P<abbr>т\.?\s*[дп]\.)(?P<tail>\s*)(?!\w)", re.IGNORECASE
)
_ADJECTIVE_ABBREVIATION_WORD = (
    r"(?!и\b|или\b|либо\b|да\b|но\b|а\b)[А-ЯЁа-яё-]+"
)
_ADJECTIVE_ABBREVIATION_PATTERN = compile_scan(
    rf"(?<!\w)(?P<abbr>{'|'.join(sorted((re.escape(key) for key in ADJECTIVE_ABBREVIATION_EXPANSIONS), key=len, reverse=True))})"
    rf"(?P<space>\s+)(?P<phrase>{_ADJECTIVE_ABBREVIATION_WORD}(?:\s+{_ADJECTIVE_ABBREVIATION_WORD}){{0,5}})",
    re.IGNORECASE,
)
_LEFT_CONTEXT_TOKEN_PATTERN = compile_scan(r"[А-ЯЁа-яё-]+|[.!?]")
_UNAMBIGUOUS_PREPOSITION_CASES = {
    "без": "gent",
    "для": "gent",
    "до": "gent",
    "из": "gent",
    "к": "datv",
    "ко": "datv",
    "между": "ablt",
    "над": "ablt",
    "о": "loct",
    "об": "loct",
    "обо": "loct",
    "около": "gent",
    "от": "gent",
    "перед": "ablt",
    "при": "loct",
    "у": "gent",
}
#: Части речи, которые не начинают именную группу с определением слева:
#: служебные слова и числительное. Числительное справа означает номер рубрики
#: («гл. сорок вторая»), а не предмет, к которому относилось бы определение.
_FUNCTION_WORD_POS = frozenset({"PREP", "CONJ", "PRCL", "INTJ", "NUMR"})
_CASE_CONTEXT_BARRIER_POS = frozenset(
    {
        "ADJF",
        "ADJS",
        "COMP",
        "CONJ",
        "GRND",
        "NOUN",
        "NPRO",
        "NUMR",
        "PRED",
        "PREP",
        "PRTF",
        "PRTS",
    }
)
_WORD_AMPERSAND_PATTERN = compile_scan(
    r"(?P<left>[A-Za-zА-Яа-яЁё]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)*)\s*&\s*(?P<right>[A-Za-zА-Яа-яЁё]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)*)"
)
_SINGLE_TOKEN_EN_LETTER_NAMES = frozenset(
    value.lower()
    for value in (*EN_LETTER_NAMES.values(), *EN_DOUBLED_VOWEL_LETTER_NAMES.values())
    if " " not in value
)
_LANGUAGE_ORIGIN_ABBREVIATIONS = {
    key: ADJECTIVE_ABBREVIATION_EXPANSIONS[key]
    for key in (
        "англ.",
        "руск.",
        "рус.",
        "немецк.",
        "нем.",
        "франц.",
        "греч.",
        "латин.",
        "лат.",
    )
}
_SENTENCE_OPENING_CHARS = " \t\r\"'«„“([{"
_SENTENCE_END_CHARS = ".!?…"
_LANGUAGE_ORIGIN_PATTERN = compile_scan(
    rf"(?<!\w)(?P<prep>от|из|с|со)\s+(?P<abbr>{'|'.join(sorted((re.escape(key) for key in _LANGUAGE_ORIGIN_ABBREVIATIONS), key=len, reverse=True))})"
    r"(?P<space>\s+)(?P<word>[^\s.,;:!?()\"\[\]{}«»]+)",
    re.IGNORECASE,
)
_FOLLOWING_NAME_TOKEN_PATTERN = compile_scan(
    rf"\s+(?P<token>{RUSSIAN_NAME_TOKEN})(?![A-Za-zА-Яа-яЁё])"
)
_CARDINAL_ONE_WORDS = frozenset({"один", "одна", "одно", "одну"})


def _has_non_one_cardinal_before_abbreviation(left_context: str) -> bool:
    tokens = _LEFT_CONTEXT_TOKEN_PATTERN.findall(left_context[-40:])
    if not tokens:
        return False
    preceding = tokens[-1].casefold()
    if preceding in _CARDINAL_ONE_WORDS:
        return False
    return any(candidate.tag.POS == "NUMR" for candidate in parse_word(preceding))


def _etc_conjunction_precedes(left_context: str) -> bool:
    """Перед «и т. д.» стоит союз «и»: он входит в саму идиому."""

    tokens = _LEFT_CONTEXT_TOKEN_PATTERN.findall(left_context[-40:])
    return bool(tokens) and tokens[-1].casefold() == "и"


def _expand_contextual_etc_abbreviations(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        raw_abbr = match.group("abbr")
        tail = match.group("tail")
        normalized_abbr = re.sub(r"\s+", "", raw_abbr).lower()
        expansion = "так далее" if "д" in normalized_abbr else "тому подобное"

        # Заглавная вторая буква — это инициалы перед фамилией («Т. Д.
        # Лысенко») либо после неё («Лысенко Т. Д.»), а не сокращение.
        # Идиома пишется с заглавными только там, где заглавная вся строка,
        # и тогда при ней остаётся союз: «КНИГИ И Т. Д. ЛЕЖАЛИ НА СТОЛЕ».
        if raw_abbr[-2].isupper() and not _etc_conjunction_precedes(
            text[: match.start()]
        ):
            return match.group(0)

        next_char = text[match.end()] if match.end() < len(text) else ""
        next_index, saw_newline = first_non_whitespace_index(text, match.end())
        next_significant = text[next_index] if next_index < len(text) else ""
        has_linebreak_before_next = "\n" in tail or saw_newline

        keep_terminal_dot = (
            not next_significant
            or has_linebreak_before_next
            or (next_significant and next_significant.isupper())
        )

        if (
            next_char in '"»”)]}'
            and next_index + 1 < len(text)
            and text[next_index + 1].isupper()
        ):
            keep_terminal_dot = True

        return f"{expansion}{'.' if keep_terminal_dot else ''}{tail}"

    return _ETC_ABBREVIATION_PATTERN.sub(repl, text)


#: Сокращения, омонимичные существительному: «гл.» — и «главный», и «глава».
_HEADING_NOUN_ABBREVIATIONS = frozenset({"гл."})


def _governs_genitive_whole(noun_parse: MorphParse) -> bool:
    """Существительное справа — родительное неодушевлённое целое.

    «Глава» управляет родительным целого: «глава книги», «глава города»,
    «глава управления». Прилагательное «главный» так не управляет: у него
    справа стоит одушевлённая должность («гл. врача») или другой падеж
    («гл. образом»). Форма проверяется по всем разборам слова, потому что
    «книги» — и родительный единственного, и именительный множественного,
    а выбор между ними здесь ни на что не опирается.
    """
    return any(
        candidate.tag.POS == "NOUN"
        and candidate.tag.case == "gent"
        and "inan" in candidate.tag
        for candidate in parse_word(noun_parse.word)
    )


def _expand_contextual_adjective_abbreviations(text: str) -> str:
    def parses_agree(modifier: MorphParse, head: MorphParse) -> bool:
        modifier_case = canonicalize_case(modifier.tag.case)
        head_case = canonicalize_case(head.tag.case)
        if modifier_case != head_case or modifier.tag.number != head.tag.number:
            return False
        if head.tag.number == "sing" and modifier.tag.gender != head.tag.gender:
            return False
        if head_case == "accs" and (
            head.tag.number == "plur" or head.tag.gender == "masc"
        ):
            modifier_animacy = modifier.tag.animacy
            head_animacy = head.tag.animacy
            if (
                modifier_animacy is not None
                and head_animacy is not None
                and modifier_animacy != head_animacy
            ):
                return False
        return True

    def infer_governing_case(left_context: str) -> str | None:
        tokens = _LEFT_CONTEXT_TOKEN_PATTERN.findall(left_context[-160:])[-6:]
        for token in reversed(tokens):
            if token in {".", "!", "?"}:
                break
            word = token.lower()
            if word in _UNAMBIGUOUS_PREPOSITION_CASES:
                return _UNAMBIGUOUS_PREPOSITION_CASES[word]
            parses = parse_word(word)
            best_parse = max(parses, key=lambda candidate: candidate.score, default=None)
            verb_candidates = [
                candidate
                for candidate in parses
                if candidate.tag.POS in {"VERB", "INFN", "GRND"}
            ]
            verb = max(
                verb_candidates,
                key=lambda candidate: candidate.score,
                default=None,
            )
            if (
                best_parse is None
                or verb is None
                or not math.isclose(
                    verb.score,
                    best_parse.score,
                    rel_tol=1e-9,
                    abs_tol=1e-12,
                )
            ):
                if (
                    best_parse is not None
                    and best_parse.tag.POS in _CASE_CONTEXT_BARRIER_POS
                ):
                    break
                continue
            governed_case = VERB_CASE.get(verb.normal_form)
            if governed_case is not None:
                return governed_case
            if "tran" in verb.tag:
                return "accs"
        return None

    def choose_head_noun(phrase: str, expected_case: str | None):
        def case_hint_score(candidate: MorphParse) -> int:
            if expected_case is None:
                return 0
            candidate_case = canonicalize_case(candidate.tag.case)
            if candidate_case == expected_case:
                return 2
            if (
                expected_case in {"nomn", "accs"}
                and candidate_case in {"nomn", "accs"}
                and candidate.tag.number == "plur"
                and "inan" in candidate.tag
            ):
                return 1
            return 0

        words = phrase.split()
        parsed_words = [parse_word(word.lower()) for word in words]
        modifier_parses: list[MorphParse] = []
        fallback_noun: MorphParse | None = None
        for word_index, parsed in enumerate(parsed_words):
            noun_candidates = [
                candidate for candidate in parsed if "NOUN" in candidate.tag
            ]
            adjective_candidates = [
                candidate
                for candidate in parsed
                if candidate.tag.POS in {"ADJF", "PRTF"}
            ]
            substantive_candidates = [
                candidate for candidate in adjective_candidates if "Subx" in candidate.tag
            ]
            later_parses = parsed_words[word_index + 1 :]
            later_noun_candidates = [
                candidate
                for candidates in later_parses
                for candidate in candidates
                if candidate.tag.POS == "NOUN"
            ]
            later_substantive_candidates = [
                candidate
                for candidates in later_parses
                for candidate in candidates
                if candidate.tag.POS in {"ADJF", "PRTF"} and "Subx" in candidate.tag
            ]
            agrees_with_later_noun = any(
                parses_agree(adjective, noun)
                for adjective in adjective_candidates
                for noun in later_noun_candidates
            )

            # Ambiguous forms such as «часовой» can be both a noun and an
            # adjective. Prefer their modifier reading when a later noun
            # provides an explicit agreement target.
            if adjective_candidates and agrees_with_later_noun:
                modifier_parses.extend(adjective_candidates)
                continue

            def compatibility(
                noun_candidate,
                modifiers=tuple(modifier_parses),
            ) -> tuple[int, int, int]:
                modifier_score = 0
                noun_case = canonicalize_case(noun_candidate.tag.case)
                for modifier in modifiers:
                    if canonicalize_case(modifier.tag.case) != noun_case:
                        continue
                    if modifier.tag.number != noun_candidate.tag.number:
                        continue
                    if (
                        noun_candidate.tag.number == "sing"
                        and modifier.tag.gender != noun_candidate.tag.gender
                    ):
                        continue
                    modifier_score += 1
                return (
                    modifier_score,
                    int("inan" in noun_candidate.tag),
                    case_hint_score(noun_candidate),
                )

            if noun_candidates:
                best_noun = max(noun_candidates, key=compatibility)
                if fallback_noun is None:
                    fallback_noun = best_noun
                if not modifier_parses or any(
                    parses_agree(modifier, noun)
                    for modifier in modifier_parses
                    for noun in noun_candidates
                ):
                    return best_noun
                continue

            if substantive_candidates and not agrees_with_later_noun:
                def substantive_score(candidate: MorphParse) -> tuple[int, int, float]:
                    case_score = int(
                        expected_case is not None
                        and canonicalize_case(candidate.tag.case) == expected_case
                    )
                    modifier_score = sum(
                        parses_agree(modifier, candidate) for modifier in modifier_parses
                    )
                    return case_score, modifier_score, candidate.score

                return max(substantive_candidates, key=substantive_score)

            if adjective_candidates and (
                later_noun_candidates or later_substantive_candidates
            ):
                modifier_parses.extend(adjective_candidates)
        return fallback_noun

    def inflect_adjective(
        lemma: str, noun_parse, *, counted_by_non_one_cardinal: bool = False
    ) -> str:
        parsed = parse_word(lemma)
        adjective_parse = next(
            (
                candidate
                for candidate in parsed
                if candidate.tag.POS in {"ADJF", "PRTF"}
            ),
            parsed[0] if parsed else None,
        )
        if adjective_parse is None:
            return lemma

        noun_case = canonicalize_case(noun_parse.tag.case)
        if noun_case is None:
            return lemma
        is_plural = "plur" in noun_parse.tag
        if counted_by_non_one_cardinal:
            # The noun's surface form is ambiguous in phrases such as "пути";
            # cardinal government still requires a genitive-plural modifier:
            # "два государственных пути".
            target_tags = {"gent", "plur"}
        else:
            target_tags = {noun_case}
            if is_plural:
                target_tags.add("plur")
            else:
                target_tags.add("sing")
                if noun_parse.tag.gender:
                    target_tags.add(noun_parse.tag.gender)
        # Animacy only matters for a real accusative target; the cardinal branch
        # above already fixed the modifier at genitive plural.
        if (
            not counted_by_non_one_cardinal
            and noun_case == "accs"
            and (is_plural or noun_parse.tag.gender == "masc")
        ):
            for animacy in ("anim", "inan"):
                if animacy in noun_parse.tag:
                    target_tags.add(animacy)
                    break
        return safe_inflect(
            adjective_parse,
            target_tags,
            fallback_word=lemma,
            pos_filter={"ADJF", "PRTF"},
        )

    def repl(match: re.Match[str]) -> str:
        abbr = match.group("abbr")
        phrase = match.group("phrase")
        if abbr.lower() in _LANGUAGE_ORIGIN_ABBREVIATIONS and phrase[:1].isupper():
            return match.group(0)
        # Определение стоит непосредственно перед своей группой, поэтому
        # служебное слово справа означает, что группы здесь нет: «гл. без
        # номера» — это существительное, а не прилагательное.
        if first_parse_required(phrase.split()[0].lower()).tag.POS in _FUNCTION_WORD_POS:
            return match.group(0)
        # The pattern is built from this dictionary's keys, so the lookup always
        # hits: a KeyError here would mean the two have drifted apart.
        lemma = ADJECTIVE_ABBREVIATION_EXPANSIONS[abbr.lower()]
        left_context_start = max(0, match.start() - 160)
        expected_case = infer_governing_case(text[left_context_start : match.start()])
        noun_parse = choose_head_noun(phrase, expected_case)
        if noun_parse is None:
            return match.group(0)
        if not word_is_known(noun_parse.word) or not word_is_known(
            phrase.split()[0].lower()
        ):
            # Форму незнакомого слова словарь угадывает, и согласовываться с
            # догадкой нельзя: у дореформенного «Александръ» она даёт
            # родительный неодушевлённого, а у «Владиміра» — краткое
            # прилагательное женского рода, из-за которого вершиной группы
            # становится слово из соседнего однородного члена.
            return match.group(0)
        if abbr.lower() in _HEADING_NOUN_ABBREVIATIONS and _governs_genitive_whole(
            noun_parse
        ):
            return match.group(0)
        expanded = inflect_adjective(
            lemma,
            noun_parse,
            counted_by_non_one_cardinal=_has_non_one_cardinal_before_abbreviation(
                text[left_context_start : match.start()]
            ),
        )
        if abbr[:1].isupper():
            expanded = expanded[:1].upper() + expanded[1:]
        return f"{expanded}{match.group('space')}{phrase}"

    return _ADJECTIVE_ABBREVIATION_PATTERN.sub(repl, text)


def _expand_language_origin_abbreviations(text: str) -> str:
    def has_non_cyrillic_word(word: str) -> bool:
        letters = [char for char in word if char.isalpha()]
        return bool(letters) and not any(
            ("А" <= char <= "я") or char in "Ёё" for char in letters
        )

    def inflect_language_lemma(lemma: str) -> str:
        parsed = next(
            (
                candidate
                for candidate in parse_word(lemma)
                if candidate.tag.POS in {"ADJF", "PRTF"}
            ),
            None,
        )
        if parsed is None:
            return lemma
        return safe_inflect(
            parsed,
            {"gent", "sing", "masc"},
            fallback_word=lemma,
            pos_filter={"ADJF", "PRTF"},
        )

    def repl(match: re.Match[str]) -> str:
        word = match.group("word")
        if not has_non_cyrillic_word(word):
            return match.group(0)
        lemma = _LANGUAGE_ORIGIN_ABBREVIATIONS[match.group("abbr").lower()]
        return (
            f"{match.group('prep')} {inflect_language_lemma(lemma)}"
            f"{match.group('space')}{word}"
        )

    return _LANGUAGE_ORIGIN_PATTERN.sub(repl, text)


def _expand_rule_preserving_sentence_case(
    match: re.Match[str], replacement: str, source: str
) -> str:
    expanded = match.expand(replacement)
    source_words = re.findall(r"[^\W\d_]+", match.group(0))
    if len(source_words) < 2 or any(len(word) != 1 for word in source_words):
        return expanded
    first_source_letter = next((char for char in match.group(0) if char.isalpha()), "")
    if not first_source_letter.isupper():
        return expanded

    prefix_index = match.start() - 1
    while prefix_index >= 0 and source[prefix_index] in _SENTENCE_OPENING_CHARS:
        prefix_index -= 1
    if (
        prefix_index >= 0
        and source[prefix_index] not in _SENTENCE_END_CHARS
        and source[prefix_index] != "\n"
    ):
        return expanded

    first_expansion_letter = next(
        (index for index, char in enumerate(expanded) if char.isalpha()), None
    )
    if first_expansion_letter is None:
        return expanded
    return (
        expanded[:first_expansion_letter]
        + expanded[first_expansion_letter].upper()
        + expanded[first_expansion_letter + 1 :]
    )


def expand_person_initials(
    text: str,
    *,
    vowel_mode: LetterVowelMode = "single",
    pause_mode: InitialsPauseMode = "preserve",
) -> str:
    def initial_name(ch: str) -> str:
        return resolve_letter_name(ch, vowel_mode) or ch.lower()

    def pause_separated(*parts: str) -> str:
        separator = ", " if pause_mode == "comma" else " "
        return separator.join(parts)

    def surname_first_non_final(
        *parts: str, add_trailing_pause: bool = True
    ) -> str:
        expanded = pause_separated(*parts)
        if pause_mode == "comma" and add_trailing_pause:
            return f"{expanded},"
        return expanded

    def candidate_grammemes(candidate) -> frozenset[str]:
        grammemes = getattr(candidate.tag, "grammemes", None)
        if grammemes is None:
            return frozenset()
        return frozenset(grammemes)

    def is_likely_person_name_token(token: str) -> bool:
        parsed = parse_word(token)
        if not parsed:
            return True
        meaningful = [
            candidate
            for candidate in parsed
            if "PNCT" not in candidate_grammemes(candidate)
        ]
        if not meaningful:
            return True
        if any(
            marker in candidate_grammemes(candidate)
            for candidate in meaningful
            for marker in ("Surn", "Name", "Patr")
        ):
            return True
        top_candidates = meaningful[:3]
        if top_candidates and all(
            "Geox" in candidate_grammemes(candidate) for candidate in top_candidates
        ):
            return False
        return not (
            top_candidates
            and all(
                "Abbr" in candidate_grammemes(candidate) for candidate in top_candidates
            )
        )

    def is_confident_person_name_token(token: str) -> bool:
        parsed = parse_word(token)
        if not parsed:
            return False
        meaningful = [
            candidate
            for candidate in parsed
            if "PNCT" not in candidate_grammemes(candidate)
        ]
        return any(
            marker in candidate_grammemes(candidate)
            for candidate in meaningful
            for marker in ("Surn", "Name", "Patr")
        )

    def has_following_person_name_token(match_end: int) -> bool:
        match = _FOLLOWING_NAME_TOKEN_PATTERN.match(text, match_end)
        if match is None:
            return False
        return is_confident_person_name_token(match.group("token"))

    def choose_tail(match_end: int) -> tuple[bool, bool]:
        next_index, _ = first_non_whitespace_index(text, match_end)
        if next_index >= len(text):
            return True, False
        stripped_first = text[next_index]
        # Opening marks only. A closing mark means the quotation ends here, so it
        # must reach the strip loop below instead: with "»" in this set too, the
        # opening test won and "Иванов А. Б.»" got the non-final comma form.
        # '"' and "'" stay here because they are ambiguous and default to opening.
        if stripped_first in "\"'«“„‟‚‘‹([{":
            return False, False
        while next_index < len(text) and text[next_index] in "\"'»”’›)]}":
            next_index, _ = first_non_whitespace_index(text, next_index + 1)
        if next_index >= len(text):
            return True, False
        stripped_first = text[next_index]
        if stripped_first in ".!?…":
            return True, False
        if stripped_first in ",;:—–-":
            return False, True
        if stripped_first.islower() or stripped_first.isdigit():
            return False, False
        return True, False

    def repl_surname_initials(match):
        if has_following_person_name_token(match.end()):
            return match.group(0)
        surname = match.group("surname")
        i1 = initial_name(match.group("i1"))
        i2 = initial_name(match.group("i2"))
        is_final, has_clause_punctuation = choose_tail(match.end())
        if is_final:
            terminal = (
                ""
                if (
                    (next_index := first_non_whitespace_index(text, match.end())[0])
                    < len(text)
                    and text[next_index] in ".!?…"
                )
                else "."
            )
            return f"{surname} {i1} {i2}{terminal}"
        return surname_first_non_final(
            surname,
            i1,
            i2,
            add_trailing_pause=not has_clause_punctuation,
        )

    def repl_surname_single_initial(match):
        if has_following_person_name_token(match.end()):
            return match.group(0)
        surname = match.group("surname")
        if not is_likely_person_name_token(surname):
            return match.group(0)
        i1 = initial_name(match.group("i1"))
        is_final, has_clause_punctuation = choose_tail(match.end())
        if is_final:
            terminal = (
                ""
                if (
                    (next_index := first_non_whitespace_index(text, match.end())[0])
                    < len(text)
                    and text[next_index] in ".!?…"
                )
                else "."
            )
            return f"{surname} {i1}{terminal}"
        return surname_first_non_final(
            surname,
            i1,
            add_trailing_pause=not has_clause_punctuation,
        )

    def repl_initials_surname(match):
        i1 = initial_name(match.group("i1"))
        i2 = initial_name(match.group("i2"))
        surname = match.group("surname")
        is_final, _has_clause_punctuation = choose_tail(match.end())
        if is_final:
            terminal = (
                ""
                if (
                    (next_index := first_non_whitespace_index(text, match.end())[0])
                    < len(text)
                    and text[next_index] in ".!?…"
                )
                else "."
            )
            return f"{i1} {i2} {surname}{terminal}"
        return f"{i1} {i2} {surname}"

    def repl_single_initial_surname(match):
        surname = match.group("surname")
        if not is_likely_person_name_token(surname):
            return match.group(0)
        i1 = initial_name(match.group("i1"))
        is_final, _has_clause_punctuation = choose_tail(match.end())
        if is_final:
            terminal = (
                ""
                if (
                    (next_index := first_non_whitespace_index(text, match.end())[0])
                    < len(text)
                    and text[next_index] in ".!?…"
                )
                else "."
            )
            return f"{i1} {surname}{terminal}"
        return f"{i1} {surname}"

    text = PERSON_SURNAME_INITIALS_PATTERN.sub(repl_surname_initials, text)
    text = PERSON_INITIALS_SURNAME_PATTERN.sub(repl_initials_surname, text)
    text = PERSON_SURNAME_SINGLE_INITIAL_PATTERN.sub(repl_surname_single_initial, text)
    return PERSON_SINGLE_INITIAL_SURNAME_PATTERN.sub(repl_single_initial_surname, text)


def expand_letter_abbreviations(
    text: str, *, vowel_mode: LetterVowelMode = "single"
) -> str:
    def keep_dotted_tail_dot(match: re.Match[str]) -> bool:
        next_index, saw_newline = first_non_whitespace_index(text, match.end())
        if next_index >= len(text) or saw_newline:
            return True
        next_char = text[next_index]
        if next_char in ".!?…":
            return True
        if next_char in "\"»”)]}":
            next_index, _ = first_non_whitespace_index(text, next_index + 1)
            return next_index >= len(text) or text[next_index].isupper()
        return next_char.isupper()

    def expand_token(
        token: str, is_dotted: bool, *, keep_terminal_dot: bool = True
    ) -> str:
        tail_dot = token.endswith(".") and keep_terminal_dot
        letters = [char for char in token if char.isalpha()]
        if len(letters) < ABBREV_MIN_LEN:
            return token

        letters_upper = [char.upper() for char in letters]
        joined_key = "".join(letters_upper)
        if joined_key in KNOWN_ABBREVIATIONS:
            custom_reading = KNOWN_ABBREVIATIONS[joined_key]
            if joined_key not in {"UTC", "ISO"}:
                custom_reading = apply_letter_vowel_mode(custom_reading, vowel_mode)
            return custom_reading + "." if tail_dot else custom_reading

        if all(char in RU_LETTER_NAMES for char in letters_upper):
            has_vowel = any(char in RU_VOWELS for char in letters_upper)
            if not is_dotted:
                lowered_key = joined_key.lower()
                # Словом читается только то, что произносимо и знакомо словарю
                # по-настоящему. Оба условия нужны: «ШКПС» pymorphy разбирает как
                # существительное по догадке, «гдр» лежит в словаре настоящей
                # статьёй, и обе аббревиатуры уезжали в синтез нечитаемой кашей.
                if has_vowel and word_is_known(lowered_key):
                    parsed = first_parse_required(lowered_key)
                    if parsed.tag.POS in REAL_WORD_POS and "Abbr" not in parsed.tag:
                        return token
            if not is_dotted:
                if len(letters_upper) > ABBREV_MAX_LEN_RU:
                    return token
                if sum(1 for char in letters_upper if char in RU_VOWELS) > 1:
                    return token
            names = [resolve_letter_name(char, vowel_mode) or char for char in letters_upper]
        elif all(char in EN_LETTER_NAMES for char in letters_upper):
            if not is_dotted and len(letters_upper) > ABBREV_MAX_LEN_EN:
                return token
            names = [resolve_letter_name(char, vowel_mode) or char for char in letters_upper]
        else:
            return token

        expanded = " ".join(names)
        return expanded + "." if tail_dot else expanded

    text = ABBREV_DOTTED_PATTERN.sub(
        lambda m: expand_token(
            m.group(0), True, keep_terminal_dot=keep_dotted_tail_dot(m)
        ),
        text,
    )
    return ABBREV_SOLID_PATTERN.sub(lambda m: expand_token(m.group(0), False), text)


def _normalize_contextual_ampersands(
    text: str, options: NormalizeOptions | None = None
) -> str:
    if "&" not in text:
        return text
    active = options or NormalizeOptions()

    def has_ascii_letters(token: str) -> bool:
        return any("A" <= char <= "Z" or "a" <= char <= "z" for char in token)

    def has_cyrillic_letters(token: str) -> bool:
        return any(("А" <= char <= "я") or char in "Ёё" for char in token)

    def is_english_letter_name(token: str) -> bool:
        return token.lower() in _SINGLE_TOKEN_EN_LETTER_NAMES

    def repl(match: re.Match[str]) -> str:
        left = match.group("left")
        right = match.group("right")
        left_has_ascii = has_ascii_letters(left)
        right_has_ascii = has_ascii_letters(right)
        left_is_english = is_english_letter_name(left)
        right_is_english = is_english_letter_name(right)

        brand_like_context = (
            (left_has_ascii and right_has_ascii and active.enable_latinization)
            or (left_is_english and right_is_english)
            or (left_is_english and right_has_ascii)
            or (left_has_ascii and right_is_english)
        )
        if brand_like_context:
            return f"{left} энд {right}"

        if left_has_ascii and right_has_ascii:
            return f"{left} & {right}"

        if (
            has_cyrillic_letters(left)
            or has_cyrillic_letters(right)
            or left_is_english
            or right_is_english
        ):
            return f"{left} и {right}"

        return match.group(0)

    return _WORD_AMPERSAND_PATTERN.sub(repl, text)


_GEO_CLASSIFIER_PATTERN = compile_scan(
    rf"(?<!\w)(?P<abbr>{'|'.join(sorted(GEO_CLASSIFIER_ABBREVIATIONS, key=len, reverse=True))})\.\s+"
    rf"(?=(?P<name>[А-ЯЁ][а-яё-]+))",
    re.IGNORECASE,
)
#: Сколько слов слева просматривать в поисках формы рельефа: она стоит вершиной
#: родительной цепочки прямо перед классификатором («у подножия г. Эльбрус»).
_RELIEF_CONTEXT_SCAN = 2
#: «в»/«на»/«за» перед географическим классификатором читаются локативно:
#: повествование описывает положение («на оз. Байкал»), а не направление.
_GEO_STATIC_PREPOSITION_CASE = {
    "в": "loct",
    "во": "loct",
    "на": "loct",
    "за": "ablt",
    "под": "ablt",
    "над": "ablt",
    "перед": "ablt",
}
#: Сколько слов слева от предлога просматривать в поисках глагола движения:
#: между ними стоят обстоятельства («переехал вместе с семьёй в г. Казань»).
_MOTION_VERB_SCAN = 4


def _motion_verb_precedes(tokens: list[str]) -> bool:
    """Есть ли слева глагол движения: тогда «в»/«на» — направление.

    Проверяется корень нормальной формы: приставка и вид дают десятки форм
    одного глагола, и перечислять их поштучно значило бы завести список слов
    вместо правила.
    """
    for token in reversed(tokens[-_MOTION_VERB_SCAN:]):
        word = token.lower().strip(PUNCT_STRIP)
        if not word:
            continue
        parsed = first_parse_required(word)
        if parsed.tag.POS not in {"VERB", "INFN", "GRND", "PRTF", "PRTS"}:
            continue
        if parsed.normal_form.endswith(MOTION_VERB_ROOT_SUFFIXES):
            return True
    return False


def _reads_as_place_name(name: str, classifier_case: str) -> bool:
    """Стоит ли справа от классификатора имя населённого пункта.

    Помета `Geox` у угаданного слова ничего не значит: словарь метит так и
    «Хан-Тенгри», и незнакомую фамилию на согласный. У знакомого слова форма
    должна укладываться в конструкцию: имя либо повторяет падеж классификатора
    («близ города Ялуторовска»), либо остаётся несклоняемым в исходной форме
    («в городе Казань»). «Г. Буле» проверку не проходит: у «Буле» есть только
    дательный и предложный, а классификатор здесь именительный — значит это
    «господин», а не «город».
    """
    if not word_is_known(name):
        return False
    allowed = {classifier_case, "nomn", "accs"}
    return any(
        "Geox" in candidate.tag and candidate.tag.case in allowed
        for candidate in parse_word(name)
    )


def _expand_geo_classifier_abbreviations(text: str) -> str:
    """«до оконечности оз. Иссык-Куль» → «озера»: падеж задаёт левый контекст.

    Падеж классификатора сообщает предлог перед ним или управляющее
    существительное слева (родительная цепочка «оконечности озера»); без них
    классификатор — подлежащее и остаётся именительным.
    """

    def repl(match: re.Match[str]) -> str:
        abbr = match.group("abbr")
        lemma = GEO_CLASSIFIER_ABBREVIATIONS[abbr.lower()]
        left_tokens = simple_tokenize(text[max(0, match.start() - 40) : match.start()])
        case = "nomn"
        prev = left_tokens[-1].lower().strip(PUNCT_STRIP) if left_tokens else ""
        if prev:
            if prev in _GEO_STATIC_PREPOSITION_CASE:
                case = _GEO_STATIC_PREPOSITION_CASE[prev]
                if prev in {"в", "во", "на"} and _motion_verb_precedes(
                    left_tokens[:-1]
                ):
                    case = "accs"
            elif prev in PREP_CASE:
                case = PREP_CASE[prev]
            else:
                p_prev = first_parse_required(prev)
                if "NOUN" in p_prev.tag and "Fixd" not in p_prev.tag:
                    case = "gent"
        if abbr.lower() in GEO_NAME_REQUIRED_ABBREVIATIONS and not _reads_as_place_name(
            match.group("name"), case
        ):
            return match.group(0)
        if abbr.lower() in GEO_NAME_REQUIRED_ABBREVIATIONS and any(
            first_parse_required(token.lower().strip(PUNCT_STRIP)).normal_form
            in RELIEF_CONTEXT_LEMMAS
            for token in left_tokens[-_RELIEF_CONTEXT_SCAN:]
            if token.strip(PUNCT_STRIP)
        ):
            # «У подножия г. Эльбрус» — гора: подставить «город» нельзя,
            # а раскрывать «гору» этому правилу не поручено.
            return match.group(0)
        expanded = lemma
        if case != "nomn":
            p_lemma = next(
                (
                    candidate
                    for candidate in parse_word(lemma)
                    if "NOUN" in candidate.tag and candidate.tag.case == "nomn"
                ),
                None,
            )
            if p_lemma is not None:
                expanded = safe_inflect(p_lemma, {case, "sing"}, fallback_word=lemma)
        if abbr[:1].isupper():
            expanded = expanded[:1].upper() + expanded[1:]
        return f"{expanded} "

    return _GEO_CLASSIFIER_PATTERN.sub(repl, text)


#: Сокращение существительного без номера. Номер справа означает ссылку, и её
#: забирает `normalize_numbered_references` в препроцессе; здесь остаются
#: употребления, у которых падеж задаёт только левый контекст.
_DECLINABLE_NOUN_ABBREVIATION_PATTERN = compile_scan(
    rf"(?<!\w)(?P<abbr>{'|'.join(sorted(DECLINABLE_NOUN_ABBREVIATIONS, key=len, reverse=True))})"
    r"\.(?!\s*\d)(?!\w)",
    re.IGNORECASE,
)
#: «в»/«на»/«за» перед предметом речи читаются локативно: «в таблице»,
#: «в рублях», «в области» — предмет, а не направление.
_NOUN_ABBREVIATION_STATIC_CASE = {
    "в": "loct",
    "во": "loct",
    "на": "loct",
    "о": "loct",
    "об": "loct",
    "при": "loct",
    "за": "ablt",
    "под": "ablt",
    "над": "ablt",
    "перед": "ablt",
}
#: Сколько слов слева просматривать в поисках предлога: между предлогом и
#: сокращением стоит согласованное определение («в Московской обл.»), и больше
#: двух определений подряд в этой конструкции не бывает.
_NOUN_ABBREVIATION_PREPOSITION_SCAN = 3


def _noun_abbreviation_case(text: str, start: int) -> str:
    """Падеж сокращённого существительного по левому контексту.

    Предлог ищется через согласованные определения: «в Московской обл.» —
    предложный от «в», а «Московской» уже стоит в нём же. Без предлога
    сокращение — подлежащее или дополнение при глаголе, и остаётся
    именительным: угадывать управление глагола здесь нечем.
    """
    tokens = simple_tokenize(text[max(0, start - 48) : start])
    for token in reversed(tokens[-_NOUN_ABBREVIATION_PREPOSITION_SCAN:]):
        word = token.lower().strip(PUNCT_STRIP)
        if not word:
            continue
        if word in _NOUN_ABBREVIATION_STATIC_CASE:
            return _NOUN_ABBREVIATION_STATIC_CASE[word]
        if word in PREP_CASE:
            return PREP_CASE[word]
        parsed = first_parse_required(word)
        if parsed.tag.POS not in {"ADJF", "PRTF"}:
            break
    return "nomn"


def _expand_declinable_noun_abbreviations(text: str) -> str:
    """«Цена в руб.» → «в рублях», «в Московской обл.» → «в области».

    Раньше эти существительные подставлялись одной формой независимо от
    контекста, и получалось «в Московской область», «в рублей», «в таблица».
    """

    def repl(match: re.Match[str]) -> str:
        abbr = match.group("abbr")
        lemma, number = DECLINABLE_NOUN_ABBREVIATIONS[abbr.casefold()]
        case = _noun_abbreviation_case(text, match.start())
        if case == "nomn" and number == "sing":
            # Именительный единственного — это сама лемма, и подстановка ничем
            # не отличается от литерального правила: пусть его и применяет.
            return match.group(0)
        parsed = next(
            (
                candidate
                for candidate in parse_word(lemma)
                if "NOUN" in candidate.tag and candidate.tag.case == "nomn"
            ),
            None,
        )
        if parsed is None:
            return match.group(0)
        expanded = safe_inflect(parsed, {case, number}, fallback_word=lemma)
        if abbr[:1].isupper():
            expanded = expanded[:1].upper() + expanded[1:]
        if should_keep_terminal_abbreviation_dot(text, match.end()):
            expanded += "."
        return expanded

    return _DECLINABLE_NOUN_ABBREVIATION_PATTERN.sub(repl, text)


def expand_abbreviations(text: str, options: NormalizeOptions | None = None) -> str:
    active = options or NormalizeOptions()
    text = _expand_language_origin_abbreviations(text)
    if active.enable_contextual_abbreviation_expansion:
        text = _expand_geo_classifier_abbreviations(text)
        text = _expand_declinable_noun_abbreviations(text)
        text = _expand_contextual_etc_abbreviations(text)
        text = _expand_contextual_adjective_abbreviations(text)
        folded_text = text.casefold()
        for (pattern, replacement), literal_hint in zip(
            ABBREVIATION_PATTERNS,
            ABBREVIATION_LITERAL_HINTS,
            strict=True,
        ):
            if literal_hint is not None and literal_hint not in folded_text:
                continue
            updated = pattern.sub(
                lambda match, repl=replacement, source=text: (
                    _expand_rule_preserving_sentence_case(match, repl, source)
                ),
                text,
            )
            if updated != text:
                text = updated
                folded_text = text.casefold()
    if active.enable_initials_expansion:
        text = expand_person_initials(
            text,
            vowel_mode=active.initials_vowel_mode,
            pause_mode=active.initials_pause_mode,
        )
    if active.enable_letter_abbreviation_expansion:
        # A trailing all-caps run in a CamelCase protocol or product name is a
        # real acronym (PostgreSQL, GraphQL, OpenVPN). Split only a terminal
        # run of at least two capitals; ordinary iPhone-like words stay intact.
        # Two lowercase letters must precede the run: a single sandwiched
        # lowercase letter marks a stylized brand name, not a prefix plus an
        # acronym — «NeXT» reads «нэкст», not «ни икс ти».
        text = re.sub(
            r"(?<=[a-zа-яё][a-zа-яё])(?=[A-ZА-ЯЁ]{2,}\b)",
            " ",
            text,
        )
        text = expand_letter_abbreviations(text, vowel_mode=active.letter_vowel_mode)
    return _normalize_contextual_ampersands(text, active)
