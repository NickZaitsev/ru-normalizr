from __future__ import annotations

from .._morph import canonicalize_case

CASE_TO_NUM2WORDS = {
    "nomn": "nominative",
    "gent": "genitive",
    "datv": "dative",
    "accs": "accusative",
    "ablt": "instrumental",
    "loct": "prepositional",
}

ORDINAL_GENDER_TO_NUM2WORDS = {
    "masc": "m",
    "femn": "f",
    "neut": "n",
}

CARDINAL_GENDER_TO_NUM2WORDS = {
    "masc": "masculine",
    "femn": "feminine",
    "neut": "neuter",
}


def resolve_num2words_case(case: str, default: str = "nominative") -> str:
    return CASE_TO_NUM2WORDS.get(case, default)


def resolve_primary_case(case: str) -> str:
    """Map a pymorphy secondary case onto the primary case numerals inflect for."""
    return canonicalize_case(case)
