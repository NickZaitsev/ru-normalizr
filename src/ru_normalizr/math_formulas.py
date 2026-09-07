"""Озвучивание математики: блок ``$…$`` превращается в русские слова.

Исходники научных книг несут вёрстку TeX прямо в тексте: ``$\\omega$``,
``$\\frac{2400}{84}$``, ``$\\sqrt{ar}$``. Синтезатор читает это как набор
случайных звуков, а сам знак ``$`` и фигурные скобки вообще не имеют
произношения. Замер по 1057 боевым частям: 3626 блоков в 22 книгах, 91
уникальная команда, у худшей книги 1587 блоков.

Знак доллара при этом остаётся знаком доллара. ``$100 тыс. до $250 тыс.``
внешне выглядит как блок, поэтому телом формулы считается только то, что
устроено как формула: либо внутри есть команда со слешем, либо каждое слово
внутри — число, одиночная переменная или оператор, и при этом есть латинская
буква или знак сравнения. Правило проверено на 740 книгах: три ложных
срабатывания вида ``, 1`` отсекаются требованием буквы или сравнения.

Чего эта стадия сознательно не делает: греческие слова, набранные по буквам
(``$\\delta\\tilde{\\eta}\\mu\\circ\\varsigma$`` — δῆμος), читаются именами
букв, «дельта эта мю омикрон сигма». Таких блоков во всём каталоге 18 против
1620 формул, и отдельное правило транслитерации не стоит своей сложности.
"""

from __future__ import annotations

import re

#: Греческие буквы. Заглавная команда читается тем же словом: разница только на
#: письме, вслух ``\Delta`` и ``\delta`` — «дельта».
_GREEK: dict[str, str] = {
    "alpha": "альфа",
    "beta": "бета",
    "gamma": "гамма",
    "delta": "дельта",
    "epsilon": "эпсилон",
    "varepsilon": "эпсилон",
    "zeta": "дзета",
    "eta": "эта",
    "theta": "тета",
    "vartheta": "тета",
    "iota": "иота",
    "kappa": "каппа",
    "varkappa": "каппа",
    "lambda": "ламбда",
    "mu": "мю",
    "nu": "ню",
    "xi": "кси",
    "omicron": "омикрон",
    "pi": "пи",
    "rho": "ро",
    "sigma": "сигма",
    "varsigma": "сигма",
    "tau": "тау",
    "upsilon": "ипсилон",
    "phi": "фи",
    "varphi": "фи",
    "chi": "хи",
    "psi": "пси",
    "omega": "омега",
}

#: Операторы, отношения и знаки. Слова подобраны так, как формулу читают вслух,
#: а не так, как её называют в учебнике: «умножить на», не «оператор умножения».
_OPERATORS: dict[str, str] = {
    "times": "умножить на",
    "cdot": "умножить на",
    "div": "делить на",
    "pm": "плюс минус",
    "mp": "минус плюс",
    "le": "меньше или равно",
    "leq": "меньше или равно",
    "leqslant": "меньше или равно",
    "ge": "больше или равно",
    "geq": "больше или равно",
    "geqslant": "больше или равно",
    "ll": "много меньше",
    "gg": "много больше",
    "ne": "не равно",
    "neq": "не равно",
    "approx": "примерно равно",
    "equiv": "тождественно равно",
    "cong": "равно",
    "sim": "порядка",
    "propto": "пропорционально",
    "infty": "бесконечность",
    "in": "принадлежит",
    "notin": "не принадлежит",
    "ni": "содержит",
    "subset": "подмножество",
    "subseteq": "подмножество",
    "supset": "надмножество",
    "supseteq": "надмножество",
    "cup": "объединение",
    "bigcup": "объединение",
    "cap": "пересечение",
    "bigcap": "пересечение",
    "setminus": "без",
    "emptyset": "пустое множество",
    "varnothing": "пустое множество",
    "forall": "для любого",
    "exists": "существует",
    "nexists": "не существует",
    "neg": "не",
    "not": "не",
    "land": "и",
    "lor": "или",
    "wedge": "и",
    "vee": "или",
    "to": "стремится к",
    "rightarrow": "стремится к",
    "longrightarrow": "стремится к",
    "leftarrow": "следует из",
    "Rightarrow": "следует",
    "implies": "следует",
    "Leftarrow": "следует из",
    "leftrightarrow": "равносильно",
    "Leftrightarrow": "равносильно",
    "iff": "равносильно",
    "mapsto": "переходит в",
    "mid": "такой что",
    "perp": "перпендикулярно",
    "parallel": "параллельно",
    "oplus": "прямая сумма",
    "otimes": "тензорное произведение",
    "odot": "произведение",
    "bigcirc": "кружок",
    "triangle": "треугольник",
    "sum": "сумма",
    "prod": "произведение",
    "int": "интеграл",
    "iint": "двойной интеграл",
    "oint": "контурный интеграл",
    "partial": "частная производная",
    "nabla": "набла",
    "lim": "предел",
    "inf": "инфимум",
    "sup": "супремум",
    "min": "минимум",
    "max": "максимум",
    "log": "логарифм",
    "ln": "натуральный логарифм",
    "lg": "десятичный логарифм",
    "exp": "экспонента",
    "sin": "синус",
    "cos": "косинус",
    "tan": "тангенс",
    "tg": "тангенс",
    "cot": "котангенс",
    "ctg": "котангенс",
    "arcsin": "арксинус",
    "arccos": "арккосинус",
    "arctan": "арктангенс",
    "degree": "градусов",
    "circ": "градусов",
    "prime": "штрих",
    "sharp": "диез",
    "flat": "бемоль",
    "aleph": "алеф",
    "dots": "и так далее",
    "ldots": "и так далее",
    "cdots": "и так далее",
    "vdots": "и так далее",
    "quad": "",
    "qquad": "",
    ",": "",
    ";": "",
    ":": "",
    "!": "",
}

#: Команды-обёртки: сами не звучат, а содержимое читается как есть. Сюда же
#: диакритика над переменной (``\dot{x}``) — вслух её никто не проговаривает.
_TRANSPARENT: frozenset[str] = frozenset(
    {
        "text",
        "textrm",
        "textit",
        "textbf",
        "mathrm",
        "mathsf",
        "mathbf",
        "mathit",
        "mathcal",
        "mathfrak",
        "mathbb",
        "operatorname",
        "stackrel",
        "left",
        "right",
        "big",
        "Big",
        "bigg",
        "Bigg",
        "displaystyle",
        "limits",
        "dot",
        "ddot",
        "tilde",
        "hat",
        "widehat",
        "bar",
        "overline",
        "vec",
        "acute",
        "grave",
        "breve",
        "check",
    }
)

#: Одиночные знаки внутри формулы.
_SYMBOLS: dict[str, str] = {
    "=": " равно ",
    "+": " плюс ",
    "-": " минус ",
    "−": " минус ",
    "*": " умножить на ",
    "/": " делить на ",
    "<": " меньше ",
    ">": " больше ",
    "%": " процент ",
    "(": " ",
    ")": " ",
    "[": " ",
    "]": " ",
    "{": " ",
    "}": " ",
    "|": " ",
    "\\": " ",
    "&": " ",
    "'": " штрих ",
}

#: Тело длиннее этого — уже не формула, а знак доллара через полстраницы.
_MAX_BODY_CHARS = 200

_BLOCK_RE = re.compile(rf"\$\$?([^$]{{1,{_MAX_BODY_CHARS}}}?)\$\$?", re.S)
_COMMAND_RE = re.compile(r"\\([A-Za-z]+)")
_ANY_COMMAND_RE = re.compile(r"\\([A-Za-z]+|[,;:!])")
_NUMBER_RE = re.compile(r"^[0-9]+(?:[.,][0-9]+)?$")
_VARIABLE_RE = re.compile(r"^[A-Za-z](?:[_^][0-9A-Za-z]+)?$")
_COEFFICIENT_RE = re.compile(r"^[0-9]+(?:[.,][0-9]+)?[A-Za-z]$")
_OPERATOR_TOKEN_RE = re.compile(r"^[=+\-*/^_<>()|,{}]+$")
_COMPARISON_RE = re.compile(r"[=<>^_]")
_LATIN_RE = re.compile(r"[A-Za-z]")

_FRAC_RE = re.compile(r"\\(?:d|t)?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_ROOT_DEGREE_RE = re.compile(r"\\sqrt\s*\[([^\[\]]*)\]\s*\{([^{}]*)\}")
_ROOT_RE = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_TRANSPARENT_RE = re.compile(r"\\([A-Za-z]+)\s*\{([^{}]*)\}")
#: ``90^\circ`` — это «90 градусов», а не «90 в степени градусов».
_DEGREE_RE = re.compile(r"\^\s*\{?\s*\\(?:circ|degree)\s*\}?")
#: ``60X`` — коэффициент при переменной: без пробела стадия числительных
#: склеивает его в «шестьдесят-X».
_COEFFICIENT_SPLIT_RE = re.compile(r"(?<=[0-9])(?=[A-Za-z])")
#: ``L_\omega`` и ``0^\sharp``: команда после ``_`` или ``^`` — это и есть
#: аргумент, но без скобок его не видят обработчики ниже.
_SCRIPT_COMMAND_RE = re.compile(r"([_^])\s*(\\[A-Za-z]+)")
_POWER_BRACED_RE = re.compile(r"\^\s*\{([^{}]*)\}")
_POWER_SHORT_RE = re.compile(r"\^\s*([0-9A-Za-z])")
_INDEX_BRACED_RE = re.compile(r"_\s*\{([^{}]*)\}")
_INDEX_SHORT_RE = re.compile(r"_\s*([0-9A-Za-z])")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_SPACE_BEFORE_PUNCT_RE = re.compile(r" +(?=[,.;:!?])")


def is_math_body(body: str) -> bool:
    """Это тело формулы, а не текст между двумя знаками доллара?"""
    if not body or "\n\n" in body:
        return False
    if _COMMAND_RE.search(body):
        return True
    tokens = body.split()
    if not tokens:
        return False
    for token in tokens:
        if not (
            _NUMBER_RE.match(token)
            or _VARIABLE_RE.match(token)
            or _COEFFICIENT_RE.match(token)
            or _OPERATOR_TOKEN_RE.match(token)
        ):
            return False
    # Без латинской буквы и без знака сравнения «, 1» между двумя суммами в
    # долларах не отличить от формулы, а цена ошибки — сломанная фраза.
    return bool(_LATIN_RE.search(body) or _COMPARISON_RE.search(body))


def _expand_nested(pattern: re.Pattern[str], replace, text: str) -> str:
    """Раскрывать вложенные конструкции изнутри наружу, пока они есть."""
    for _ in range(10):
        expanded = pattern.sub(replace, text)
        if expanded == text:
            return expanded
        text = expanded
    return text


#: Команды со своей структурой: их разбирают отдельные правила, и общий
#: обработчик обёрток обязан пройти мимо, иначе у ``\frac{a}{b}`` он съест
#: первую группу и дробь останется без знаменателя.
_STRUCTURAL: frozenset[str] = frozenset({"frac", "dfrac", "tfrac", "sqrt"})


def _replace_transparent(match: re.Match[str]) -> str:
    name, inner = match.group(1), match.group(2)
    if name in _STRUCTURAL:
        return match.group(0)
    if name in _TRANSPARENT:
        return f" {inner} "
    if name in _GREEK or name in _OPERATORS:
        return match.group(0)
    # Незнакомая команда: содержимое читаем, само имя вслух не произносим —
    # иначе слушатель получает «мэсзфрак».
    return f" {inner} "


def _replace_command(match: re.Match[str]) -> str:
    name = match.group(1)
    if name in _GREEK:
        return f" {_GREEK[name]} "
    if name in _OPERATORS:
        return f" {_OPERATORS[name]} "
    # Заглавная греческая команда читается тем же словом: \Delta — «дельта».
    capital = _GREEK.get(name[:1].lower() + name[1:])
    if capital is not None:
        return f" {capital} "
    return " "


def speak_formula(body: str) -> str:
    """Перевести тело формулы в слова, оставив числа цифрами для стадии числительных."""
    text = body
    # Структурные правила и обёртки раскрываются одним циклом: у вложенной
    # дроби внешние скобки чисты только после того, как \text внутри неё уже
    # раскрыт, а внутренняя дробь — только после раскрытия внешней обёртки.
    for _ in range(10):
        before = text
        text = _TRANSPARENT_RE.sub(_replace_transparent, text)
        text = _FRAC_RE.sub(lambda m: f" {m.group(1)} дробь {m.group(2)} ", text)
        text = _ROOT_DEGREE_RE.sub(
            lambda m: f" корень степени {m.group(1)} из {m.group(2)} ", text
        )
        text = _ROOT_RE.sub(lambda m: f" корень из {m.group(1)} ", text)
        if text == before:
            break
    text = _DEGREE_RE.sub(" градусов ", text)
    text = _SCRIPT_COMMAND_RE.sub(lambda m: f"{m.group(1)}{{{m.group(2)}}}", text)
    text = _expand_nested(_POWER_BRACED_RE, lambda m: f" в степени {m.group(1)} ", text)
    text = _POWER_SHORT_RE.sub(lambda m: f" в степени {m.group(1)} ", text)
    text = _expand_nested(_INDEX_BRACED_RE, lambda m: f" индекс {m.group(1)} ", text)
    text = _INDEX_SHORT_RE.sub(lambda m: f" индекс {m.group(1)} ", text)
    text = _ANY_COMMAND_RE.sub(_replace_command, text)
    text = "".join(_SYMBOLS.get(char, char) for char in text)
    text = _COEFFICIENT_SPLIT_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def normalize_math(text: str) -> str:
    """Заменить блоки ``$…$`` на их произношение, не тронув суммы в долларах."""
    if "$" not in text:
        return text

    def replace(match: re.Match[str]) -> str:
        body = match.group(1)
        if not is_math_body(body):
            return match.group(0)
        spoken = speak_formula(body)
        if not spoken:
            return " "
        return f" {spoken} "

    result = _BLOCK_RE.sub(replace, text)
    result = _MULTI_SPACE_RE.sub(" ", result)
    return _SPACE_BEFORE_PUNCT_RE.sub("", result)


def math_block_count(text: str) -> tuple[int, int]:
    """Сколько блоков формул в тексте и сколько из них длиннее 25 символов.

    Второе число — мера сложности: одиночное ``$\\omega$`` читается нормально, а
    ``$\\frac{2400 - 60X}{84} \\times 1,5$`` вслух остаётся кашей при любой
    таблице. Вызывающий код решает по нему, стоит ли вообще озвучивать книгу.
    """
    if "$" not in text:
        return 0, 0
    total = 0
    complex_blocks = 0
    for match in _BLOCK_RE.finditer(text):
        body = match.group(1)
        if not is_math_body(body):
            continue
        total += 1
        if len(body) > 25:
            complex_blocks += 1
    return total, complex_blocks


__all__ = ["is_math_body", "math_block_count", "normalize_math", "speak_formula"]
