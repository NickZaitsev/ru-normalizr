from __future__ import annotations

import re

from .preprocess_utils import NEGATIVE_NUMBER_PLACEHOLDER, PARAGRAPH_BREAK_PLACEHOLDER

TOKEN_PATTERN = re.compile(
    rf"\n+|{re.escape(PARAGRAPH_BREAK_PLACEHOLDER)}+|{re.escape(NEGATIVE_NUMBER_PLACEHOLDER)}\d+(?:[.,]\d+)?|\d+-[A-Za-z]+|[^\W\d_]+-\d+|\d+|\+?[^\W\d_]+(?:[-+][^\W\d_]+)+|\+?[^\W\d_]+|[$€₽£¥₴₸₺₹¢₪₩₫₱₦]|[^\w\s]",
    flags=re.UNICODE,
)
PUNCT_STRIP = '.,:;!"«»()[]{}'


def simple_tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text)


def normalize_context_token(token: str) -> str:
    return token.lower().strip(PUNCT_STRIP)
