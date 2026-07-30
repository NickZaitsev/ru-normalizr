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


#: pymorphy reports secondary cases for the nouns that have them (partitive
#: "чаю", locative "в лесу", vocative "Пап!") and call sites pass that case
#: through unchanged. Numerals have no such forms, so a secondary case must be
#: read as its primary one before rendering. Otherwise num2words is skipped and
#: pymorphy answers a request it cannot satisfy with an arbitrary matching form.
SECONDARY_CASE_TO_PRIMARY = {
    "gen1": "gent",
    "gen2": "gent",
    "acc2": "accs",
    "loc1": "loct",
    "loc2": "loct",
    "voct": "nomn",
}


def resolve_num2words_case(case: str, default: str = "nominative") -> str:
    return CASE_TO_NUM2WORDS.get(case, default)


def resolve_primary_case(case: str) -> str:
    """Map a pymorphy secondary case onto the primary case numerals inflect for."""
    return SECONDARY_CASE_TO_PRIMARY.get(case, case)
