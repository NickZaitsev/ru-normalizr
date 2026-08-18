from __future__ import annotations

import re

from .placeholders import NEGATIVE_NUMBER_PLACEHOLDER

#: Порядок альтернатив здесь — это правила разрешения неоднозначностей, а не
#: оформление: каждая следующая ветка ловит только то, что не забрала
#: предыдущая. «А.С.П.» должно уйти в инициалы раньше, чем в «слово + точка»,
#: а «Ту-154» — раньше, чем в отдельные «Ту», «-», «154». Переставить ветки
#: значит поменять разбиение на токены, поэтому порядок закреплён тестом
#: `tests/test_text_context.py`.
TOKEN_PATTERN = re.compile(
    rf"""
      \n+                                  # прогон переводов строки — граница абзаца
    | {re.escape(NEGATIVE_NUMBER_PLACEHOLDER)} \d+ (?:[.,]\d+)?
                                           # защищённое отрицательное число вместе со знаком
    | (?:[^\W\d_]\.)+ - [^\W\d_]+ \.       # «ген.-майор.» — сокращение через дефис
    | (?:[A-ZА-ЯЁ]\.){{2,}} [A-ZА-ЯЁ]? \.? # инициалы «А.С.П.» одним токеном
    | \d+ - [A-Za-z]+                      # «5-th» — число с латинским наращением
    | [^\W\d_]+ - \d+                      # «Ту-154» — слово с числовым индексом
    | \d+                                  # число
    | \+? [^\W\d_]+ (?:[-+][^\W\d_]+)+     # «жёлто-зелёный», «плюс-минус»
    | \+? [^\W\d_]+                        # обычное слово
    | [$€₽£¥₴₸₺₹¢₪₩₫₱₦]                    # знак валюты
    | [^\w\s]                              # любой другой одиночный знак
    """,
    flags=re.UNICODE | re.VERBOSE,
)
PUNCT_STRIP = '.,:;!"«»()[]{}'


def simple_tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text)


def tokenize_with_spans(text: str) -> tuple[list[str], list[tuple[int, int]]]:
    """Tokens plus their source spans, so a rewrite can splice replacements
    back into the original text and keep every untouched character intact."""
    tokens: list[str] = []
    spans: list[tuple[int, int]] = []
    for match in TOKEN_PATTERN.finditer(text):
        tokens.append(match.group(0))
        spans.append((match.start(), match.end()))
    return tokens, spans


def normalize_context_token(token: str) -> str:
    return token.lower().strip(PUNCT_STRIP)
