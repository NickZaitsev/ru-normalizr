from __future__ import annotations

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
