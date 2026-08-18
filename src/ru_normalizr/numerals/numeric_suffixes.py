from __future__ import annotations

import functools
import logging
import re
from dataclasses import dataclass
from typing import Literal

from .._log_once import warn_once
from .._morph import canonicalize_case, parse_word, select_parse
from ..ordinal_utils import render_ordinal
from ..preprocess_utils import NEGATIVE_NUMBER_PLACEHOLDER
from ..text_context import PUNCT_STRIP, simple_tokenize
from ..text_scan import compile_scan
from ._constants import PREP_CASE
from ._helpers import get_numeral_case, inflect_numeral_string

logger = logging.getLogger(__name__)

ORDINAL_SUFFIXES = frozenset(
    {
        "й",
        "ый",
        "ий",
        "ой",
        "я",
        "ая",
        "е",
        "ее",
        "ое",
        "ые",
        "ых",
        "ыми",
        "го",
        "ого",
        "му",
        "ому",
        "м",
        "ом",
        "ем",
        "ю",
        "ую",
        "ей",
        "ым",
        "им",
    }
)

# These spellings are non-standard for cardinal numerals, but occur frequently
# in source material.  The registry is deliberately closed: a short arbitrary
# Cyrillic tail must not become a grammatical instruction by accident.
CARDINAL_SUFFIXES = frozenset(
    {"ти", "и", "ми", "х", "мя", "тью", "ух", "ех", "ёх", "ум", "ём", "у"}
)
NUMERIC_SUFFIXES = ORDINAL_SUFFIXES | CARDINAL_SUFFIXES

_SUFFIX_ALTERNATION = "|".join(
    re.escape(value) for value in sorted(NUMERIC_SUFFIXES, key=lambda item: (-len(item), item))
)
# The trailing hard sign covers pre-reform spellings («3-хъ», «5-ти» stays
# as is): the ending resolves without it and the sign is re-attached after a
# consonant. The hyphen lookahead leaves «17-ти-летняя» to the compound
# adjective rule, which folds the numeral into the word.
NUMERIC_SUFFIX_PATTERN = compile_scan(
    rf"(?<![\w,-])(?<!\d[.,])(?P<sign>{re.escape(NEGATIVE_NUMBER_PLACEHOLDER)}|-)?"
    rf"(?P<number>\d+)-(?P<suffix>{_SUFFIX_ALTERNATION})(?P<hard>ъ)?(?!\w)(?!-[а-яё])",
    re.IGNORECASE | re.UNICODE,
)

_CASES = ("nomn", "gent", "datv", "accs", "ablt", "loct")
_CASE_ORDER = {case: index for index, case in enumerate(_CASES)}
_TEXT_START_PREFIX_CHARS = " \t\r\n\"'«„“([{"
_OB_BEFORE_CONSONANT_PATTERN = compile_scan(
    r"\bоб(?=\s+[бвгджзйклмнпрстфхцчшщ])", re.IGNORECASE
)
_COPULA_ORDINAL_SUFFIXES = frozenset({"м", "ом", "ем", "ым", "им"})
_ORDINAL_ONLY_SUFFIXES = ORDINAL_SUFFIXES - {"ми"}


@dataclass(frozen=True, slots=True)
class NumericSuffixCandidate:
    reading: str
    kind: Literal["cardinal", "ordinal"]
    case: str
    gender: str | None = None
    plural: bool = False
    animate: bool | None = None
    exact: bool = True


@dataclass(frozen=True, slots=True)
class _NounFeatures:
    case: str
    gender: str | None
    plural: bool
    animate: bool | None


def _last_word(reading: str) -> str:
    words = reading.casefold().split()
    return words[-1] if words else ""


def _is_rendered_reading(reading: str) -> bool:
    return bool(reading) and not any(char.isdecimal() for char in reading)


@functools.lru_cache(maxsize=16384)
def generate_numeric_suffix_candidates(
    number: int, suffix: str
) -> tuple[NumericSuffixCandidate, ...]:
    suffix_key = suffix.casefold()
    candidates: dict[tuple[object, ...], NumericSuffixCandidate] = {}

    for case in _CASES:
        for gender in (None, "masc", "femn", "neut"):
            for animate in (None, False, True):
                reading = inflect_numeral_string(
                    str(number), case, gender=gender, animate=animate
                )
                if not _is_rendered_reading(reading):
                    continue
                candidate = NumericSuffixCandidate(
                    reading=reading,
                    kind="cardinal",
                    case=case,
                    gender=gender,
                    animate=animate,
                    exact=_last_word(reading).endswith(suffix_key),
                )
                key = (
                    candidate.reading,
                    candidate.kind,
                    candidate.case,
                    candidate.gender,
                    candidate.plural,
                    candidate.animate,
                )
                candidates[key] = candidate

        for gender in ("masc", "femn", "neut"):
            for inanimate in (False, True):
                reading = render_ordinal(
                    number,
                    case=case,
                    gender=gender,
                    plural=False,
                    inanimate=inanimate,
                )
                if not _is_rendered_reading(reading):
                    continue
                candidate = NumericSuffixCandidate(
                    reading=reading,
                    kind="ordinal",
                    case=case,
                    gender=gender,
                    plural=False,
                    animate=not inanimate,
                    exact=_last_word(reading).endswith(suffix_key),
                )
                key = (
                    candidate.reading,
                    candidate.kind,
                    candidate.case,
                    candidate.gender,
                    candidate.plural,
                    candidate.animate,
                )
                candidates[key] = candidate

        for inanimate in (False, True):
            reading = render_ordinal(
                number,
                case=case,
                gender=None,
                plural=True,
                inanimate=inanimate,
            )
            if not _is_rendered_reading(reading):
                continue
            candidate = NumericSuffixCandidate(
                reading=reading,
                kind="ordinal",
                case=case,
                plural=True,
                animate=not inanimate,
                exact=_last_word(reading).endswith(suffix_key),
            )
            key = (
                candidate.reading,
                candidate.kind,
                candidate.case,
                candidate.gender,
                candidate.plural,
                candidate.animate,
            )
            candidates[key] = candidate

    return tuple(candidates.values())


def _noun_features(
    tokens: list[str], *, reverse: bool = False, names_only: bool = False
) -> tuple[_NounFeatures, ...]:
    result: list[_NounFeatures] = []
    window = list(reversed(tokens[-4:])) if reverse else tokens[:4]
    for token in window:
        if any(mark in token for mark in ".!?…"):
            break
        clean = token.strip(".,!?;:«»\"'()[]{}")
        if not clean:
            continue
        if clean.casefold() in PREP_CASE:
            continue
        parses = parse_word(clean)
        noun_parses = [
            candidate
            for candidate in parses
            if "NOUN" in candidate.tag
            and (
                not names_only
                or any(mark in candidate.tag for mark in {"Name", "Surn", "Patr"})
            )
        ]
        for candidate in noun_parses:
            result.append(
                _NounFeatures(
                    case=canonicalize_case(candidate.tag.case),
                    gender=candidate.tag.gender,
                    plural="plur" in candidate.tag,
                    animate=(
                        True
                        if candidate.tag.animacy == "anim"
                        else (False if candidate.tag.animacy == "inan" else None)
                    ),
                )
            )
        if noun_parses:
            break
        if parses and parses[0].tag.POS in {"VERB", "INFN"}:
            break
    return tuple(result)


def _has_copula_before(tokens: list[str]) -> bool:
    for token in reversed(tokens[-6:]):
        clean = token.strip(PUNCT_STRIP)
        if not clean:
            continue
        if any(char in token for char in ".!?;:"):
            break
        parsed = select_parse(parse_word(clean), pos={"VERB", "INFN"})
        if parsed is not None and parsed.normal_form == "быть":
            return True
    return False


def _cardinal_government_score(
    number: int,
    candidate: NumericSuffixCandidate,
    noun: _NounFeatures,
) -> int:
    if candidate.kind != "cardinal" or candidate.case not in {"nomn", "accs"}:
        return 0
    tail = number % 100
    last_digit = number % 10
    if candidate.case == "accs" and candidate.animate:
        compatible = noun.case in {"accs", "gent"} and noun.plural == (number != 1)
    elif last_digit == 1 and tail != 11:
        compatible = not noun.plural and noun.case in {"nomn", "accs", "gent"}
    elif last_digit in {2, 3, 4} and tail not in {12, 13, 14}:
        compatible = not noun.plural and noun.case == "gent"
    else:
        compatible = noun.plural and noun.case == "gent"
    return 4 if compatible else -4


def _candidate_score(
    candidate: NumericSuffixCandidate,
    *,
    number: int,
    context_case: str,
    noun_features: tuple[_NounFeatures, ...],
) -> int:
    score = 8 if candidate.case == context_case else 0
    best_noun_score = 0
    for noun in noun_features:
        noun_score = 0
        if candidate.case == noun.case:
            noun_score += 5
        noun_score += _cardinal_government_score(number, candidate, noun)
        if (
            candidate.case == "accs"
            and noun.animate is not None
            and candidate.animate == noun.animate
        ):
            noun_score += 1
        best_noun_score = max(best_noun_score, noun_score)
    return score + best_noun_score


def _agreement_score(
    candidate: NumericSuffixCandidate,
    noun_features: tuple[_NounFeatures, ...],
) -> int:
    if candidate.kind != "ordinal":
        return 0
    best_score = 0
    for noun in noun_features:
        score = 3 if candidate.plural == noun.plural else 0
        if not candidate.plural and candidate.gender == noun.gender:
            score += 2
        best_score = max(best_score, score)
    return best_score


_MONTH_LEMMAS = frozenset(
    {
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


def _month_follows(tokens_right: list[str]) -> bool:
    for token in tokens_right[:2]:
        clean = token.strip(PUNCT_STRIP)
        if not clean:
            continue
        parsed = select_parse(parse_word(clean), pos={"NOUN"})
        return parsed is not None and parsed.normal_form in _MONTH_LEMMAS
    return False


_COORDINATORS = frozenset({"и", "или", "ни"})
_SUFFIXED_NUMBER_TOKEN = compile_scan(r"\A(?P<number>\d+)-?(?P<suffix>[а-яё]{1,3})\Z", re.IGNORECASE)


def _coordinated_suffix_numbers(
    tokens_left: list[str], tokens_right: list[str], suffix: str
) -> list[int]:
    """Numbers coordinated with this one and written with the same suffix.

    Only the immediate neighbour across a coordinator is inspected, so the scan
    stays constant-time per match.
    """
    # The tokenizer splits "2-м" into "2", "-", "м", so a sibling spans up to
    # three tokens next to the coordinator.
    neighbours: list[list[str]] = []
    if tokens_right and tokens_right[0].strip(PUNCT_STRIP).casefold() in _COORDINATORS:
        neighbours.append(tokens_right[1:4])
    if tokens_left and tokens_left[-1].strip(PUNCT_STRIP).casefold() in _COORDINATORS:
        neighbours.append(tokens_left[-4:-1])

    numbers: list[int] = []
    for neighbour in neighbours:
        joined = "".join(token.strip(PUNCT_STRIP) for token in neighbour)
        sibling = _SUFFIXED_NUMBER_TOKEN.match(joined)
        if sibling is not None and sibling.group("suffix").casefold() == suffix.casefold():
            numbers.append(int(sibling.group("number")))
    return numbers


def _kind_forced_by_coordination(
    suffix: str,
    context_case: str,
    tokens_left: list[str],
    tokens_right: list[str],
) -> str | None:
    """Reading imposed on an ambiguous numeral by a coordinated sibling.

    Coordinated members share one reading: in "в 1-м и 2-м кварталах" the
    sibling "2-м" has no cardinal form in the locative, which settles the
    otherwise ambiguous "1-м" ("одном" vs "первом") as an ordinal.
    """
    for number in _coordinated_suffix_numbers(tokens_left, tokens_right, suffix):
        kinds = {
            candidate.kind
            for candidate in generate_numeric_suffix_candidates(number, suffix)
            if candidate.exact and candidate.case == context_case
        }
        if len(kinds) == 1:
            return next(iter(kinds))
    return None


def _candidate_sort_key(candidate: NumericSuffixCandidate) -> tuple[object, ...]:
    return (
        0 if candidate.kind == "cardinal" else 1,
        _CASE_ORDER.get(candidate.case, len(_CASE_ORDER)),
        0 if candidate.gender is None else 1,
        candidate.reading,
    )


def _fallback_cardinal(
    number_text: str,
    *,
    context_case: str,
    noun_features: tuple[_NounFeatures, ...],
) -> str:
    noun = next(
        (candidate for candidate in noun_features if candidate.case == context_case),
        noun_features[0] if noun_features else None,
    )
    return inflect_numeral_string(
        number_text,
        context_case,
        gender=noun.gender if noun and not noun.plural else None,
        animate=noun.animate if noun and context_case == "accs" else None,
    )


def resolve_numeric_suffix(
    number_text: str,
    suffix: str,
    *,
    tokens_left: list[str],
    tokens_right: list[str],
) -> str:
    try:
        number = int(number_text)
    except ValueError as exc:
        logger.debug("numeric suffix integer conversion failed for %r: %s", number_text, exc)
        return number_text

    try:
        context_tokens = [*tokens_left, number_text, *tokens_right]
        context_case = get_numeral_case(context_tokens, len(tokens_left))
        if (
            suffix.casefold() in _COPULA_ORDINAL_SUFFIXES
            and _has_copula_before(tokens_left)
        ):
            # A copular predicate with a written ordinal is instrumental:
            # "он был 2-м после лидера".  This is a grammatical predicate
            # context, not a special case for the particular verb form.
            context_case = "ablt"
        if (
            suffix.casefold() in _ORDINAL_ONLY_SUFFIXES
            and context_case == "accs"
            and tokens_left
            and tokens_left[-1].casefold().strip(PUNCT_STRIP) in {"в", "во"}
            and not _noun_features(tokens_right)
        ):
            # ``в 3-м`` can end a clause without an overt head noun.  The
            # standard ``-м`` spelling is still ordinal, and this residual
            # preposition ambiguity is locative rather than accusative.
            context_case = "loct"
        right_noun_features = _noun_features(tokens_right)
        left_name_features = _noun_features(tokens_left, reverse=True, names_only=True)
        noun_features = right_noun_features or left_name_features
        if not right_noun_features and left_name_features:
            context_case = left_name_features[0].case
        exact = [
            candidate
            for candidate in generate_numeric_suffix_candidates(number, suffix)
            if candidate.exact
        ]
    except Exception as exc:  # pragma: no cover - dependency boundary
        warn_once(
            logger,
            f"suffix-morphology:{number_text}:{suffix}",
            "numeric suffix morphology failed for %r: %s",
            number_text,
            exc,
        )
        return inflect_numeral_string(number_text, "nomn")
    if not exact:
        return _fallback_cardinal(
            number_text,
            context_case=context_case,
            noun_features=noun_features,
        )

    scored = [
        (
            _candidate_score(
                candidate,
                number=number,
                context_case=context_case,
                noun_features=noun_features,
            ),
            candidate,
        )
        for candidate in exact
    ]
    best_score = max(score for score, _candidate in scored)
    best = [candidate for score, candidate in scored if score == best_score]
    if len({candidate.kind for candidate in best}) > 1:
        forced_kind = _kind_forced_by_coordination(
            suffix, context_case, tokens_left, tokens_right
        )
        if forced_kind is not None:
            best = [candidate for candidate in best if candidate.kind == forced_kind]
    if (
        any(candidate.kind == "ordinal" for candidate in best)
        and _month_follows(tokens_right)
    ):
        # A suffixed day before a month name is an ordinal: «1-го октября» is
        # «первого октября», never the genitive cardinal «одного октября».
        best = [candidate for candidate in best if candidate.kind == "ordinal"]
    elif any(candidate.kind == "cardinal" for candidate in best):
        best = [candidate for candidate in best if candidate.kind == "cardinal"]
    best_agreement = max(_agreement_score(candidate, noun_features) for candidate in best)
    best = [
        candidate
        for candidate in best
        if _agreement_score(candidate, noun_features) == best_agreement
    ]
    readings = {candidate.reading for candidate in best}
    if len(readings) == 1:
        return next(iter(readings))
    return min(best, key=_candidate_sort_key).reading


def normalize_numeric_suffixes(
    text: str, *, capitalize_text_start: bool = False
) -> str:
    text_start_end = len(text) - len(text.lstrip(_TEXT_START_PREFIX_CHARS))

    def repl(match: re.Match[str]) -> str:
        number_text = match.group("number")
        suffix = match.group("suffix").casefold()
        context_left = text[max(0, match.start() - 60) : match.start()]
        context_right = text[match.end() : match.end() + 60]
        reading = resolve_numeric_suffix(
            number_text,
            suffix,
            tokens_left=simple_tokenize(context_left),
            tokens_right=simple_tokenize(context_right),
        )
        if match.group("hard") and reading and reading[-1] not in "аеёиоуыэюяьъ":
            # Pre-reform orthography closes a consonant-final word with «ъ».
            reading += "ъ"
        if match.group("sign"):
            reading = f"минус {reading}"
        if (
            capitalize_text_start
            and match.start() <= text_start_end
            and reading[:1].isalpha()
        ):
            reading = reading[:1].upper() + reading[1:]
        return reading

    normalized = NUMERIC_SUFFIX_PATTERN.sub(repl, text)
    if normalized == text:
        return normalized

    def fix_ob(match: re.Match[str]) -> str:
        return "О" if match.group(0)[:1].isupper() else "о"

    return _OB_BEFORE_CONSONANT_PATTERN.sub(fix_ob, normalized)


def is_numeric_suffix(value: str) -> bool:
    return value.casefold().strip(".") in NUMERIC_SUFFIXES
