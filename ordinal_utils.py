from __future__ import annotations

import num2words

from ._morph import get_morph

CASE_TO_NUM2WORDS = {
    "nomn": "nominative",
    "gent": "genitive",
    "datv": "dative",
    "accs": "accusative",
    "ablt": "instrumental",
    "loct": "prepositional",
}
GENDER_TO_NUM2WORDS = {"masc": "m", "femn": "f", "neut": "n"}


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
        "case": CASE_TO_NUM2WORDS.get(generation_case, "nominative"),
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
