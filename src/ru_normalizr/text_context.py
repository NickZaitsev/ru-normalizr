from __future__ import annotations

import re

from .preprocess_utils import NEGATIVE_NUMBER_PLACEHOLDER

TOKEN_PATTERN = re.compile(
    rf"\n+|{re.escape(NEGATIVE_NUMBER_PLACEHOLDER)}\d+(?:[.,]\d+)?|(?:[^\W\d_]\.)+-[^\W\d_]+\.|(?:[A-ZА-ЯЁ]\.){{2,}}[A-ZА-ЯЁ]?\.?|\d+-[A-Za-z]+|[^\W\d_]+-\d+|\d+|\+?[^\W\d_]+(?:[-+][^\W\d_]+)+|\+?[^\W\d_]+|[$€₽£¥₴₸₺₹¢₪₩₫₱₦]|[^\w\s]",
    flags=re.UNICODE,
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
