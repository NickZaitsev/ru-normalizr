"""Postal address abbreviations: «ул. Полевая, д. 10, корп. 2, кв. 35».

The stage runs before the numerals stage on purpose. Left in place, the dot of
«д.» reads as a sentence end, so the numerals stage capitalizes the house number
(«д. Десять») and a TTS engine inserts a sentence pause in the middle of an
address. Expanding the abbreviation removes the dot and the false boundary with
it.

Only the element the preposition actually governs is inflected; the rest of the
chain are appositions and stay nominative, which is how a Russian address is
read aloud: «по улице Лесной, дом десять».
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ._morph import MorphParse, canonicalize_case, parse_word, select_parse
from .numerals._helpers import safe_inflect
from .options import NormalizeOptions

_NAMED = "named"
_NUMBERED = "numbered"


@dataclass(frozen=True, slots=True)
class AddressAbbreviation:
    """One postal abbreviation and the shape of the value that follows it."""

    lemma: str
    kind: str
    #: Ambiguous abbreviations also spell out non-address words («стр.» is a
    #: page far more often than a building), so they only expand when another,
    #: unambiguous address element sits in the same chain.
    ambiguous: bool = False


ADDRESS_ABBREVIATIONS: dict[str, AddressAbbreviation] = {
    "ул.": AddressAbbreviation("улица", _NAMED),
    "просп.": AddressAbbreviation("проспект", _NAMED),
    "пр-т": AddressAbbreviation("проспект", _NAMED),
    "пр-кт": AddressAbbreviation("проспект", _NAMED),
    "пер.": AddressAbbreviation("переулок", _NAMED),
    "пл.": AddressAbbreviation("площадь", _NAMED),
    "наб.": AddressAbbreviation("набережная", _NAMED),
    "ш.": AddressAbbreviation("шоссе", _NAMED),
    "б-р": AddressAbbreviation("бульвар", _NAMED),
    "бул.": AddressAbbreviation("бульвар", _NAMED),
    "мкр.": AddressAbbreviation("микрорайон", _NAMED),
    "мкрн.": AddressAbbreviation("микрорайон", _NAMED),
    "туп.": AddressAbbreviation("тупик", _NAMED),
    "кв-л": AddressAbbreviation("квартал", _NAMED),
    "дер.": AddressAbbreviation("деревня", _NAMED),
    "д.": AddressAbbreviation("дом", _NUMBERED, ambiguous=True),
    "корп.": AddressAbbreviation("корпус", _NUMBERED),
    "кор.": AddressAbbreviation("корпус", _NUMBERED, ambiguous=True),
    "к.": AddressAbbreviation("корпус", _NUMBERED, ambiguous=True),
    "кв.": AddressAbbreviation("квартира", _NUMBERED),
    "стр.": AddressAbbreviation("строение", _NUMBERED, ambiguous=True),
    "влд.": AddressAbbreviation("владение", _NUMBERED),
    "вл.": AddressAbbreviation("владение", _NUMBERED, ambiguous=True),
    "пом.": AddressAbbreviation("помещение", _NUMBERED),
    "оф.": AddressAbbreviation("офис", _NUMBERED),
    "эт.": AddressAbbreviation("этаж", _NUMBERED),
    "лит.": AddressAbbreviation("литера", _NUMBERED, ambiguous=True),
}

#: Cases a preposition can assign, most likely first. Ambiguous prepositions
#: («в дом» vs «в доме») list every option so the following proper name can
#: settle the choice; when it cannot, the first entry wins.
ADDRESS_PREPOSITION_CASES: dict[str, tuple[str, ...]] = {
    "в": ("loct", "accs"),
    "во": ("loct", "accs"),
    "на": ("loct", "accs"),
    "за": ("ablt", "accs"),
    "под": ("ablt", "accs"),
    "по": ("datv",),
    "к": ("datv",),
    "ко": ("datv",),
    "с": ("gent",),
    "со": ("gent",),
    "из": ("gent",),
    "от": ("gent",),
    "до": ("gent",),
    "у": ("gent",),
    "около": ("gent",),
    "возле": ("gent",),
    "напротив": ("gent",),
    "вдоль": ("gent",),
    "мимо": ("gent",),
    "вблизи": ("gent",),
    "при": ("loct",),
    "перед": ("ablt",),
    "между": ("ablt",),
    "через": ("accs",),
}

_ABBREVIATION_ALTERNATION = "|".join(
    re.escape(abbr)
    for abbr in sorted(ADDRESS_ABBREVIATIONS, key=lambda value: (-len(value), value))
)
_NAME_VALUE = r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁа-яё][а-яё]*)*(?:[ \t]+[А-ЯЁ][а-яё]+)?"
_NUMBER_VALUE = r"\d+(?:[/-]\d+)?[А-ЯЁа-яёA-Za-z]?(?!\w)"

# The abbreviation alternation is the only case-insensitive part: the value
# patterns must keep requiring a real capital letter to tell «ул. Лесной» from
# a stray lowercase word.
_ADDRESS_ELEMENT_PATTERN = re.compile(
    rf"(?<![\w.])(?P<abbr>(?i:{_ABBREVIATION_ALTERNATION}))(?P<gap>[ \t]*)"
    rf"(?:(?P<name>{_NAME_VALUE})|(?P<number>{_NUMBER_VALUE}))"
)
_ADDRESS_HINT_PATTERN = re.compile(rf"(?i:{_ABBREVIATION_ALTERNATION})")
_CHAIN_GAP_PATTERN = re.compile(r"[ \t]*[,;]?[ \t]*")
_PRECEDING_WORD_PATTERN = re.compile(r"(?P<word>[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*)[ \t]*\Z")
_NOUN_POS = frozenset({"NOUN"})
_SUBSTANTIVE_POS = {"NOUN", "ADJF"}


def _specification(match: re.Match[str]) -> AddressAbbreviation | None:
    spec = ADDRESS_ABBREVIATIONS.get(match.group("abbr").lower())
    if spec is None:
        return None
    kind = _NAMED if match.group("name") is not None else _NUMBERED
    return spec if spec.kind == kind else None


def _preposition_cases(text: str, chain_start: int) -> tuple[str, ...]:
    preceding = _PRECEDING_WORD_PATTERN.search(text, 0, chain_start)
    if preceding is None:
        return ()
    return ADDRESS_PREPOSITION_CASES.get(preceding.group("word").lower(), ())


def _name_cases(name: str) -> frozenset[str]:
    head = name.split()[0]
    return frozenset(
        canonicalize_case(parsed.tag.case)
        for parsed in parse_word(head)
        if parsed.tag.case is not None
    )


def _target_case(text: str, chain_start: int, match: re.Match[str]) -> str:
    candidates = _preposition_cases(text, chain_start)
    if not candidates:
        return "nomn"
    name = match.group("name")
    if name is not None:
        available = _name_cases(name)
        # A nominative reading means the name is an uninflected apposition
        # («в микрорайоне Северный»), so it carries no case signal at all. Only
        # a name that has already been declined can override the preposition.
        if "nomn" not in available:
            for case in candidates:
                if case in available:
                    return case
    return candidates[0]


def _inflect_lemma(lemma: str, case: str) -> str:
    if case == "nomn":
        return lemma
    parsed: MorphParse | None = select_parse(lemma, pos=_NOUN_POS)
    if parsed is None:
        # «набережная» is a substantivized adjective, not a noun.
        parsed = select_parse(lemma, pos=_SUBSTANTIVE_POS)
    if parsed is None:
        return lemma
    return safe_inflect(parsed, {case}, fallback_word=lemma, pos_filter=_SUBSTANTIVE_POS)


def _match_case_style(expansion: str, abbr: str) -> str:
    if not abbr[:1].isupper():
        return expansion
    return expansion[:1].upper() + expansion[1:]


def _build_chains(text: str, matches: list[re.Match[str]]) -> list[list[re.Match[str]]]:
    chains: list[list[re.Match[str]]] = []
    for match in matches:
        if chains and _CHAIN_GAP_PATTERN.fullmatch(
            text, chains[-1][-1].end(), match.start()
        ):
            chains[-1].append(match)
            continue
        chains.append([match])
    return chains


def expand_address_abbreviations(
    text: str, options: NormalizeOptions | None = None
) -> str:
    """Expand postal abbreviations that carry an address value."""

    active = options or NormalizeOptions()
    if not (
        active.enable_abbreviation_expansion
        and active.enable_contextual_abbreviation_expansion
    ):
        return text
    if _ADDRESS_HINT_PATTERN.search(text) is None:
        return text

    matches = [
        match
        for match in _ADDRESS_ELEMENT_PATTERN.finditer(text)
        if _specification(match) is not None
    ]
    if not matches:
        return text

    pieces: list[str] = []
    last_end = 0
    for chain in _build_chains(text, matches):
        specifications = [_specification(match) for match in chain]
        has_unambiguous = any(
            spec is not None and not spec.ambiguous for spec in specifications
        )
        chain_start = chain[0].start()
        is_chain_head = True
        for match, spec in zip(chain, specifications, strict=True):
            if spec is None or (spec.ambiguous and not has_unambiguous):
                continue
            case = _target_case(text, chain_start, match) if is_chain_head else "nomn"
            is_chain_head = False
            expansion = _match_case_style(
                _inflect_lemma(spec.lemma, case), match.group("abbr")
            )
            value = match.group("name") or match.group("number")
            pieces.append(text[last_end : match.start()])
            pieces.append(f"{expansion} {value}")
            last_end = match.end()

    if not pieces:
        return text
    pieces.append(text[last_end:])
    return "".join(pieces)
