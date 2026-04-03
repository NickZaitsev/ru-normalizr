from __future__ import annotations

import num2words

from ._morph import get_morph
from .numerals._num2words import (
    CASE_TO_NUM2WORDS as _CASE_TO_NUM2WORDS,
)
from .numerals._num2words import (
    ORDINAL_GENDER_TO_NUM2WORDS,
    resolve_num2words_case,
)

CASE_TO_NUM2WORDS = _CASE_TO_NUM2WORDS
GENDER_TO_NUM2WORDS = ORDINAL_GENDER_TO_NUM2WORDS


def noun_parse_case(noun_parse) -> str:
    return "loct" if "loc2" in noun_parse.tag else (noun_parse.tag.case or "nomn")


def choose_noun_parse(word: str, prefer_inanimate: bool = True):
    noun_parses = [
        candidate for candidate in get_morph().parse(word.lower()) if "NOUN" in candidate.tag
    ]
    if not noun_parses:
        return None
    if not prefer_inanimate:
        return noun_parses[0]
    inanimate_parses = [candidate for candidate in noun_parses if "inan" in candidate.tag]
    return inanimate_parses[0] if inanimate_parses else noun_parses[0]


def find_first_noun_right(tokens_right: list[str], suffix: str):
    morph = get_morph()
    for token in tokens_right[:4]:
        if any(char in token for char in ".!?…"):
            break
        clean = token.strip(".,!?;:")
        if not clean:
            continue
        parsed = morph.parse(clean)
        noun_candidates = [
            candidate for candidate in parsed if "NOUN" in candidate.tag
        ]
        noun_candidate = None
        if suffix in {"е", "ые", "их", "х", "ми"}:
            noun_candidate = next(
                (
                    candidate
                    for candidate in noun_candidates
                    if "sing" in candidate.tag and "neut" in candidate.tag
                ),
                None,
            )
            if noun_candidate is None:
                noun_candidate = next(
                    (
                        candidate
                        for candidate in noun_candidates
                        if "plur" in candidate.tag
                    ),
                    None,
                )
        if noun_candidate is None:
            noun_candidate = noun_candidates[0] if noun_candidates else None
        if noun_candidate is not None:
            return noun_candidate
        if parsed and parsed[0].tag.POS in {"VERB", "INFN"}:
            break
    return None


def find_left_name_anchor(tokens_left: list[str]):
    morph = get_morph()
    for token in reversed(tokens_left[-4:]):
        clean = token.strip(".,!?;:«»\"'()[]{}")
        if not clean:
            continue
        parsed = morph.parse(clean)
        name_candidates = [
            candidate
            for candidate in parsed
            if "NOUN" in candidate.tag
            and "anim" in candidate.tag
            and any(marker in candidate.tag for marker in ("Name", "Surn", "Patr"))
        ]
        noun_candidate = next(
            (
                candidate
                for candidate in name_candidates
                if "Fixd" not in candidate.tag
            ),
            None,
        )
        if noun_candidate is None:
            noun_candidate = name_candidates[0] if name_candidates else None
        if noun_candidate is not None:
            return noun_candidate
    return None


def normalize_ordinal_suffix_defaults(
    case: str,
    suffix: str,
) -> tuple[str, str | None, bool]:
    default_case = case
    default_gender: str | None = "masc"
    default_plural = False
    if suffix in {"я", "ая"}:
        default_gender = "femn"
        default_case = "nomn"
    elif suffix in {"е", "ее", "ое"}:
        default_gender = "neut"
        default_case = "nomn"
    elif suffix in {"ые", "их"}:
        default_gender = None
        default_case = "nomn"
        default_plural = True
    elif suffix in {"го", "ого"}:
        default_case = "gent"
    elif suffix in {"му", "ому"}:
        default_case = "datv"
    elif suffix in {"м", "ом", "ем"}:
        default_case = "loct"
    elif suffix in {"ю", "ую"}:
        default_case = "accs"
        default_gender = "femn"
    elif suffix in {"ей"}:
        default_case = "ablt" if case == "ablt" else "loct"
        default_gender = "femn"
    elif suffix in {"ым", "им"}:
        default_case = "ablt"
    return default_case, default_gender, default_plural


def resolve_ordinal_suffix_case(
    case: str,
    suffix: str,
    tokens_right: list[str],
    gender: str,
) -> tuple[str, str]:
    morph = get_morph()
    case_from_suffix = None
    resolved_gender = gender
    if suffix in {"го", "ого"}:
        case_from_suffix = "gent"
    elif suffix in {"му", "ому"}:
        case_from_suffix = "datv"
    elif suffix in {"ю", "ую"}:
        case_from_suffix = "accs"
        resolved_gender = "femn"
    if suffix in {"м", "ом", "ем"}:
        if tokens_right:
            next_parse = morph.parse(tokens_right[0].strip(".,!?;:"))[0]
            case_from_suffix = "loct" if "sing" in next_parse.tag else "datv"
        else:
            case_from_suffix = "loct"
    return case_from_suffix or case, resolved_gender


def resolve_ordinal_plural(
    suffix: str,
    case: str,
    tokens_right: list[str],
) -> bool:
    morph = get_morph()
    plural = suffix in ("х", "ми", "е", "м", "ые", "их") and not (
        suffix == "м" and case == "loct"
    )
    if suffix in {"е", "ее", "ое"} and tokens_right:
        next_clean = tokens_right[0].strip(".,!?;:")
        if next_clean:
            next_parse = morph.parse(next_clean)[0]
            if "sing" in next_parse.tag and "neut" in next_parse.tag:
                plural = False
    return plural


def render_ordinal(
    number: int,
    case: str = "nomn",
    gender: str | None = None,
    plural: bool = False,
    inanimate: bool = False,
) -> str:
    generation_case = case
    if case == "accs" and not plural and inanimate and gender in {"masc", "neut"}:
        generation_case = "nomn"

    kwargs: dict[str, str | bool] = {
        "lang": "ru",
        "to": "ordinal",
        "case": resolve_num2words_case(generation_case),
    }
    if plural:
        kwargs["plural"] = True
    elif gender in GENDER_TO_NUM2WORDS:
        kwargs["gender"] = GENDER_TO_NUM2WORDS[gender]

    try:
        return num2words.num2words(number, **kwargs)
    except Exception:
        pass

    try:
        ordinal = num2words.num2words(number, lang="ru", to="ordinal")
    except Exception:
        return str(number)

    words = ordinal.split()
    if not words:
        return ordinal

    parsed = get_morph().parse(words[-1])
    if not parsed:
        return ordinal

    target_tags = {generation_case}
    if plural:
        target_tags.add("plur")
    elif gender:
        target_tags.add(gender)
    inflected = parsed[0].inflect(target_tags)
    if inflected:
        words[-1] = inflected.word
    return " ".join(words)


def render_ordinal_from_noun_word(
    number: int,
    noun_word: str,
    *,
    prefer_inanimate: bool = True,
    singularize_plural: bool = False,
) -> str | None:
    noun_parse = choose_noun_parse(noun_word, prefer_inanimate=prefer_inanimate)
    if noun_parse is None:
        return None
    return render_ordinal_from_noun_parse(
        number,
        noun_parse,
        singularize_plural=singularize_plural,
    )


def render_ordinal_from_noun_parse(
    number: int,
    noun_parse,
    *,
    singularize_plural: bool = False,
) -> str:
    case = noun_parse_case(noun_parse)
    gender = noun_parse.tag.gender or "masc"
    plural = "plur" in noun_parse.tag and not singularize_plural
    inanimate = "inan" in noun_parse.tag
    return render_ordinal(
        number,
        case=case,
        gender=gender,
        plural=plural,
        inanimate=inanimate,
    )
