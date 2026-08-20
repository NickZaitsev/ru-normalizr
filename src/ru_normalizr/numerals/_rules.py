"""Механика упорядоченных правил выбора падежа числительного.

Выбор падежа — это список эвристик, у которых порядок сам является контрактом:
верхнее правило заслоняет нижнее. Раньше список был телом одной функции на
несколько сотен строк, и добавить правило, не задев соседнее, было нельзя. Здесь
лежит только механика — именованное правило, контекст и цикл; сами правила и их
словари живут в `_helpers.py`, потому что им нужна морфология оттуда, а
`get_numeral_case` оттуда же импортируют другие модули.

Правило — одна функция `decide(ctx) -> str | None`: `None` значит «не про меня,
спрашивайте дальше». Разделения на `applies` и `result` здесь нет намеренно:
половина правил, чтобы ответить «моё ли это», просматривает окно из пяти-шести
токенов с разбором морфологии, и при двух вызовах эта работа делалась бы дважды.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace

from .._morph import MorphParse, first_parse_required
from ..text_context import normalize_context_token

#: Токены-тире: с них начинается диапазон и ими же обрывается левый контекст.
DASH_TOKENS = frozenset({"-", "–", "—"})


@dataclass(frozen=True, slots=True)
class NumeralContext:
    """Окно вокруг числа, из которого правила выбирают падеж.

    `visible_length` — граница, за которую смотреть нельзя: вызывающий код
    прячет хвост токенов, который ещё не отнормализован. Все методы доступа её
    соблюдают, поэтому правило не может случайно прочитать невидимый токен.
    """

    tokens: list[str]
    idx: int
    visible_length: int
    left_scan_starts: tuple[int, ...]
    #: Памятки по абсолютной позиции токена: правила спрашивают одних и тех же
    #: соседей по очереди, и привести токен к виду для сравнений выходит дороже,
    #: чем сама проверка. Ключ абсолютный, поэтому памятки безопасно делить с
    #: контекстом, полученным из `at`.
    _words: dict[int, str] = field(default_factory=dict, repr=False)
    _parses: dict[int, MorphParse] = field(default_factory=dict, repr=False)

    @property
    def token(self) -> str:
        """Сам числовой токен."""
        return self.tokens[self.idx]

    @property
    def left_scan_start(self) -> int:
        """Левая граница предложения: дальше неё контекст не читается."""
        return self.left_scan_starts[self.idx]

    @property
    def is_range_start(self) -> bool:
        """Число — левая граница диапазона («2-3 ошибки»)."""
        return self.idx < self.visible_length - 1 and self.tokens[self.idx + 1] in DASH_TOKENS

    def raw(self, offset: int) -> str:
        """Токен на смещении `offset` как есть; за границами — пустая строка."""
        position = self.idx + offset
        if position < 0 or position >= self.visible_length:
            return ""
        return self.tokens[position]

    def word(self, offset: int) -> str:
        """Токен на смещении `offset`, приведённый к виду для сравнений."""
        position = self.idx + offset
        if position < 0 or position >= self.visible_length:
            return ""
        cached = self._words.get(position)
        if cached is None:
            cached = normalize_context_token(self.tokens[position])
            self._words[position] = cached
        return cached

    def parse(self, offset: int) -> MorphParse | None:
        """Разбор приведённого токена на смещении; `None` — токена нет.

        Разбор запоминается: соседа слева спрашивают шесть правил подряд.
        """
        position = self.idx + offset
        if position < 0 or position >= self.visible_length:
            return None
        cached = self._parses.get(position)
        if cached is not None:
            return cached
        word = self.word(offset)
        if not word:
            return None
        parsed = first_parse_required(word)
        self._parses[position] = parsed
        return parsed

    def at(self, idx: int) -> NumeralContext:
        """Тот же контекст, но про другое число — для правил-ссылок на сосед."""
        return replace(self, idx=idx)


#: Правило выбора падежа. Имя уникально и кебаб-кейсом: оно попадает в
#: сообщения тестов и в отчёты аудита, поэтому должно читаться без кода.
@dataclass(frozen=True, slots=True)
class CaseRule:
    name: str
    decide: Callable[[NumeralContext], str | None]


def deciders(rules: Sequence[CaseRule]) -> tuple[Callable[[NumeralContext], str | None], ...]:
    """Развернуть список правил в кортеж их функций.

    Обход идёт по горячему пути — по разу на каждое число в тексте, — и брать
    `rule.decide` заново на каждом шаге значит платить лишний поиск атрибута на
    каждое правило. Список правил остаётся документацией приоритетов, а цикл
    получает готовые функции.
    """
    return tuple(rule.decide for rule in rules)


def run_rules(
    rules: Sequence[Callable[[NumeralContext], str | None]], ctx: NumeralContext
) -> str | None:
    """Первое сработавшее правило и есть ответ; `None` — не сработало ни одно."""
    for decide in rules:
        decision = decide(ctx)
        if decision is not None:
            return decision
    return None
