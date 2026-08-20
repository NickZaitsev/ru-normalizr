from __future__ import annotations

import functools
import re

from ..text_scan import compile_scan
from .unit_data import explicit_expression_aliases, generated_prefixed_aliases
from .unit_registry import UnitDescriptor, UnitMorphology, UnitRegistry

POST_NUMERAL_ABBREVIATION_PATTERN = compile_scan(
    r"(?<!\w)(?:тыс\.|млн\.|млрд\.|трлн\.|руб\.|долл\.|дол\.|и\s+др\.)(?!\w)",
    re.IGNORECASE,
)
POST_NUMERAL_ABBREVIATION_REPLACEMENTS = {
    "тыс.": "тысяч",
    "млн.": "миллионов",
    "млрд.": "миллиардов",
    "трлн.": "триллионов",
    "руб.": "рублей",
    "долл.": "долларов",
    "дол.": "долларов",
    "и др.": "и другие",
}

GREEK_LETTERS = {
    "α": "альфа",
    "β": "бета",
    "γ": "гамма",
    "δ": "дельта",
    "ε": "эпсилон",
    "ϵ": "эпсилон",
    "ζ": "дзета",
    "η": "эта",
    "θ": "тета",
    "ϑ": "тета",
    "ι": "йота",
    "κ": "каппа",
    "ϰ": "каппа",
    "λ": "лямбда",
    "μ": "мю",
    "µ": "мю",
    "ν": "ню",
    "ξ": "кси",
    "ο": "омикрон",
    "π": "пи",
    "ϖ": "пи",
    "ρ": "ро",
    "ϱ": "ро",
    "σ": "сигма",
    "ς": "сигма",
    "τ": "тау",
    "φ": "фи",
    "ϕ": "фи",
    "χ": "хи",
    "ψ": "пси",
    "ω": "омега",
    "Δ": "дельта",
    "Σ": "сигма",
    "Ω": "омега",
    "Π": "пи",
    "Φ": "фи",
    "Γ": "гамма",
    "Λ": "лямбда",
    "Θ": "тета",
}

MATH_SYMBOLS = {
    "×": " умножить на ",
    "÷": " разделить на ",
    "±": " плюс-минус ",
    "∓": " минус-плюс ",
    "≈": " приблизительно равно ",
    "≠": " не равно ",
    "≤": " меньше или равно ",
    "≥": " больше или равно ",
    "∞": " бесконечность ",
    "√": " корень из ",
    "∑": " сумма ",
    "∏": " произведение ",
    "∫": " интеграл ",
    "∂": " дель ",
    "∈": " принадлежит ",
    "∉": " не принадлежит ",
    "∪": " объединение ",
    "∩": " пересечение ",
    "⇒": " следует ",
    "№": " номер ",
}

CURRENCY_STANDALONE = {
    "$": "доллар",
    "€": "евро",
    "£": "фунт",
    "¥": "йена",
    "₽": "рубль",
    "₴": "гривна",
    "₸": "тенге",
    "₺": "лира",
    "₹": "рупия",
    "¢": "цент",
}

PREP_CASE = {
    "в": "accs",
    "о": "loct",
    "об": "loct",
    "на": "accs",
    "за": "accs",
    "из": "gent",
    "с": "gent",
    "к": "datv",
    "по": "datv",
    "для": "gent",
    "без": "gent",
    "при": "loct",
    "между": "ablt",
    "до": "gent",
    "от": "gent",
    "у": "gent",
    "во": "accs",
    "со": "gent",
    "ко": "datv",
    "обо": "loct",
    "около": "gent",
    "порядка": "gent",
    "не более": "gent",
    "не менее": "gent",
    "не больше": "gent",
    "не меньше": "gent",
    "более": "gent",
    "больше": "gent",
    "менее": "gent",
    "меньше": "gent",
    "больше или равно": "gent",
    "меньше или равно": "gent",
    "свыше": "gent",
    "после": "gent",
    "против": "gent",
    "среди": "gent",
    "вместо": "gent",
    "возле": "gent",
    "вокруг": "gent",
    "внутри": "gent",
    "вне": "gent",
    "ради": "gent",
    "в течение": "gent",
    "течение": "gent",
    "в продолжение": "gent",
    "из-за": "gent",
    "из-под": "gent",
    "вблизи": "gent",
    "вроде": "gent",
    "наподобие": "gent",
    "касательно": "gent",
    "относительно": "gent",
    "насчет": "gent",
    "по поводу": "gent",
    "по причине": "gent",
    "ввиду": "gent",
    "в силу": "gent",
    "в целях": "gent",
    "в рамках": "gent",
    "в ходе": "gent",
    "в отсутствие": "gent",
    "во избежание": "gent",
    "по истечении": "gent",
    "исходя из": "gent",
    "независимо от": "gent",
    "в отличие от": "gent",
    "в зависимости от": "gent",
    "вследствие": "gent",
    "через": "accs",
    "вдоль": "gent",
    "благодаря": "datv",
    "вопреки": "datv",
    "согласно": "datv",
    "навстречу": "datv",
    "подобно": "datv",
    "сообразно": "datv",
    "применительно к": "datv",
    "по направлению к": "datv",
    "по мере": "gent",
    "над": "ablt",
    "надо": "ablt",
    "перед": "ablt",
    "передо": "ablt",
    "пред": "ablt",
    "меж": "ablt",
    "в связи с": "ablt",
    "рядом с": "ablt",
    "вместе с": "ablt",
    "наряду с": "ablt",
    "старше": "gent",
    "моложе": "gent",
    "младше": "gent",
    "выше": "gent",
    "ниже": "gent",
    "дольше": "gent",
    "короче": "gent",
}

VERB_CASE = {
    "обнаружить": "accs",
    "выявить": "accs",
    "показать": "accs",
    "считать": "accs",
    "оценить": "accs",
    "иметь": "accs",
    "избегать": "gent",
    "опасаться": "gent",
    "достичь": "gent",
    "достигать": "gent",
    "лишиться": "gent",
    "верить": "datv",
    "доверять": "datv",
    "видеть": "accs",
    "наблюдать": "accs",
    "замечать": "accs",
    "осознавать": "accs",
    "понимать": "accs",
    "изучать": "accs",
    "анализировать": "accs",
    "рассматривать": "accs",
    "определять": "accs",
    "устанавливать": "accs",
    "формировать": "accs",
    "использовать": "accs",
    "применять": "accs",
    "реализовывать": "accs",
    "разрабатывать": "accs",
    "создавать": "accs",
    "включать": "accs",
    "получать": "accs",
    "не иметь": "gent",
    "избежать": "gent",
    "достигнуть": "gent",
    "требовать": "gent",
    "ожидать": "gent",
    "бояться": "gent",
    "страшиться": "gent",
    "лишать": "gent",
    "касаться": "gent",
    "относиться": "gent",
    "состоять": "gent",
    "дожидаться": "gent",
    "избавиться": "gent",
    "помогать": "datv",
    "способствовать": "datv",
    "препятствовать": "datv",
    "следовать": "datv",
    "соответствовать": "datv",
    "противоречить": "datv",
    "удивляться": "datv",
    "радоваться": "datv",
    "завидовать": "datv",
    "угрожать": "datv",
    # «рекомендовать» и «предлагать» дательным управляют только для адресата;
    # число при них — прямой объект («предлагали 300 тысяч»), его решает
    # переходность.
    "являться": "ablt",
    "считаться": "ablt",
    "обладать": "ablt",
    "характеризоваться": "ablt",
    "отличаться": "ablt",
    "определяться": "ablt",
    "пользоваться": "ablt",
    "управлять": "ablt",
    "владеть": "ablt",
    # Предложный падеж без предлога в русском невозможен, поэтому глаголы
    # речи и мысли («говорить», «думать», «писать»…) голым числом не управляют:
    # «думает 100000 рублей достать» — винительный. Чтение «о пяти задачах»
    # обеспечивает сам предлог «о».
    "стоить": "accs",
}

def _paradigm(
    singular: tuple[str, str, str, str, str, str],
    plural: tuple[str, str, str, str, str, str],
) -> tuple[tuple[str, str, str], ...]:
    cases = ("nomn", "gent", "datv", "accs", "ablt", "loct")
    return tuple(
        (case, number, word)
        for number, forms in (("sing", singular), ("plur", plural))
        for case, word in zip(cases, forms, strict=True)
    )


_UNIT_MORPHOLOGY = {
    "евро": UnitMorphology(expected_normal_form="евро", indeclinable=True),
    "песо": UnitMorphology(expected_normal_form="песо", indeclinable=True),
    "тенге": UnitMorphology(expected_normal_form="тенге", indeclinable=True),
    "промилле": UnitMorphology(expected_normal_form="промилле", indeclinable=True),
    "генри": UnitMorphology(expected_normal_form="генри", indeclinable=True),
    "лира": UnitMorphology(expected_normal_form="лира", animacy="inan"),
    "вона": UnitMorphology(expected_normal_form="вона", animacy="inan"),
    "моль": UnitMorphology(expected_normal_form="моль", animacy="inan"),
    "микрограмм": UnitMorphology(
        expected_normal_form="микрограмм",
        forbidden_grammemes=frozenset({"Coun"}),
    ),
    # Счётная форма: после числительных родительный множественного — «человек»,
    # а не супплетивное «людей» («десять тысяч человек»).
    "человек": UnitMorphology(
        expected_normal_form="человек",
        animacy="anim",
        paradigm=(("gent", "plur", "человек"),),
    ),
    # Косвенные падежи множественного числа верста́ несут ударение на окончании
    # («в двух верстах от города»); pymorphy отдаёт разговорное «вёрстах».
    "верста": UnitMorphology(
        expected_normal_form="верста",
        paradigm=(
            ("datv", "plur", "верстам"),
            ("ablt", "plur", "верстами"),
            ("loct", "plur", "верстах"),
        ),
    ),
    "шекель": UnitMorphology(
        expected_normal_form="шекель",
        paradigm=_paradigm(
            ("шекель", "шекеля", "шекелю", "шекель", "шекелем", "шекеле"),
            ("шекели", "шекелей", "шекелям", "шекели", "шекелями", "шекелях"),
        ),
    ),
    "грей": UnitMorphology(
        expected_normal_form="грей",
        paradigm=_paradigm(
            ("грей", "грея", "грею", "грей", "греем", "грее"),
            ("греи", "греев", "греям", "греи", "греями", "греях"),
        ),
    ),
    "фарад": UnitMorphology(
        expected_normal_form="фарад",
        paradigm=_paradigm(
            ("фарад", "фарада", "фараду", "фарад", "фарадом", "фараде"),
            ("фарады", "фарадов", "фарадам", "фарады", "фарадами", "фарадах"),
        ),
    ),
    "миллифарад": UnitMorphology(
        expected_normal_form="миллифарад",
        paradigm=_paradigm(
            (
                "миллифарад",
                "миллифарада",
                "миллифараду",
                "миллифарад",
                "миллифарадом",
                "миллифараде",
            ),
            (
                "миллифарады",
                "миллифарадов",
                "миллифарадам",
                "миллифарады",
                "миллифарадами",
                "миллифарадах",
            ),
        ),
    ),
    "микрофарад": UnitMorphology(
        expected_normal_form="микрофарад",
        paradigm=_paradigm(
            (
                "микрофарад",
                "микрофарада",
                "микрофараду",
                "микрофарад",
                "микрофарадом",
                "микрофараде",
            ),
            (
                "микрофарады",
                "микрофарадов",
                "микрофарадам",
                "микрофарады",
                "микрофарадами",
                "микрофарадах",
            ),
        ),
    ),
    "нанофарад": UnitMorphology(
        expected_normal_form="нанофарад",
        paradigm=_paradigm(
            ("нанофарад", "нанофарада", "нанофараду", "нанофарад", "нанофарадом", "нанофараде"),
            ("нанофарады", "нанофарадов", "нанофарадам", "нанофарады", "нанофарадами", "нанофарадах"),
        ),
    ),
    "пикофарад": UnitMorphology(
        expected_normal_form="пикофарад",
        paradigm=_paradigm(
            ("пикофарад", "пикофарада", "пикофараду", "пикофарад", "пикофарадом", "пикофараде"),
            ("пикофарады", "пикофарадов", "пикофарадам", "пикофарады", "пикофарадами", "пикофарадах"),
        ),
    ),
    "тесла": UnitMorphology(
        expected_normal_form="тесла",
        paradigm=_paradigm(
            ("тесла", "теслы", "тесле", "теслу", "теслой", "тесле"),
            ("теслы", "тесл", "теслам", "теслы", "теслами", "теслах"),
        ),
    ),
    "паскаль": UnitMorphology(
        expected_normal_form="паскаль",
        paradigm=_paradigm(
            ("паскаль", "паскаля", "паскалю", "паскаль", "паскалем", "паскале"),
            ("паскали", "паскалей", "паскалям", "паскали", "паскалями", "паскалях"),
        ),
    ),
    "килопаскаль": UnitMorphology(
        expected_normal_form="килопаскаль",
        paradigm=_paradigm(
            ("килопаскаль", "килопаскаля", "килопаскалю", "килопаскаль", "килопаскалем", "килопаскале"),
            ("килопаскали", "килопаскалей", "килопаскалям", "килопаскали", "килопаскалями", "килопаскалях"),
        ),
    ),
    "мегапаскаль": UnitMorphology(
        expected_normal_form="мегапаскаль",
        paradigm=_paradigm(
            ("мегапаскаль", "мегапаскаля", "мегапаскалю", "мегапаскаль", "мегапаскалем", "мегапаскале"),
            ("мегапаскали", "мегапаскалей", "мегапаскалям", "мегапаскали", "мегапаскалями", "мегапаскалях"),
        ),
    ),
    "зиверт": UnitMorphology(
        expected_normal_form="зиверт",
        paradigm=_paradigm(
            ("зиверт", "зиверта", "зиверту", "зиверт", "зивертом", "зиверте"),
            ("зиверты", "зивертов", "зивертам", "зиверты", "зивертами", "зивертах"),
        ),
    ),
    "мегавольт": UnitMorphology(
        expected_normal_form="мегавольт",
        paradigm=_paradigm(
            ("мегавольт", "мегавольта", "мегавольту", "мегавольт", "мегавольтом", "мегавольте"),
            ("мегавольты", "мегавольт", "мегавольтам", "мегавольты", "мегавольтами", "мегавольтах"),
        ),
    ),
    "сутки": UnitMorphology(
        expected_normal_form="сутки",
        plural_only=True,
        paradigm=tuple(
            (case, "plur", word)
            for case, word in (
                ("nomn", "сутки"),
                ("gent", "суток"),
                ("datv", "суткам"),
                ("accs", "сутки"),
                ("ablt", "сутками"),
                ("loct", "сутках"),
            )
        ),
    ),
}

for _byte_lemma in (
    "байт",
    "килобайт",
    "мегабайт",
    "гигабайт",
    "терабайт",
):
    _UNIT_MORPHOLOGY[_byte_lemma] = UnitMorphology(
        expected_normal_form=_byte_lemma,
        byte_family=True,
        forbidden_grammemes=frozenset({"Coun"}),
    )

for _bit_lemma in ("бит", "килобит", "мегабит", "гигабит", "терабит"):
    _UNIT_MORPHOLOGY[_bit_lemma] = UnitMorphology(
        expected_normal_form=_bit_lemma,
        preferred_grammemes=frozenset({"Coun"}),
    )


def _upgrade_units(
    raw: dict[str, tuple[str, str, str] | tuple[str, str, str, str]],
) -> dict[str, UnitDescriptor]:
    return {
        token: UnitDescriptor(
            lemma=values[0],
            gender=values[1],
            category=values[2],
            suffix=values[3] if len(values) == 4 else None,
            morphology=_UNIT_MORPHOLOGY.get(
                values[0],
                UnitMorphology(expected_normal_form=values[0]),
            ),
        )
        for token, values in raw.items()
    }


UNITS_DATA = _upgrade_units({
    "₽": ("рубль", "masc", "money"),
    "р": ("рубль", "masc", "money"),
    "руб": ("рубль", "masc", "money"),
    "руб.": ("рубль", "masc", "money"),
    "рубль": ("рубль", "masc", "money"),
    "$": ("доллар", "masc", "money"),
    "¢": ("цент", "masc", "money"),
    "доллар": ("доллар", "masc", "money"),
    "долл.": ("доллар", "masc", "money"),
    "долл": ("доллар", "masc", "money"),
    "usd": ("доллар", "masc", "money"),
    "€": ("евро", "masc", "money"),
    "eur": ("евро", "masc", "money"),
    "евро": ("евро", "masc", "money"),
    "£": ("фунт", "masc", "money"),
    "фунт": ("фунт", "masc", "money"),
    "¥": ("иена", "femn", "money"),
    "иена": ("иена", "femn", "money"),
    "¥н": ("юань", "masc", "money"),
    "юань": ("юань", "masc", "money"),
    "₪": ("шекель", "masc", "money"),
    "шекель": ("шекель", "masc", "money"),
    "₴": ("гривна", "femn", "money"),
    "uah": ("гривна", "femn", "money"),
    "₸": ("тенге", "masc", "money"),
    "kzt": ("тенге", "masc", "money"),
    "тенге": ("тенге", "masc", "money"),
    "₺": ("лира", "femn", "money"),
    "try": ("лира", "femn", "money"),
    "лира": ("лира", "femn", "money"),
    "₹": ("рупия", "femn", "money"),
    "inr": ("рупия", "femn", "money"),
    "₩": ("вона", "femn", "money"),
    "krw": ("вона", "femn", "money"),
    "вона": ("вона", "femn", "money"),
    "₫": ("донг", "masc", "money"),
    "vnd": ("донг", "masc", "money"),
    "₱": ("песо", "neut", "money"),
    "₦": ("найра", "femn", "money"),
    "ngn": ("найра", "femn", "money"),
    "копейка": ("копейка", "femn", "money"),
    "коп": ("копейка", "femn", "money"),
    "коп.": ("копейка", "femn", "money"),
    "цент": ("цент", "masc", "money"),
    "%": ("процент", "masc", "percent"),
    "процент": ("процент", "masc", "percent"),
    "‰": ("промилле", "masc", "percent"),
    "‱": ("базисный пункт", "masc", "percent"),
    "п.п.": ("процентный пункт", "masc", "percent"),
    "б.п.": ("базисный пункт", "masc", "percent"),
    "bps": ("базисный пункт", "masc", "percent"),
    "°c": ("градус", "masc", "measure", "Цельсия"),
    "°k": ("градус", "masc", "measure", "Кельвина"),
    "°f": ("градус", "masc", "measure", "Фаренгейта"),
    "°": ("градус", "masc", "measure"),
    "градус": ("градус", "masc", "measure"),
    # "k": ("кельвин", "masc", "measure"),
    # "к": ("кельвин", "masc", "measure"),
    "кельвин": ("кельвин", "masc", "measure"),
    "v": ("вольт", "masc", "measure"),
    "в.": ("век", "masc", "measure"),
    "вольт": ("вольт", "masc", "measure"),
    "кв": ("киловольт", "masc", "measure"),
    "mv": ("милливольт", "masc", "measure"),
    "kv": ("киловольт", "masc", "measure"),
    "ma": ("миллиампер", "masc", "measure"),
    "ka": ("килоампер", "masc", "measure"),
    "ua": ("микроампер", "masc", "measure"),
    "µa": ("микроампер", "masc", "measure"),
    "μa": ("микроампер", "masc", "measure"),
    "вт": ("ватт", "masc", "measure"),
    "ватт": ("ватт", "masc", "measure"),
    "w": ("ватт", "masc", "measure"),
    "kw": ("киловатт", "masc", "measure"),
    "mw": ("мегаватт", "masc", "measure"),
    "gw": ("гигаватт", "masc", "measure"),
    "ампер": ("ампер", "masc", "measure"),
    "ω": ("ом", "masc", "measure"),
    "ом": ("ом", "masc", "measure"),
    "н": ("ньютон", "masc", "measure"),
    "n": ("ньютон", "masc", "measure"),
    "ньютон": ("ньютон", "masc", "measure"),
    "кн": ("килоньютон", "masc", "measure"),
    "kn": ("килоньютон", "masc", "measure"),
    "мн": ("меганьютон", "masc", "measure"),
    "mn": ("меганьютон", "masc", "measure"),
    "ф": ("фарад", "masc", "measure"),
    "f": ("фарад", "masc", "measure"),
    "фарад": ("фарад", "masc", "measure"),
    "мф": ("миллифарад", "masc", "measure"),
    "mf": ("миллифарад", "masc", "measure"),
    "мкф": ("микрофарад", "masc", "measure"),
    "µf": ("микрофарад", "masc", "measure"),
    "μf": ("микрофарад", "masc", "measure"),
    "uf": ("микрофарад", "masc", "measure"),
    "нф": ("нанофарад", "masc", "measure"),
    "nf": ("нанофарад", "masc", "measure"),
    "пф": ("пикофарад", "masc", "measure"),
    "pf": ("пикофарад", "masc", "measure"),
    "гн": ("генри", "masc", "measure"),
    "h": ("генри", "masc", "measure"),
    "генри": ("генри", "masc", "measure"),
    "кл": ("кулон", "masc", "measure"),
    "c": ("кулон", "masc", "measure"),
    "кулон": ("кулон", "masc", "measure"),
    "тл": ("тесла", "femn", "measure"),
    "тесла": ("тесла", "femn", "measure"),
    "вб": ("вебер", "masc", "measure"),
    "wb": ("вебер", "masc", "measure"),
    "вебер": ("вебер", "masc", "measure"),
    "лм": ("люмен", "masc", "measure"),
    "lm": ("люмен", "masc", "measure"),
    "люмен": ("люмен", "masc", "measure"),
    "лк": ("люкс", "masc", "measure"),
    "lx": ("люкс", "masc", "measure"),
    "люкс": ("люкс", "masc", "measure"),
    "бк": ("беккерель", "masc", "measure"),
    "bq": ("беккерель", "masc", "measure"),
    "беккерель": ("беккерель", "masc", "measure"),
    "gy": ("грей", "masc", "measure"),
    "грей": ("грей", "masc", "measure"),
    "зв": ("зиверт", "masc", "measure"),
    "sv": ("зиверт", "masc", "measure"),
    "зиверт": ("зиверт", "masc", "measure"),
    "дж": ("джоуль", "masc", "measure"),
    "джоуль": ("джоуль", "masc", "measure"),
    "кдж": ("килоджоуль", "masc", "measure"),
    "па": ("паскаль", "masc", "measure"),
    "паскаль": ("паскаль", "masc", "measure"),
    "мпа": ("мегапаскаль", "masc", "measure"),
    "кпа": ("килопаскаль", "masc", "measure"),
    "бар": ("бар", "masc", "measure"),
    "квт": ("киловатт", "masc", "measure"),
    "киловатт": ("киловатт", "masc", "measure"),
    "квтч": ("киловатт-час", "masc", "measure"),
    "квт.ч": ("киловатт-час", "masc", "measure"),
    "квт-ч": ("киловатт-час", "masc", "measure"),
    "мвт": ("мегаватт", "masc", "measure"),
    "гвт": ("гигаватт", "masc", "measure"),
    "гц": ("герц", "masc", "measure"),
    "герц": ("герц", "masc", "measure"),
    "кгц": ("килогерц", "masc", "measure"),
    "мгц": ("мегагерц", "masc", "measure"),
    "ггц": ("гигагерц", "masc", "measure"),
    "байт": ("байт", "masc", "measure"),
    "кб": ("килобайт", "masc", "measure"),
    "кбайт": ("килобайт", "masc", "measure"),
    "мб": ("мегабайт", "masc", "measure"),
    "мбайт": ("мегабайт", "masc", "measure"),
    "гб": ("гигабайт", "masc", "measure"),
    "гбайт": ("гигабайт", "masc", "measure"),
    "тб": ("терабайт", "masc", "measure"),
    "тбайт": ("терабайт", "masc", "measure"),
    "бит": ("бит", "masc", "measure"),
    "кбит": ("килобит", "masc", "measure"),
    "мбит": ("мегабит", "masc", "measure"),
    "гбит": ("гигабит", "masc", "measure"),
    "тбит": ("терабит", "masc", "measure"),
    "mb": ("мегабайт", "masc", "measure"),
    "gb": ("гигабайт", "masc", "measure"),
    "tb": ("терабайт", "masc", "measure"),
    "kbps": ("килобит", "masc", "measure", "в секунду"),
    "mbps": ("мегабит", "masc", "measure", "в секунду"),
    "gbps": ("гигабит", "masc", "measure", "в секунду"),
    "бит/с": ("бит", "masc", "measure", "в секунду"),
    "кбит/с": ("килобит", "masc", "measure", "в секунду"),
    "мбит/с": ("мегабит", "masc", "measure", "в секунду"),
    "гбит/с": ("гигабит", "masc", "measure", "в секунду"),
    "байт/с": ("байт", "masc", "measure", "в секунду"),
    "кб/с": ("килобайт", "masc", "measure", "в секунду"),
    "мб/с": ("мегабайт", "masc", "measure", "в секунду"),
    "гб/с": ("гигабайт", "masc", "measure", "в секунду"),
    "mb/s": ("мегабайт", "masc", "measure", "в секунду"),
    "gb/s": ("гигабайт", "masc", "measure", "в секунду"),
    "fps": ("кадр", "masc", "measure", "в секунду"),
    "га": ("гектар", "masc", "measure"),
    "гектар": ("гектар", "masc", "measure"),
    "кал": ("калория", "femn", "measure"),
    "ккал": ("килокалория", "femn", "measure"),
    "л.с.": ("лошадиная сила", "femn", "measure"),
    "л. с.": ("лошадиная сила", "femn", "measure"),
    "кг": ("килограмм", "masc", "measure"),
    "килограмм": ("килограмм", "masc", "measure"),
    "kg": ("килограмм", "masc", "measure"),
    "г": ("грамм", "masc", "measure"),
    "грамм": ("грамм", "masc", "measure"),
    "гр": ("грамм", "masc", "measure"),
    "тонна": ("тонна", "femn", "measure"),
    "мг": ("миллиграмм", "masc", "measure"),
    "мкг": ("микрограмм", "masc", "measure"),
    "нг": ("нанограмм", "masc", "measure"),
    "oz": ("унция", "femn", "measure"),
    "унция": ("унция", "femn", "measure"),
    "lb": ("фунт", "masc", "measure"),
    # Do not register bare or prefixed "М" spellings as molarity. They overlap
    # length symbols and are especially noisy in damaged source text; amount
    # concentration is supported only through explicit aliases such as "ммоль/л".
    "м": ("метр", "masc", "measure"),
    "нм.": ("нанометр", "masc", "measure"),
    "нм": ("нанометр", "masc", "measure"),
    "метр": ("метр", "masc", "measure"),
    "см": ("сантиметр", "masc", "measure"),
    "cm": ("сантиметр", "masc", "measure"),
    "см²": ("квадратный сантиметр", "masc", "measure"),
    "см³": ("кубический сантиметр", "masc", "measure"),
    "см2": ("квадратный сантиметр", "masc", "measure"),
    "см3": ("кубический сантиметр", "masc", "measure"),
    "см^2": ("квадратный сантиметр", "masc", "measure"),
    "см^3": ("кубический сантиметр", "masc", "measure"),
    "мм": ("миллиметр", "masc", "measure"),
    "mm": ("миллиметр", "masc", "measure"),
    "мм²": ("квадратный миллиметр", "masc", "measure"),
    "мм³": ("кубический миллиметр", "masc", "measure"),
    "мм2": ("квадратный миллиметр", "masc", "measure"),
    "мм3": ("кубический миллиметр", "masc", "measure"),
    "мм^2": ("квадратный миллиметр", "masc", "measure"),
    "мм^3": ("кубический миллиметр", "masc", "measure"),
    "м²": ("квадратный метр", "masc", "measure"),
    "м³": ("кубический метр", "masc", "measure"),
    "м2": ("квадратный метр", "masc", "measure"),
    "м3": ("кубический метр", "masc", "measure"),
    "м^2": ("квадратный метр", "masc", "measure"),
    "м^3": ("кубический метр", "masc", "measure"),
    "кв.м": ("квадратный метр", "masc", "measure"),
    "квм": ("квадратный метр", "masc", "measure"),
    "куб.м": ("кубический метр", "masc", "measure"),
    "кубм": ("кубический метр", "masc", "measure"),
    "кв.км": ("квадратный километр", "masc", "measure"),
    "куб.км": ("кубический километр", "masc", "measure"),
    "кв.см": ("квадратный сантиметр", "masc", "measure"),
    "куб.см": ("кубический сантиметр", "masc", "measure"),
    "кв.мм": ("квадратный миллиметр", "masc", "measure"),
    "куб.мм": ("кубический миллиметр", "masc", "measure"),
    "кв.дм": ("квадратный дециметр", "masc", "measure"),
    "куб.дм": ("кубический дециметр", "masc", "measure"),
    "кмч": ("километр", "masc", "measure", "в час"),
    "км": ("километр", "masc", "measure"),
    "километр": ("километр", "masc", "measure"),
    "km": ("километр", "masc", "measure"),
    "км²": ("квадратный километр", "masc", "measure"),
    "км2": ("квадратный километр", "masc", "measure"),
    "км^2": ("квадратный километр", "masc", "measure"),
    "inch": ("дюйм", "masc", "measure"),
    "inches": ("дюйм", "masc", "measure"),
    "дюйм": ("дюйм", "masc", "measure"),
    "in³": ("кубический дюйм", "masc", "measure"),
    "л": ("литр", "masc", "measure"),
    "литр": ("литр", "masc", "measure"),
    "мл": ("миллилитр", "masc", "measure"),
    "ml": ("миллилитр", "masc", "measure"),
    "миллилитр": ("миллилитр", "masc", "measure"),
    "пинта": ("пинта", "femn", "measure"),
    "pint": ("пинта", "femn", "measure"),
    "м/с": ("метр", "masc", "measure", "в секунду"),
    "м/с²": ("метр", "masc", "measure", "в секунду в квадрате"),
    "м/с2": ("метр", "masc", "measure", "в секунду в квадрате"),
    "м/с^2": ("метр", "masc", "measure", "в секунду в квадрате"),
    "км/ч": ("километр", "masc", "measure", "в час"),
    "об/мин": ("оборот", "masc", "measure", "в минуту"),
    "rpm": ("оборот", "masc", "measure", "в минуту"),
    "ч": ("час", "masc", "measure"),
    "ч.": ("час", "masc", "measure"),
    "ч.л.": ("чайная ложка", "femn", "measure"),
    "ч. л.": ("чайная ложка", "femn", "measure"),
    "час": ("час", "masc", "measure"),
    "мин": ("минута", "femn", "measure"),
    "мин.": ("минута", "femn", "measure"),
    "минута": ("минута", "femn", "measure"),
    "сек": ("секунда", "femn", "measure"),
    "сек.": ("секунда", "femn", "measure"),
    "секунд": ("секунда", "femn", "measure"),
    "секунда": ("секунда", "femn", "measure"),
    "с": ("секунда", "femn", "measure"),
    "с.": ("секунда", "femn", "measure"),
    "мс": ("миллисекунда", "femn", "measure"),
    "мкс": ("микросекунда", "femn", "measure"),
    "нс": ("наносекунда", "femn", "measure"),
    "сут": ("сутки", "plur", "measure"),
    "сут.": ("сутки", "plur", "measure"),
    "дн": ("день", "masc", "measure"),
    "дн.": ("день", "masc", "measure"),
    "нед": ("неделя", "femn", "measure"),
    "нед.": ("неделя", "femn", "measure"),
    "мес": ("месяц", "masc", "measure"),
    "мес.": ("месяц", "masc", "measure"),
    "фут": ("фут", "masc", "measure"),
    "фута": ("фут", "masc", "measure"),
    "футов": ("фут", "masc", "measure"),
    "шт": ("штука", "femn", "measure"),
    "шт.": ("штука", "femn", "measure"),
    "штука": ("штука", "femn", "measure"),
    "экземпляр": ("экземпляр", "masc", "measure"),
    "человек": ("человек", "masc", "measure"),
    "единица": ("единица", "femn", "measure"),
    "чел": ("человек", "masc", "measure"),
    "чел.": ("человек", "masc", "measure"),
    "тыс": ("тысяча", "femn", "measure"),
    "тыс.": ("тысяча", "femn", "measure"),
    "тысяча": ("тысяча", "femn", "measure"),
    "тысячи": ("тысяча", "femn", "measure"),
    "тысяч": ("тысяча", "femn", "measure"),
    "млн": ("миллион", "masc", "measure"),
    "млн.": ("миллион", "masc", "measure"),
    "миллион": ("миллион", "masc", "measure"),
    "миллиона": ("миллион", "masc", "measure"),
    "миллионов": ("миллион", "masc", "measure"),
    "млрд": ("миллиард", "masc", "measure"),
    "млрд.": ("миллиард", "masc", "measure"),
    "миллиард": ("миллиард", "masc", "measure"),
    "миллиарда": ("миллиард", "masc", "measure"),
    "миллиардов": ("миллиард", "masc", "measure"),
    "трлн": ("триллион", "masc", "measure"),
    "трлн.": ("триллион", "masc", "measure"),
    "триллион": ("триллион", "masc", "measure"),
    "триллиона": ("триллион", "masc", "measure"),
    "триллионов": ("триллион", "masc", "measure"),
    "ар": ("ар", "masc", "measure"),
    "дм": ("дециметр", "masc", "measure"),
    "ft": ("фут", "masc", "measure"),
    "yd": ("ярд", "masc", "measure"),
    "mi": ("миля", "femn", "measure"),
    "аршин": ("аршин", "masc", "measure"),
    "арш": ("аршин", "masc", "measure"),
    "верста": ("верста", "femn", "measure"),
    "mph": ("миля", "femn", "measure", "в час"),
    "обмин": ("оборот", "masc", "measure", "в минуту"),
    "уз": ("узел", "masc", "measure"),
    "узел": ("узел", "masc", "measure"),
    "млн₽": ("миллион", "masc", "measure", "рублей"),
    "млрд₽": ("миллиард", "masc", "measure", "рублей"),
    "трлн₽": ("триллион", "masc", "measure", "рублей"),
    "тыс₽": ("тысяча", "femn", "measure", "рублей"),
    "млн$": ("миллион", "masc", "measure", "долларов"),
    "млрд$": ("миллиард", "masc", "measure", "долларов"),
    "тыс$": ("тысяча", "femn", "measure", "долларов"),
    "млн€": ("миллион", "masc", "measure", "евро"),
    "тыс€": ("тысяча", "femn", "measure", "евро"),
    "mah": ("миллиампер-час", "masc", "measure"),
    "ah": ("ампер-час", "masc", "measure"),
    "wh": ("ватт-час", "masc", "measure"),
    "kwh": ("киловатт-час", "masc", "measure"),
    "mwh": ("мегаватт-час", "masc", "measure"),
    "gwh": ("гигаватт-час", "masc", "measure"),
    "va": ("вольт-ампер", "masc", "measure"),
    "kva": ("киловольт-ампер", "masc", "measure"),
    "mol": ("моль", "masc", "measure"),
    "моль": ("моль", "masc", "measure"),
    "ммоль": ("миллимоль", "masc", "measure"),
    "mmol": ("миллимоль", "masc", "measure"),
    "мкмоль": ("микромоль", "masc", "measure"),
    "µmol": ("микромоль", "masc", "measure"),
    "μmol": ("микромоль", "masc", "measure"),
    "ммоль/л": ("миллимоль", "masc", "measure", "на литр"),
    "ммольл": ("миллимоль", "masc", "measure", "на литр"),
    "мг/л": ("миллиграмм", "masc", "measure", "на литр"),
    "мг/мл": ("миллиграмм", "masc", "measure", "на миллилитр"),
    "мкг/мл": ("микрограмм", "masc", "measure", "на миллилитр"),
    "мг/дл": ("миллиграмм", "masc", "measure", "на децилитр"),
    "ед": ("единица", "femn", "measure"),
    "ед.": ("единица", "femn", "measure"),
    "ме": ("международная единица", "femn", "measure"),
    "iu": ("международная единица", "femn", "measure"),
    "ui": ("международная единица", "femn", "measure"),
    "рад.": ("радиан", "masc", "measure"),
    "кадров/с": ("кадр", "masc", "measure", "в секунду"),
    "атм": ("атмосфера", "femn", "measure"),
})

# SI prefixes and symbols are case-sensitive: folding мА/кА to ма/ка would
# make ordinary lowercase words look like electrical units.
CASE_SENSITIVE_UNITS_DATA = _upgrade_units({
    "т": ("тонна", "femn", "measure"),
    "°С": ("градус", "masc", "measure", "Цельсия"),
    "°К": ("градус", "masc", "measure", "Кельвина"),
    # Traditional Russian spelling of the temperature scales, still common in
    # older prose: «12,5° Ц.», «60° Ф.».
    "°Ц": ("градус", "masc", "measure", "Цельсия"),
    "°Ф": ("градус", "masc", "measure", "Фаренгейта"),
    "мкА": ("микроампер", "masc", "measure"),
    "мА": ("миллиампер", "masc", "measure"),
    "кА": ("килоампер", "masc", "measure"),
    "мАч": ("миллиампер-час", "masc", "measure"),
    "mA": ("миллиампер", "masc", "measure"),
    "MA": ("мегаампер", "masc", "measure"),
    "mV": ("милливольт", "masc", "measure"),
    "MV": ("мегавольт", "masc", "measure"),
    "mW": ("милливатт", "masc", "measure"),
    "MW": ("мегаватт", "masc", "measure"),
    "мВт": ("милливатт", "masc", "measure"),
    "МВт": ("мегаватт", "masc", "measure"),
    "Гр": ("грей", "masc", "measure"),
    "гр": ("грамм", "masc", "measure"),
    "b": ("бит", "masc", "measure"),
    "B": ("байт", "masc", "measure"),
    "kb": ("килобит", "masc", "measure"),
    "kB": ("килобайт", "masc", "measure"),
    "Mb": ("мегабит", "masc", "measure"),
    "MB": ("мегабайт", "masc", "measure"),
    "Gb": ("гигабит", "masc", "measure"),
    "GB": ("гигабайт", "masc", "measure"),
    "Tb": ("терабит", "masc", "measure"),
    "TB": ("терабайт", "masc", "measure"),
    "Mbps": ("мегабит", "masc", "measure", "в секунду"),
    "MBps": ("мегабайт", "masc", "measure", "в секунду"),
})
CASE_SENSITIVE_UNITS_DATA["Mb"] = UnitDescriptor(
    lemma="мегабит",
    gender="masc",
    category="measure",
    morphology=UnitMorphology(
        expected_normal_form="мегабит",
        preferred_grammemes=frozenset({"Coun"}),
    ),
)


def _merge_exact_units(generated: dict[str, UnitDescriptor]) -> None:
    for alias, descriptor in generated.items():
        existing = CASE_SENSITIVE_UNITS_DATA.get(alias)
        if existing is not None and existing != descriptor:
            raise ValueError(
                f"Generated unit alias {alias!r} conflicts with a manual declaration"
            )
        CASE_SENSITIVE_UNITS_DATA[alias] = descriptor


_merge_exact_units(generated_prefixed_aliases(_UNIT_MORPHOLOGY))
_merge_exact_units(explicit_expression_aliases(_UNIT_MORPHOLOGY))

# Uppercase one-letter SI symbols are valid only when explicitly registered.
# They must not depend on case repair: that would also turn arbitrary uppercase
# letters such as bare "М" into lowercase units.
for _symbol, _source_alias in {
    "А": "ампер",
    "A": "ампер",
    "В": "v",
    "V": "v",
    "W": "w",
    "Н": "н",
    "N": "n",
    "Ф": "ф",
    "F": "f",
    "H": "h",
    "C": "c",
}.items():
    CASE_SENSITIVE_UNITS_DATA[_symbol] = UNITS_DATA[_source_alias]

UNIT_REGISTRY = UnitRegistry(UNITS_DATA, CASE_SENSITIVE_UNITS_DATA)

# A decimal money amount is spoken as major plus minor units ("89,40 ₽" ->
# "восемьдесят девять рублей сорок копеек"), not as a fraction of the major
# unit. Only currencies whose subunit is actually pronounced in Russian are
# listed: an obscure subunit (тиын, куруш, агора) would be read out where a
# speaker says nothing, so those currencies deliberately keep the plain
# decimal-fraction reading.
CURRENCY_MINOR_UNITS = _upgrade_units({
    "рубль": ("копейка", "femn", "money"),
    "гривна": ("копейка", "femn", "money"),
    "доллар": ("цент", "masc", "money"),
    "евро": ("цент", "masc", "money"),
    "фунт": ("пенс", "masc", "money"),
})


@functools.lru_cache(maxsize=16384)
def resolve_unit_info(unit: str) -> UnitDescriptor | None:
    return UNIT_REGISTRY.resolve(unit)


@functools.lru_cache(maxsize=16384)
def resolve_unit_form(token: str) -> UnitDescriptor | None:
    direct = resolve_unit_info(token)
    if direct is not None:
        return direct
    from .._morph import parse_word

    surface = token.lower().strip(".")
    for candidate in parse_word(surface):
        if candidate.tag.POS != "NOUN":
            continue
        descriptor = resolve_unit_info(candidate.normal_form)
        if descriptor is None:
            continue
        morphology = descriptor.morphology
        if any(form == surface for _, _, form in morphology.paradigm):
            return descriptor
        if (
            candidate.normal_form
            == (morphology.expected_normal_form or descriptor.lemma)
            and (morphology.animacy is None or morphology.animacy in candidate.tag)
        ):
            return descriptor
    return None


def is_exact_unit_token(token: str) -> bool:
    return UNIT_REGISTRY.is_exact_symbol(token)


def is_unit_token(token: str) -> bool:
    return UNIT_REGISTRY.is_unit_token(token)


def unit_entity_category(token: str) -> str | None:
    return UNIT_REGISTRY.entity_category(token)

ENTITY_KEYWORDS = {"percent": set(), "money": set(), "measure": set()}
for key, descriptor in (*UNITS_DATA.items(), *CASE_SENSITIVE_UNITS_DATA.items()):
    ENTITY_KEYWORDS[descriptor.category].add(key.lower())
    ENTITY_KEYWORDS[descriptor.category].add(descriptor.lemma)

ENTITY_DEFAULT_CASE = {"percent": "nomn", "money": "nomn", "measure": "nomn"}
ALL_UNITS = (
    set(UNITS_DATA)
    | {key.lower() for key in CASE_SENSITIVE_UNITS_DATA}
    | {
        descriptor.lemma
        for descriptor in (*UNITS_DATA.values(), *CASE_SENSITIVE_UNITS_DATA.values())
    }
)

CURRENCY_SYMBOLS = frozenset(
    alias
    for alias, descriptor in UNITS_DATA.items()
    if descriptor.category == "money" and len(alias) == 1 and not alias.isalnum()
)

# Every currency symbol has to be reachable from the fragment, otherwise a
# decimal amount matches the number but not its currency and the symbol is left
# raw in the output ("девятнадцать целых девяносто пять сотых £").
_UNIT_FRAGMENT_CHARS = "а-яА-ЯёЁa-zA-ZµμΩ%°" + re.escape("".join(sorted(CURRENCY_SYMBOLS)))

UNIT_TOKEN_FRAGMENT = (
    rf"[{_UNIT_FRAGMENT_CHARS}]+"
    rf"(?:[./^·][{_UNIT_FRAGMENT_CHARS}]+|\d+|[²³])*"
)

NUMERIC_UNIT_RANGE_PATTERN = compile_scan(
    rf"(?<!\d)(?P<left>\d+)\s*[—–-]\s*(?P<right>\d+)\s*(?P<unit>{UNIT_TOKEN_FRAGMENT}(?:\s+[^\W\d_]+){{0,2}})(?P<udot>\.(?!\.))?(?!\w)"
)
FRACTION_PATTERN = compile_scan(r"(?<![\d,])(\d+)/(\d+)(?![\d,])")
# The optional infix is a duplicated case ending of the numeral written out
# before the word it modifies: «17-ти-летняя» is «семнадцатилетняя».
HYPHENATED_WORD_PATTERN = compile_scan(
    # Твёрдый знак после окончания числительного — дореформенное «3-хъ-дневный»:
    # он часть окончания, а не начало слова справа.
    r"(?<![\w\d])(?P<num>\d+)-(?:(?P<infix>тью|ти|ми|мя|ух|ех|ёх|х)ъ?-)?"
    r"(?P<word>[а-яА-ЯёЁ]{1,})"
)
STANDALONE_CURRENCY_PATTERN = compile_scan(r"(?<!\S)([$€£¥₽₴₸₺₹¢])(?!\S)")
DIGIT_PATTERN = compile_scan(r"\d+")

TIME_WORDS = {
    "год": "masc",
    "года": "masc",
    "лет": "masc",
    "году": "masc",
    "годом": "masc",
    "годе": "masc",
    "годов": "masc",
    "годам": "masc",
    "годами": "masc",
    "годах": "masc",
    "месяц": "masc",
    "месяца": "masc",
    "месяцев": "masc",
    "месяцу": "masc",
    "месяцем": "masc",
    "месяце": "masc",
    "месяцам": "masc",
    "месяцами": "masc",
    "месяцах": "masc",
    "день": "masc",
    "дня": "masc",
    "дней": "masc",
    "дню": "masc",
    "днем": "masc",
    "днём": "masc",
    "дне": "masc",
    "дням": "masc",
    "днями": "masc",
    "днях": "masc",
    "неделя": "femn",
    "недели": "femn",
    "недель": "femn",
    "неделе": "femn",
    "неделю": "femn",
    "неделей": "femn",
    "неделях": "femn",
    "неделям": "femn",
    "неделями": "femn",
    "сутки": "plur",
    "сут": "plur",
    "суток": "plur",
    "суткам": "plur",
    "сутками": "plur",
    "сутках": "plur",
    "час": "masc",
    "часа": "masc",
    "часов": "masc",
    "часу": "masc",
    "часом": "masc",
    "часе": "masc",
    "часам": "masc",
    "часами": "masc",
    "часах": "masc",
    "минута": "femn",
    "минуты": "femn",
    "минут": "femn",
    "минуте": "femn",
    "минуту": "femn",
    "минутой": "femn",
    "минутам": "femn",
    "минутами": "femn",
    "минутах": "femn",
    "секунда": "femn",
    "сек": "femn",
    "секунд": "femn",
    "секунды": "femn",
    "секунде": "femn",
    "секунду": "femn",
    "секундой": "femn",
    "секундам": "femn",
    "секундами": "femn",
    "секундах": "femn",
    "ч": "masc",
    "мин": "femn",
    "с": "femn",
    "дн": "masc",
    "нед": "femn",
    "в": "masc",
    "в.": "masc",
    "век": "masc",
    "века": "masc",
    "веку": "masc",
    "веке": "masc",
    "веком": "masc",
    "веков": "masc",
    "столетие": "neut",
    "столетия": "neut",
    "столетию": "neut",
    "столетии": "neut",
    "столетием": "neut",
}
