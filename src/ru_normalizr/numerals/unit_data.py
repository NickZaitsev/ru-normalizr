from __future__ import annotations

from dataclasses import dataclass

from .._morph import select_parse
from .unit_registry import PrefixDefinition, UnitDescriptor, UnitMorphology

PREFIXES = {
    "nano": PrefixDefinition("nano", "нано", -9, "n", ("н",)),
    "micro": PrefixDefinition("micro", "микро", -6, "µ", ("мк",)),
    "milli": PrefixDefinition("milli", "милли", -3, "m", ("м",)),
    "kilo": PrefixDefinition("kilo", "кило", 3, "k", ("к",)),
    "mega": PrefixDefinition("mega", "мега", 6, "M", ("М",)),
    "giga": PrefixDefinition("giga", "гига", 9, "G", ("Г",)),
    "tera": PrefixDefinition("tera", "тера", 12, "T", ("Т",)),
}


@dataclass(frozen=True)
class PrefixableUnit:
    id: str
    lemma: str
    gender: str
    latin_symbol: str
    cyrillic_symbol: str
    allowed_prefixes: tuple[str, ...]


# This is deliberately bounded data, not a Cartesian product of every SI
# prefix and every known unit. Additions require an explicit family decision.
PREFIXABLE_UNITS = (
    PrefixableUnit("pascal", "паскаль", "masc", "Pa", "Па", ("milli", "kilo", "mega")),
    PrefixableUnit("newton", "ньютон", "masc", "N", "Н", ("milli", "kilo", "mega")),
    PrefixableUnit("hertz", "герц", "masc", "Hz", "Гц", ("milli", "kilo", "mega", "giga")),
    PrefixableUnit("gram", "грамм", "masc", "g", "г", ("nano", "micro", "milli", "mega")),
    PrefixableUnit("metre", "метр", "masc", "m", "м", ("nano", "micro", "milli")),
    PrefixableUnit("second", "секунда", "femn", "s", "с", ("nano", "micro", "milli", "mega")),
    PrefixableUnit("litre", "литр", "masc", "L", "л", ("milli", "mega")),
    PrefixableUnit("farad", "фарад", "masc", "F", "Ф", ("nano", "micro", "milli", "mega")),
)

_CASES = ("nomn", "gent", "datv", "accs", "ablt", "loct")


def _generated_morphology(
    unit: PrefixableUnit,
    prefix: PrefixDefinition,
    morphology_by_lemma: dict[str, UnitMorphology],
) -> UnitMorphology:
    lemma = f"{prefix.spoken}{unit.lemma}"
    base_morphology = morphology_by_lemma.get(unit.lemma)
    if base_morphology is not None and base_morphology.paradigm:
        return UnitMorphology(
            expected_normal_form=lemma,
            paradigm=tuple(
                (case, number, f"{prefix.spoken}{word}")
                for case, number, word in base_morphology.paradigm
            ),
        )

    parsed = select_parse(
        unit.lemma,
        pos="NOUN",
        required_grammemes={"inan"},
        forbidden_grammemes={"Coun"},
        gender=unit.gender,
    )
    if parsed is None:
        return UnitMorphology(expected_normal_form=lemma)
    forms: list[tuple[str, str, str]] = []
    for number in ("sing", "plur"):
        for case in _CASES:
            inflected = parsed.inflect({case, number})
            if inflected is None:
                return UnitMorphology(expected_normal_form=lemma)
            forms.append((case, number, f"{prefix.spoken}{inflected.word}"))
    return UnitMorphology(expected_normal_form=lemma, paradigm=tuple(forms))


def generated_prefixed_aliases(
    morphology_by_lemma: dict[str, UnitMorphology],
) -> dict[str, UnitDescriptor]:
    aliases: dict[str, UnitDescriptor] = {}
    for unit in PREFIXABLE_UNITS:
        for prefix_id in unit.allowed_prefixes:
            prefix = PREFIXES[prefix_id]
            lemma = f"{prefix.spoken}{unit.lemma}"
            morphology = morphology_by_lemma.get(lemma)
            if morphology is None:
                morphology = _generated_morphology(
                    unit, prefix, morphology_by_lemma
                )
            descriptor = UnitDescriptor(
                lemma=lemma,
                gender=unit.gender,
                category="measure",
                morphology=morphology or UnitMorphology(expected_normal_form=lemma),
            )
            if prefix.latin is not None:
                aliases[f"{prefix.latin}{unit.latin_symbol}"] = descriptor
                if prefix.id == "micro":
                    aliases[f"μ{unit.latin_symbol}"] = descriptor
                    aliases[f"u{unit.latin_symbol}"] = descriptor
            for localized_prefix in prefix.cyrillic:
                aliases[f"{localized_prefix}{unit.cyrillic_symbol}"] = descriptor
    return aliases


def explicit_expression_aliases(
    morphology_by_lemma: dict[str, UnitMorphology],
) -> dict[str, UnitDescriptor]:
    def descriptor(lemma: str, suffix: str | None = None) -> UnitDescriptor:
        return UnitDescriptor(
            lemma=lemma,
            gender="masc",
            category="measure",
            suffix=suffix,
            morphology=morphology_by_lemma.get(lemma, UnitMorphology(expected_normal_form=lemma)),
        )

    def money(lemma: str, suffix: str) -> UnitDescriptor:
        """Денежное отношение: сумма читается рублями и копейками.

        Категория `money` включает чтение копеек, а отношение остаётся
        суффиксом целого выражения и произносится один раз, после суммы.
        """
        return UnitDescriptor(
            lemma=lemma,
            gender="masc",
            category="money",
            suffix=suffix,
            morphology=morphology_by_lemma.get(lemma, UnitMorphology(expected_normal_form=lemma)),
        )

    result = {
        "кВт·ч": descriptor("киловатт-час"),
        # Цена за единицу и курс валюты: числитель денежный, поэтому предлог
        # «за», а не «на». Ключ без конечной точки — реестр снимает её сам,
        # поэтому «руб./долл.» и «руб./долл» разбираются одинаково.
        "руб./долл": money("рубль", "за доллар"),
        "₽/долл": money("рубль", "за доллар"),
        "руб./кг": money("рубль", "за килограмм"),
        "₽/кг": money("рубль", "за килограмм"),
        "руб./г": money("рубль", "за грамм"),
        "₽/г": money("рубль", "за грамм"),
        "руб./л": money("рубль", "за литр"),
        "₽/л": money("рубль", "за литр"),
        "руб./м": money("рубль", "за метр"),
        "₽/м": money("рубль", "за метр"),
        "руб./шт": money("рубль", "за штуку"),
        "₽/шт": money("рубль", "за штуку"),
        "руб./ч": money("рубль", "за час"),
        "₽/ч": money("рубль", "за час"),
        # Частота ударов: знаменатель — время, поэтому «в минуту».
        "уд./мин": descriptor("удар", "в минуту"),
        "уд/мин": descriptor("удар", "в минуту"),
        "уд./с": descriptor("удар", "в секунду"),
        "уд/с": descriptor("удар", "в секунду"),
        "мА·ч": descriptor("миллиампер-час"),
        "мг/кг": descriptor("миллиграмм", "на килограмм"),
        "мл/мин": descriptor("миллилитр", "в минуту"),
        "моль/л": descriptor("моль", "на литр"),
        "ммоль/л": descriptor("миллимоль", "на литр"),
        "мкмоль/л": descriptor("микромоль", "на литр"),
        "нмоль/л": descriptor("наномоль", "на литр"),
    }
    for prefix, lemma in (
        ("k", "кило"),
        ("M", "мега"),
        ("G", "гига"),
        ("T", "тера"),
    ):
        result[f"{prefix}bps"] = descriptor(f"{lemma}бит", "в секунду")
        result[f"{prefix}Bps"] = descriptor(f"{lemma}байт", "в секунду")
        result[f"{prefix}b/s"] = descriptor(f"{lemma}бит", "в секунду")
        result[f"{prefix}B/s"] = descriptor(f"{lemma}байт", "в секунду")
    return result
