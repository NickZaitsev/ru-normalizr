from __future__ import annotations

import re

import num2words

from ._morph import get_morph
from .options import NormalizeOptions
from .preprocess_utils import NEGATIVE_NUMBER_PLACEHOLDER, PARAGRAPH_BREAK_PLACEHOLDER

POST_NUMERAL_ABBREVIATION_PATTERNS = [
    (re.compile(r"(?<!\w)тыс\.(?!\w)", re.IGNORECASE), "тысяч"),
    (re.compile(r"(?<!\w)млн\.(?!\w)", re.IGNORECASE), "миллионов"),
    (re.compile(r"(?<!\w)млрд\.(?!\w)", re.IGNORECASE), "миллиардов"),
    (re.compile(r"(?<!\w)трлн\.(?!\w)", re.IGNORECASE), "триллионов"),
    (re.compile(r"(?<!\w)руб\.(?!\w)", re.IGNORECASE), "рублей"),
    (re.compile(r"(?<!\w)долл\.(?!\w)", re.IGNORECASE), "долларов"),
    (re.compile(r"(?<!\w)дол\.(?!\w)", re.IGNORECASE), "долларов"),
    (re.compile(r"(?<!\w)и\s+др\.(?!\w)", re.IGNORECASE), "и другие"),
]

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
    "в течение": "gent",
    "течение": "gent",
    "в продолжение": "gent",
    "вследствие": "gent",
    "свыше": "gent",
    "более": "gent",
    "менее": "gent",
    "около": "gent",
    "порядка": "gent",
    "после": "gent",
    "против": "gent",
    "через": "accs",
    "среди": "gent",
    "вместо": "gent",
    "возле": "gent",
    "вокруг": "gent",
    "вдоль": "gent",
    "внутри": "gent",
    "вне": "gent",
    "ради": "gent",
    "благодаря": "datv",
    "вопреки": "datv",
    "согласно": "datv",
    "навстречу": "datv",
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
    "рекомендовать": "datv",
    "предлагать": "datv",
    "являться": "ablt",
    "считаться": "ablt",
    "обладать": "ablt",
    "характеризоваться": "ablt",
    "отличаться": "ablt",
    "определяться": "ablt",
    "пользоваться": "ablt",
    "управлять": "ablt",
    "владеть": "ablt",
    "говорить": "loct",
    "сообщать": "loct",
    "рассказывать": "loct",
    "упоминать": "loct",
    "писать": "loct",
    "думать": "loct",
    "размышлять": "loct",
    "основываться": "loct",
    "заключаться": "loct",
}

UNITS_DATA = {
    "₽": ("рубль", "masc", "money"),
    "р": ("рубль", "masc", "money"),
    "руб": ("рубль", "masc", "money"),
    "руб.": ("рубль", "masc", "money"),
    "рубль": ("рубль", "masc", "money"),
    "$": ("доллар", "masc", "money"),
    "доллар": ("доллар", "masc", "money"),
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
    "₺": ("лира", "femn", "money"),
    "try": ("лира", "femn", "money"),
    "₹": ("рупия", "femn", "money"),
    "inr": ("рупия", "femn", "money"),
    "₩": ("вон", "masc", "money"),
    "krw": ("вон", "masc", "money"),
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
    "°": ("градус", "masc", "measure"),
    "градус": ("градус", "masc", "measure"),
    "°c": ("градус", "masc", "measure", "Цельсия"),
    "°k": ("градус", "masc", "measure", "Кельвина"),
    "°f": ("градус", "masc", "measure", "Фаренгейта"),
    "v": ("вольт", "masc", "measure"),
    "вольт": ("вольт", "masc", "measure"),
    "вт": ("ватт", "masc", "measure"),
    "ватт": ("ватт", "masc", "measure"),
    "w": ("ватт", "masc", "measure"),
    "а": ("ампер", "masc", "measure"),
    "ампер": ("ампер", "masc", "measure"),
    "ω": ("ом", "masc", "measure"),
    "ом": ("ом", "masc", "measure"),
    "дж": ("джоуль", "masc", "measure"),
    "джоуль": ("джоуль", "masc", "measure"),
    "кдж": ("килоджоуль", "masc", "measure"),
    "па": ("паскаль", "masc", "measure"),
    "паскаль": ("паскаль", "masc", "measure"),
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
    "kb": ("килобайт", "masc", "measure"),
    "mb": ("мегабайт", "masc", "measure"),
    "gb": ("гигабайт", "masc", "measure"),
    "tb": ("терабайт", "masc", "measure"),
    "kbps": ("килобит в секунду", "masc", "measure"),
    "mbps": ("мегабит в секунду", "masc", "measure"),
    "gbps": ("гигабит в секунду", "masc", "measure"),
    "fps": ("кадр в секунду", "masc", "measure"),
    "га": ("гектар", "masc", "measure"),
    "гектар": ("гектар", "masc", "measure"),
    "кал": ("калория", "femn", "measure"),
    "ккал": ("килокалория", "femn", "measure"),
    "л.с.": ("лошадиная сила", "femn", "measure"),
    "кг": ("килограмм", "masc", "measure"),
    "килограмм": ("килограмм", "masc", "measure"),
    "kg": ("килограмм", "masc", "measure"),
    "г": ("грамм", "masc", "measure"),
    "грамм": ("грамм", "masc", "measure"),
    "гр": ("грамм", "masc", "measure"),
    "т": ("тонна", "femn", "measure"),
    "тонна": ("тонна", "femn", "measure"),
    "мг": ("миллиграмм", "masc", "measure"),
    "мкг": ("микрограмм", "masc", "measure"),
    "нг": ("нанограмм", "masc", "measure"),
    "oz": ("унция", "femn", "measure"),
    "унция": ("унция", "femn", "measure"),
    "lb": ("фунт", "masc", "measure"),
    "м": ("метр", "masc", "measure"),
    "метр": ("метр", "masc", "measure"),
    "см": ("сантиметр", "masc", "measure"),
    "см²": ("квадратный сантиметр", "masc", "measure"),
    "см³": ("кубический сантиметр", "masc", "measure"),
    "мм": ("миллиметр", "masc", "measure"),
    "м²": ("квадратный метр", "masc", "measure"),
    "м³": ("кубический метр", "masc", "measure"),
    "км": ("километр", "masc", "measure"),
    "километр": ("километр", "masc", "measure"),
    "km": ("километр", "masc", "measure"),
    "км²": ("квадратный километр", "masc", "measure"),
    "in³": ("кубический дюйм", "masc", "measure"),
    "л": ("литр", "masc", "measure"),
    "литр": ("литр", "masc", "measure"),
    "мл": ("миллилитр", "masc", "measure"),
    "миллилитр": ("миллилитр", "masc", "measure"),
    "пинта": ("пинта", "femn", "measure"),
    "pint": ("пинта", "femn", "measure"),
    "м/с": ("метр в секунду", "masc", "measure"),
    "км/ч": ("километр в час", "masc", "measure"),
    "ч": ("час", "masc", "measure"),
    "час": ("час", "masc", "measure"),
    "мин": ("минута", "femn", "measure"),
    "минута": ("минута", "femn", "measure"),
    "сек": ("секунда", "femn", "measure"),
    "секунда": ("секунда", "femn", "measure"),
    "с": ("секунда", "femn", "measure"),
    "мс": ("миллисекунда", "femn", "measure"),
    "мкс": ("микросекунда", "femn", "measure"),
    "нс": ("наносекунда", "femn", "measure"),
    "мес": ("месяц", "masc", "measure"),
    "мес.": ("месяц", "masc", "measure"),
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
    "mph": ("миля в час", "femn", "measure"),
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
}

ENTITY_KEYWORDS = {"percent": set(), "money": set(), "measure": set()}
for key, val in UNITS_DATA.items():
    lemma, _, category, *suffix = val
    ENTITY_KEYWORDS[category].add(key)
    ENTITY_KEYWORDS[category].add(lemma)

ENTITY_DEFAULT_CASE = {"percent": "nomn", "money": "nomn", "measure": "nomn"}
ALL_UNITS = set(UNITS_DATA.keys()) | {value[0] for value in UNITS_DATA.values()}
NUMERIC_UNIT_RANGE_PATTERN = re.compile(
    r"(?<!\d)(?P<left>\d+)\s*[—–-]\s*(?P<right>\d+)\s*(?P<unit>[а-яА-ЯёЁa-zA-Z%°$€₽Ω]+)(?!\w)"
)

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
    "секунды": "femn",
    "секунд": "femn",
    "секунде": "femn",
    "секунду": "femn",
    "секундой": "femn",
    "секундам": "femn",
    "секундами": "femn",
    "секундах": "femn",
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


def simple_tokenize(text: str) -> list[str]:
    return re.findall(
        rf"\n+|{re.escape(PARAGRAPH_BREAK_PLACEHOLDER)}+|{re.escape(NEGATIVE_NUMBER_PLACEHOLDER)}\d+(?:[.,]\d+)?|\d+-[A-Za-z]+|\d+|[^\W\d_]+(?:-[^\W_]+)+|[^\W\d_]+|[$€₽£¥₴₸₺₹¢₪₩₫₱₦]|[^\w\s]",
        text,
        flags=re.UNICODE,
    )


def is_integer_token(token: str) -> bool:
    clean_token = token.strip('.,:;!"«»()[]{}')
    if clean_token.startswith(NEGATIVE_NUMBER_PLACEHOLDER):
        clean_token = clean_token[len(NEGATIVE_NUMBER_PLACEHOLDER) :]
    return clean_token.isdigit()


def parse_integer_token(token: str) -> tuple[bool, str] | None:
    clean_token = token.strip('.,:;!"«»()[]{}')
    is_negative = clean_token.startswith(NEGATIVE_NUMBER_PLACEHOLDER)
    if is_negative:
        clean_token = clean_token[len(NEGATIVE_NUMBER_PLACEHOLDER) :]
    if not clean_token.isdigit():
        return None
    return is_negative, clean_token


def build_number_token(
    token: str, clean_token: str, replacement: str, is_negative: bool
) -> str:
    source = (
        f"{NEGATIVE_NUMBER_PLACEHOLDER}{clean_token}" if is_negative else clean_token
    )
    result = token.replace(source, replacement, 1)
    if is_negative:
        return f"минус {result}"
    return result


def safe_inflect(parsed_word, target_tags, fallback_word=None, pos_filter=None):
    if fallback_word is None:
        fallback_word = parsed_word.word
    try:
        inflected = parsed_word.inflect(target_tags)
        if inflected:
            return inflected.word
    except Exception:
        pass
    pos = parsed_word.tag.POS
    if (
        (pos_filter is None or pos in pos_filter)
        and "gent" in target_tags
        and "plur" in target_tags
        and pos in {"ADJF", "PRTF"}
    ):
        heuristic_result = apply_genitive_plural_heuristic(parsed_word.word, pos)
        if heuristic_result != parsed_word.word:
            return heuristic_result
    return fallback_word


def apply_genitive_plural_heuristic(word, pos):
    if pos not in {"ADJF", "PRTF"}:
        return word
    lower_word = word.lower()
    if lower_word.endswith("ые"):
        return word[:-2] + ("Ых" if word.isupper() else "ых")
    if lower_word.endswith("ие"):
        return word[:-2] + ("Их" if word.isupper() else "их")
    if lower_word.endswith("ый") or lower_word.endswith("ой"):
        return word[:-2] + ("Ого" if word.isupper() else "ого")
    if lower_word.endswith("ий") or lower_word.endswith("ее"):
        return word[:-2] + ("Его" if word.isupper() else "его")
    if lower_word.endswith("ая"):
        return word[:-2] + ("Ой" if word.isupper() else "ой")
    if lower_word.endswith("яя"):
        return word[:-2] + ("Ей" if word.isupper() else "ей")
    return word


def is_case_reliable_noun(parsed_word) -> bool:
    # Fixed abbreviations like "тыс" are poor signals for deciding between
    # accusative and prepositional after "в/на": they often inflect to themselves.
    return "NOUN" in parsed_word.tag and "Fixd" not in parsed_word.tag


def noun_number_form(n: int) -> str:
    if n == 0:
        return "many"
    last_two = n % 100
    last_digit = n % 10
    if last_two in {11, 12, 13, 14}:
        return "many"
    if last_digit == 1:
        return "one"
    if last_digit in {2, 3, 4}:
        return "few"
    return "many"


def _should_consume_abbreviation_dot(tokens: list[str], dot_index: int) -> bool:
    if dot_index >= len(tokens) or tokens[dot_index] != ".":
        return False
    if dot_index + 1 >= len(tokens):
        return False

    next_token = tokens[dot_index + 1]
    if "\n" in next_token or PARAGRAPH_BREAK_PLACEHOLDER in next_token:
        return False

    stripped_next = next_token.strip('.,:;!"«»()[]{}')
    if not stripped_next:
        return False

    first_char = stripped_next[:1]
    return first_char.islower() or first_char.isdigit()


def _should_keep_decimal_unit_dot(rest: str) -> bool:
    stripped_rest = rest.lstrip()
    if not stripped_rest:
        return True
    if "\n" in rest[: len(rest) - len(stripped_rest)]:
        return True
    next_char = stripped_rest[:1]
    if next_char in ".!?…":
        return True
    return not (next_char.islower() or next_char.isdigit())


def inflect_numeral_string(num_str: str, case: str, gender: str | None = None) -> str:
    try:
        value = int(num_str)
    except ValueError:
        return num_str
    cases_map = {
        "nomn": "nominative",
        "gent": "genitive",
        "datv": "dative",
        "accs": "accusative",
        "ablt": "instrumental",
        "loct": "prepositional",
    }
    n2w_gender_map = {"masc": "masculine", "femn": "feminine", "neut": "neuter"}
    if case in cases_map:
        try:
            kwargs = {"case": cases_map[case]}
            if gender == "plur":
                kwargs["plural"] = True
            elif gender in n2w_gender_map:
                kwargs["gender"] = n2w_gender_map[gender]
            return num2words.num2words(value, lang="ru", **kwargs)
        except Exception:
            pass
    try:
        words = num2words.num2words(value, lang="ru").split()
    except Exception:
        return num_str
    if case == "nomn" and gender is None:
        return " ".join(words)
    morph = get_morph()
    magnitudes = {
        "тысяча": "femn",
        "миллион": "masc",
        "миллиард": "masc",
        "триллион": "masc",
        "биллион": "masc",
    }

    def get_magnitude_gender(word_str: str):
        return magnitudes.get(morph.parse(word_str)[0].normal_form)

    inflected_words: list[str] = []
    for i, word in enumerate(words):
        parsed = morph.parse(word)
        p = parsed[0] if parsed else None
        if not p:
            inflected_words.append(word)
            continue
        current_gender = gender
        is_magnitude_self = get_magnitude_gender(word) is not None
        if not is_magnitude_self and i + 1 < len(words):
            mag_gender = get_magnitude_gender(words[i + 1])
            if mag_gender:
                current_gender = mag_gender
        if is_magnitude_self:
            current_gender = None
            if case == "nomn":
                inflected_words.append(word)
                continue
            if case == "accs" and word.lower() != "тысяча":
                inflected_words.append(word)
                continue
        tags = {case}
        if current_gender:
            tags.add(current_gender)
        inflected = p.inflect(tags)
        if inflected:
            inflected_words.append(inflected.word)
        else:
            if current_gender:
                inflected_case = p.inflect({case})
                if inflected_case:
                    inflected_words.append(inflected_case.word)
                    continue
            inflected_words.append(word)
    return " ".join(inflected_words)


def get_target_tags_for_number(num, case, noun_gender=None):
    form = noun_number_form(num)
    if case == "nomn":
        return (
            {"nomn", "sing"}
            if form == "one"
            else {"gent", "sing"} if form == "few" else {"gent", "plur"}
        )
    if case == "accs":
        return (
            {"accs", "sing"}
            if form == "one"
            else {"gent", "sing"} if form == "few" else {"gent", "plur"}
        )
    return {case, "sing"} if form == "one" else {case, "plur"}


def get_numeral_case(tokens, idx):
    morph = get_morph()
    for i in range(idx - 1, max(-1, idx - 3), -1):
        word_left = tokens[i].lower().strip(".,!?;:")
        if word_left in PREP_CASE:
            if word_left in {"с", "со"}:
                for k in range(idx + 1, min(len(tokens), idx + 5)):
                    if tokens[k].lower() in {"до", "по"}:
                        return "gent"
            if word_left in {"в", "на"}:
                for j in range(idx + 1, min(len(tokens), idx + 6)):
                    if any(p in tokens[j] for p in ".!?;:,"):
                        break
                    p = morph.parse(tokens[j])[0]
                    if is_case_reliable_noun(p):
                        if p.tag.case == "loct" or "loc2" in p.tag:
                            return "loct"
                        is_loc = p.inflect({"loct"})
                        is_acc = p.inflect({"accs"})
                        word_curr = tokens[j].lower()
                        if is_loc and is_loc.word == word_curr:
                            return "loct"
                        if is_acc and is_acc.word == word_curr:
                            return "accs"
                    if "VERB" in p.tag or "INFN" in p.tag:
                        break
                for j in range(idx + 1, min(len(tokens), idx + 4)):
                    p = morph.parse(tokens[j])[0]
                    word_norm = p.normal_form
                    if word_norm in {
                        "год",
                        "месяц",
                        "день",
                        "век",
                        "неделя",
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
                    }:
                        if is_integer_token(tokens[idx]):
                            parsed_num = parse_integer_token(tokens[idx])
                            if parsed_num is None:
                                return "loct"
                            _, unsigned = parsed_num
                            val = int(unsigned)
                            return "loct" if 1000 <= val <= 2100 else "accs"
                        return "loct"
                return "accs"
            if word_left == "по":
                if is_integer_token(tokens[idx]):
                    parsed_num = parse_integer_token(tokens[idx])
                    if parsed_num is None:
                        return "datv"
                    _, unsigned = parsed_num
                    val = int(unsigned)
                    if val % 10 == 1 and val % 100 != 11:
                        return "datv"
                    return "accs"
                return "datv"
            return PREP_CASE[word_left]

    blocked_by_noun = False
    for i in range(idx - 1, max(-1, idx - 3), -1):
        p = morph.parse(tokens[i])[0]
        if p.tag.POS == "NOUN":
            blocked_by_noun = True
            break

    for i in range(max(0, idx - 2), idx):
        p = morph.parse(tokens[i])[0]
        if blocked_by_noun and p.tag.POS in {"ADJF", "PRTF", "NPRO"}:
            continue
        if p.tag.POS in {"ADJF", "PRTF", "NPRO"} and p.tag.case:
            return p.tag.case

    for i in range(idx - 1, max(-1, idx - 5), -1):
        word_left = tokens[i].lower().strip(".,!?;:")
        p_verb = morph.parse(word_left)[0]
        if p_verb.normal_form in VERB_CASE:
            return VERB_CASE[p_verb.normal_form]
        if any(c in tokens[i] for c in ".!?"):
            break

    if idx < len(tokens) - 1:
        word_right = tokens[idx + 1].lower().strip(".,!?;:")
        p_right = morph.parse(word_right)[0]
        for entity_type, keywords in ENTITY_KEYWORDS.items():
            if p_right.normal_form in keywords or word_right in keywords:
                return ENTITY_DEFAULT_CASE[entity_type]

    if idx > 1 and tokens[idx - 1] == "и" and is_integer_token(tokens[idx - 2]):
        return get_numeral_case(tokens, idx - 2)
    if idx == 0 or any(c in tokens[idx - 1] for c in ".!?"):
        return "nomn"
    return "nomn"


def detokenize(tokens):
    parts: list[str] = []
    previous_was_newline = True

    for token in tokens:
        if not token:
            continue
        if "\n" in token or PARAGRAPH_BREAK_PLACEHOLDER in token:
            parts.append(token)
            previous_was_newline = True
            continue
        if parts and not previous_was_newline:
            parts.append(" ")
        parts.append(token)
        previous_was_newline = False

    text = "".join(parts)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"(?<=\.) (?=\d)", "", text)
    text = re.sub(r"(точка [а-яё]+)\. (?=[а-яё])", r"\1.", text, flags=re.IGNORECASE)
    text = re.sub(r"([,!?;:])\1+", r"\1", text)
    text = re.sub(r"(?<!\.)\.\.(?!\.)", r".", text)
    text = re.sub(r",\.", r".", text)
    text = re.sub(r"\.,", r".", text)
    text = re.sub(r"([\(\[\{])\s+", r"\1", text)
    text = re.sub(r"\s+([\)\]\}])", r"\1", text)
    return text


def normalize_cardinal_numerals(text: str) -> str:
    morph = get_morph()
    tokens = simple_tokenize(text)
    result_tokens: list[str] = []

    def is_redundant_unit_token(token_index: int, expected_lemma: str) -> bool:
        if token_index >= len(tokens):
            return False
        token_lower = tokens[token_index].lower().strip('.,:;!"«»()[]{}')
        if not token_lower:
            return False
        parsed = morph.parse(token_lower)
        if not parsed:
            return False
        candidate = parsed[0]
        return "NOUN" in candidate.tag and candidate.normal_form == expected_lemma

    i = 0
    while i < len(tokens):
        token = tokens[i]
        parsed_num = parse_integer_token(token)
        if parsed_num is None:
            result_tokens.append(token)
            i += 1
            continue

        is_negative, clean_token = parsed_num
        val = int(clean_token)
        case = get_numeral_case(tokens, i)
        inflected_num = inflect_numeral_string(clean_token, case)
        num_words = build_number_token(token, clean_token, inflected_num, is_negative)

        if i + 2 < len(tokens):
            adj_token = tokens[i + 1]
            noun_token = tokens[i + 2]
            clean_adj = adj_token.lower().strip('.,:;!"«»()[]{}')
            clean_noun = noun_token.lower().strip('.,:;!"«»()[]{}')
            p_adj = morph.parse(clean_adj)[0]
            p_noun = morph.parse(clean_noun)[0]
            if ("ADJF" in p_adj.tag or "PRTF" in p_adj.tag) and "NOUN" in p_noun.tag:
                gender = p_noun.tag.gender
                is_anim = "anim" in p_noun.tag
                target_num_case = case
                if case == "accs":
                    rem100 = val % 100
                    rem10 = val % 10
                    if rem10 in (2, 3, 4) and rem100 not in (12, 13, 14):
                        target_num_case = "gent" if is_anim else "nomn"
                num_words = build_number_token(
                    token,
                    clean_token,
                    inflect_numeral_string(clean_token, target_num_case, gender),
                    is_negative,
                )
                result_tokens.extend([num_words, adj_token, noun_token])
                i += 3
                continue

        if i + 1 < len(tokens):
            noun_token = tokens[i + 1]
            next_token_lower = noun_token.lower().strip('.,:;!"«»()[]{}')
            if next_token_lower == "°" and i + 2 < len(tokens):
                degree_suffix = tokens[i + 2].lower().strip('.,:;!"«»()[]{}')
                if degree_suffix in {"c", "k", "f"}:
                    next_token_lower = f"°{degree_suffix}"
                    noun_token = f"{noun_token}{tokens[i + 2]}"
            unit_info = UNITS_DATA.get(next_token_lower)
            if unit_info:
                lemma, u_gender, u_category, *u_suffix = unit_info
                p_unit = morph.parse(lemma)[0]
                multipliers = {"тысяча", "миллион", "миллиард", "триллион"}
                currency_symbol_units = {
                    "$",
                    "€",
                    "₽",
                    "£",
                    "¥",
                    "₴",
                    "₸",
                    "₺",
                    "₹",
                    "¢",
                    "₪",
                    "₩",
                    "₫",
                    "₱",
                    "₦",
                }
                if (
                    u_category == "money"
                    and next_token_lower in currency_symbol_units
                    and i + 2 < len(tokens)
                ):
                    multiplier_token = tokens[i + 2]
                    multiplier_lower = multiplier_token.lower().strip('.,:;!"«»()[]{}')
                    p_multiplier = morph.parse(multiplier_lower)[0]
                    if (
                        "NOUN" in p_multiplier.tag
                        and p_multiplier.normal_form in multipliers
                    ):
                        target_num_case = case
                        if case == "accs":
                            rem100 = val % 100
                            rem10 = val % 10
                            if rem10 in (2, 3, 4) and rem100 not in (12, 13, 14):
                                target_num_case = "nomn"
                        multiplier_gender = p_multiplier.tag.gender or "masc"
                        num_words = build_number_token(
                            token,
                            clean_token,
                            inflect_numeral_string(
                                clean_token, target_num_case, multiplier_gender
                            ),
                            is_negative,
                        )
                        result_tokens.extend(
                            [
                                num_words,
                                multiplier_token,
                                safe_inflect(p_unit, {"gent", "plur"}),
                            ]
                        )
                        i += 4 if is_redundant_unit_token(i + 3, lemma) else 3
                        continue

                target_num_case = case
                if case == "accs":
                    rem100 = val % 100
                    rem10 = val % 10
                    if rem10 in (2, 3, 4) and rem100 not in (12, 13, 14):
                        target_num_case = "nomn"
                num_words = build_number_token(
                    token,
                    clean_token,
                    inflect_numeral_string(clean_token, target_num_case, u_gender),
                    is_negative,
                )
                inflected_unit = safe_inflect(
                    p_unit, get_target_tags_for_number(val, case, u_gender)
                )
                full_unit = inflected_unit + (f" {u_suffix[0]}" if u_suffix else "")
                match_unit = re.search(
                    re.escape(next_token_lower), noun_token, re.IGNORECASE
                )
                if match_unit:
                    full_unit = (
                        noun_token[: match_unit.start()]
                        + full_unit
                        + noun_token[match_unit.end() :]
                    )
                result_tokens.extend([num_words, full_unit])
                step = (
                    3
                    if next_token_lower.startswith("°") and len(next_token_lower) == 2
                    else 2
                )
                if i + step < len(tokens) and _should_consume_abbreviation_dot(
                    tokens, i + step
                ):
                    step += 1
                if is_redundant_unit_token(i + step, lemma):
                    step += 1
                if lemma in multipliers and i + 2 < len(tokens):
                    next_next_token = tokens[i + 2]
                    nn_token_lower = next_next_token.lower().strip('.,:;!"«»()[]{}')
                    nn_unit_info = UNITS_DATA.get(nn_token_lower)
                    if nn_unit_info:
                        nn_lemma, _, _, *nn_suffix = nn_unit_info
                        p_nn = morph.parse(nn_lemma)[0]
                        nn_inflected = safe_inflect(p_nn, {"gent", "plur"})
                        if nn_suffix:
                            nn_inflected += f" {nn_suffix[0]}"
                        result_tokens.append(nn_inflected)
                        i += step + 1
                        continue
                i += step
                continue

            p_noun = morph.parse(next_token_lower)[0]
            if "NOUN" in p_noun.tag:
                gender = TIME_WORDS.get(next_token_lower, p_noun.tag.gender)
                is_anim = "anim" in p_noun.tag
                target_num_case = case
                if case == "accs":
                    rem100 = val % 100
                    rem10 = val % 10
                    if rem10 in (2, 3, 4) and rem100 not in (12, 13, 14):
                        target_num_case = "gent" if is_anim else "nomn"
                num_words = build_number_token(
                    token,
                    clean_token,
                    inflect_numeral_string(clean_token, target_num_case, gender),
                    is_negative,
                )
                result_tokens.extend([num_words, noun_token])
                i += 2
                continue

        result_tokens.append(num_words)
        i += 1
    return detokenize(result_tokens)


def normalize_numeric_unit_ranges(text: str) -> str:
    morph = get_morph()

    def repl(match: re.Match[str]) -> str:
        left = match.group("left")
        right = match.group("right")
        unit_raw = match.group("unit")
        unit_lower = unit_raw.lower().strip(".")
        unit_info = UNITS_DATA.get(unit_lower)
        if not unit_info:
            return match.group(0)

        context = text[max(0, match.start() - 40) : match.start()]
        tokens_left = simple_tokenize(context)
        case = get_numeral_case(tokens_left + [left], len(tokens_left))
        lemma, u_gender, _, *u_suffix = unit_info

        def numeral_for_range(value_text: str) -> str:
            value = int(value_text)
            target_case = case
            if case == "accs":
                rem100 = value % 100
                rem10 = value % 10
                if rem10 in (2, 3, 4) and rem100 not in (12, 13, 14):
                    target_case = "nomn"
            return inflect_numeral_string(value_text, target_case, u_gender)

        right_value = int(right)
        p_unit = morph.parse(lemma)[0]
        unit_words = safe_inflect(
            p_unit, get_target_tags_for_number(right_value, case, u_gender)
        )
        if u_suffix:
            unit_words += f" {u_suffix[0]}"

        return f"{numeral_for_range(left)} — {numeral_for_range(right)} {unit_words}"

    return NUMERIC_UNIT_RANGE_PATTERN.sub(repl, text)


def normalize_remaining_post_numeral_abbreviations(text: str) -> str:
    for pattern, replacement in POST_NUMERAL_ABBREVIATION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def normalize_all_digits_everywhere(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        try:
            return num2words.num2words(int(match.group(0)), lang="ru")
        except Exception:
            return match.group(0)

    return re.sub(r"\d+", repl, text)


def normalize_greek_letters(text: str) -> str:
    for char, replacement in GREEK_LETTERS.items():
        text = text.replace(char, replacement)
    return text


def normalize_math_symbols(text: str) -> str:
    for char, replacement in MATH_SYMBOLS.items():
        text = text.replace(char, replacement)
    return text


def normalize_standalone_currency(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return CURRENCY_STANDALONE[match.group(0)]

    return re.sub(r"(?<!\S)([$€£¥₽₴₸₺₹¢])(?!\S)", repl, text)


def normalize_numerals(text: str, options: NormalizeOptions | None = None) -> str:
    del options
    text = normalize_numeric_unit_ranges(text)
    text = normalize_cardinal_numerals(text)
    text = normalize_remaining_post_numeral_abbreviations(text)
    text = normalize_greek_letters(text)
    text = normalize_math_symbols(text)
    text = normalize_standalone_currency(text)
    text = normalize_all_digits_everywhere(text)
    return text


def normalize_decimals(text: str) -> str:
    pattern = re.compile(
        rf"(?<!\d)(?P<num>(?:-|{re.escape(NEGATIVE_NUMBER_PLACEHOLDER)})?\d+[.,]\d+)(?:\s*(?P<unit>[а-яА-ЯёЁa-zA-Z%°$€₽Ω]+)(?P<unit_dot>\.)?)?(?:\s+(?P<unit2>[а-яА-ЯёЁa-zA-Z%°$€₽Ω]+)(?P<unit2_dot>\.)?)?(?!\d)"
    )

    def repl(match: re.Match[str]) -> str:
        s = match.group("num").replace(",", ".")
        unit_raw = match.group("unit")
        start_pos = match.start()
        context = text[max(0, start_pos - 40) : start_pos]
        tokens_left = simple_tokenize(context)
        case = get_numeral_case(tokens_left + [s], len(tokens_left))
        is_negative = s.startswith("-") or s.startswith(NEGATIVE_NUMBER_PLACEHOLDER)
        abs_s = s.lstrip(f"-{NEGATIVE_NUMBER_PLACEHOLDER}")
        parts = abs_s.split(".")
        if len(parts) != 2:
            return match.group(0)
        int_part_s, frac_part_s = parts
        int_val = int(int_part_s)
        frac_val = int(frac_part_s)
        digits = len(frac_part_s)
        order_names = {
            1: "десятая",
            2: "сотая",
            3: "тысячная",
            4: "десятитысячная",
            5: "стотысячная",
            6: "миллионная",
        }
        order_name_base = order_names.get(digits, "десятитысячная")
        morph = get_morph()
        int_words = inflect_numeral_string(int_part_s, case, gender="femn")
        p_cel = morph.parse("целая")[0]
        tags_cel = (
            {case, "femn", "sing"}
            if int_val % 10 == 1 and int_val % 100 != 11
            else ({"gent", "plur"} if case in ["nomn", "accs"] else {case, "plur"})
        )
        cel_words = safe_inflect(p_cel, tags_cel)
        frac_words = inflect_numeral_string(frac_part_s, case, gender="femn")
        p_order = morph.parse(order_name_base)[0]
        tags_order = (
            {case, "femn", "sing"}
            if frac_val % 10 == 1 and frac_val % 100 != 11
            else ({"gent", "plur"} if case in ["nomn", "accs"] else {case, "plur"})
        )
        order_words = safe_inflect(p_order, tags_order)
        result = f"{int_words} {cel_words} {frac_words} {order_words}"
        if unit_raw:
            unit_dot = match.group("unit_dot")
            unit_lower = unit_raw.lower().strip(".")
            unit_info = UNITS_DATA.get(unit_lower)
            unit2_raw = match.group("unit2")
            unit2_dot = match.group("unit2_dot")
            unit2_processed = False
            if unit_info:
                lemma, _, _, *u_suffix = unit_info
                p_unit = morph.parse(lemma)[0]
                result += " " + safe_inflect(p_unit, {"gent", "sing"})
                if u_suffix:
                    result += " " + u_suffix[0]
                if unit2_raw:
                    unit2_lower = unit2_raw.lower().strip(".")
                    unit2_info = UNITS_DATA.get(unit2_lower)
                    multipliers = {"тысяча", "миллион", "миллиард", "триллион"}
                    if lemma in multipliers and unit2_info:
                        lemma2, _, _, *suffix2 = unit2_info
                        p_unit2 = morph.parse(lemma2)[0]
                        result += " " + safe_inflect(p_unit2, {"gent", "plur"})
                        if suffix2:
                            result += " " + suffix2[0]
                        unit2_processed = True
                if unit2_raw and not unit2_processed:
                    result += " " + unit2_raw
            else:
                result += " " + unit_raw
                if unit2_raw:
                    result += " " + unit2_raw
            if (
                unit2_dot
                and unit2_raw
                and _should_keep_decimal_unit_dot(text[match.end() :])
            ):
                result += "."
            elif (
                unit_dot
                and not unit2_raw
                and _should_keep_decimal_unit_dot(text[match.end() :])
            ):
                result += "."
        if is_negative:
            result = "минус " + result
        return result

    return pattern.sub(repl, text)


def normalize_fractions(text: str) -> str:
    pattern = re.compile(r"(?<![\d,])(\d+)/(\d+)(?![\d,])")

    def repl(match: re.Match[str]) -> str:
        num = int(match.group(1))
        denom = int(match.group(2))
        context = text[max(0, match.start() - 10) : match.start()].lower()
        case = "nomn"
        if re.search(r"\b(с|со|от|до|из|без|у)\s+$", context):
            case = "gent"
        elif re.search(r"\b(к|по)\s+$", context):
            case = "datv"
        elif re.search(r"\b(в|на|через)\s+$", context):
            case = "accs"
        elif re.search(r"\b(о|об|при)\s+$", context):
            case = "loct"
        try:
            num_text = num2words.num2words(num, lang="ru")
        except Exception:
            return match.group(0)
        morph = get_morph()
        if case != "nomn":
            num_text = " ".join(
                (p.inflect({case}).word if p.inflect({case}) else part)
                for part in num_text.split()
                for p in [morph.parse(part)[0]]
            )
        last_num_word = num_text.split()[-1]
        p_last = morph.parse(last_num_word)[0]
        if num % 10 == 1 and num % 100 != 11:
            inf = p_last.inflect({case, "femn", "sing"})
            if inf:
                arr = num_text.split()
                arr[-1] = inf.word
                num_text = " ".join(arr)
        elif num % 10 == 2 and num % 100 != 12 and case in ["nomn", "accs"]:
            inf = p_last.inflect({case, "femn"})
            if inf:
                arr = num_text.split()
                arr[-1] = inf.word
                num_text = " ".join(arr)
        try:
            denom_text = num2words.num2words(denom, lang="ru", to="ordinal")
        except Exception:
            return match.group(0)
        words = denom_text.split()
        p = morph.parse(words[-1])[0]
        is_sing_1 = num % 10 == 1 and num % 100 != 11
        inflected = p.inflect(
            {case, "femn", "sing"}
            if is_sing_1
            else ({"gent", "plur"} if case in ["nomn", "accs"] else {case, "plur"})
        )
        if inflected:
            words[-1] = inflected.word
        return f"{num_text} {' '.join(words)}"

    return pattern.sub(repl, text)


def normalize_hyphenated_words(text: str) -> str:
    pattern = re.compile(r"(?<![\d])(\d+)-([а-яА-ЯёЁ]{1,})")

    def repl(match: re.Match[str]) -> str:
        morph = get_morph()
        num_str = match.group(1)
        word = match.group(2)
        word_lower = word.lower()
        ordinal_suffixes = {"й", "я", "е", "го", "му", "м", "ю", "ее", "ий", "ая", "ое"}
        cardinal_case_suffixes = {"ти", "ми", "х", "мя", "и"}
        if word_lower in ordinal_suffixes:
            return match.group(0)
        if (
            word_lower
            in {
                "ый",
                "ой",
                "й",
                "ого",
                "го",
                "ому",
                "ым",
                "ом",
                "му",
                "е",
                "х",
                "м",
                "ми",
            }
            and int(num_str) > 100
        ):
            return match.group(0)
        try:
            int(num_str)
        except Exception:
            return match.group(0)
        case_from_suffix = None
        if word_lower == "х":
            case_from_suffix = None
        elif word_lower in ("ти", "и"):
            case_from_suffix = "gent"
        elif word_lower in ("ми", "мя"):
            case_from_suffix = "ablt"
        ctx_left = text[max(0, match.start() - 60) : match.start()]
        ctx_right = text[match.end() : match.end() + 60]
        tokens_left = simple_tokenize(ctx_left)
        tokens_right = simple_tokenize(ctx_right)
        context_case = get_numeral_case(
            tokens_left + [num_str] + tokens_right, len(tokens_left)
        )
        if case_from_suffix:
            case = case_from_suffix
        elif word_lower == "х":
            case = context_case if context_case in ("gent", "loct") else "gent"
        else:
            case = context_case
        p_word = morph.parse(word_lower)[0]
        is_adj_like = "ADJF" in p_word.tag or word_lower.endswith(
            (
                "дневный",
                "часовой",
                "минутный",
                "летний",
                "этажный",
                "тонный",
                "процентный",
                "кратный",
                "кратного",
                "кратном",
                "кратных",
            )
        )
        target_case = "gent" if is_adj_like and case == "nomn" else case
        num_words = inflect_numeral_string(num_str, target_case)
        if word_lower in cardinal_case_suffixes:
            return num_words
        return (
            f"{num_words}{word}"
            if is_adj_like
            else (f"{num_words}" if len(word) <= 3 else f"{num_words} {word}")
        )

    return pattern.sub(repl, text)


def normalize_ordinals(text: str) -> str:
    pattern = re.compile(r"(\d+)-([а-яА-ЯёЁ]{1,3})\b", re.IGNORECASE | re.UNICODE)

    def repl(match: re.Match[str]) -> str:
        morph = get_morph()
        num_str = match.group(1)
        suffix = match.group(2).lower()
        try:
            num = int(num_str)
        except ValueError:
            return match.group(0)
        gender = "masc"
        is_cardinal_suffix = suffix in ("ти", "ми")
        ctx_left = text[max(0, match.start() - 60) : match.start()]
        ctx_right = text[match.end() : match.end() + 60]
        tokens_left = simple_tokenize(ctx_left)
        tokens_right = simple_tokenize(ctx_right)
        case = get_numeral_case(
            tokens_left + [num_str] + tokens_right, len(tokens_left)
        )
        if suffix in ("я", "яя"):
            gender = "femn"
        elif suffix in ("е", "ее"):
            gender = "neut"
        elif suffix == "й" and tokens_right:
            p_next = morph.parse(tokens_right[0].strip(".,!?;:"))[0]
            if "femn" in p_next.tag:
                gender = "femn"
                if case == "nomn":
                    case = "gent"
        case_from_suffix = None
        if suffix == "го":
            case_from_suffix = "gent"
        elif suffix == "му":
            case_from_suffix = "datv"
        elif suffix == "й" and case == "nomn" and tokens_right:
            p_next = morph.parse(tokens_right[0].strip(".,!?;:"))[0]
            if "femn" in p_next.tag:
                gender = "femn"
                case_from_suffix = "gent"
        if suffix == "м":
            if tokens_right:
                p_next = morph.parse(tokens_right[0].strip(".,!?;:"))[0]
                case_from_suffix = "loct" if "sing" in p_next.tag else "datv"
            else:
                case_from_suffix = "loct"
        case = case_from_suffix or case
        plural = suffix in ("х", "ми", "е", "м") and not (
            suffix == "м" and case == "loct"
        )
        cases_map = {
            "nomn": "nominative",
            "gent": "genitive",
            "datv": "dative",
            "accs": "accusative",
            "ablt": "instrumental",
            "loct": "prepositional",
        }
        gender_map = {"masc": "m", "femn": "f", "neut": "n"}
        if case in cases_map:
            try:
                kwargs = {"case": cases_map[case]}
                if not is_cardinal_suffix:
                    kwargs["to"] = "ordinal"
                if plural:
                    kwargs["plural"] = True
                elif gender in gender_map and not is_cardinal_suffix:
                    kwargs["gender"] = gender_map[gender]
                return num2words.num2words(num, lang="ru", **kwargs) + " "
            except Exception:
                pass
        try:
            ordinal = num2words.num2words(
                num, lang="ru", to="cardinal" if is_cardinal_suffix else "ordinal"
            )
        except Exception:
            return match.group(0)
        words = ordinal.split()
        if not words:
            return ordinal
        parsed = morph.parse(words[-1])
        if parsed:
            p = parsed[0]
            target_tags = {case}
            if plural:
                target_tags.add("plur")
            elif gender:
                target_tags.add(gender)
            inflected = p.inflect(target_tags)
            if inflected:
                words[-1] = inflected.word
        return " ".join(words) + " "

    return pattern.sub(repl, text)
