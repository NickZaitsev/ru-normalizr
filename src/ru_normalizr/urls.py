from __future__ import annotations

import re

URL_PATTERN = re.compile(r"(?P<url>(?:https?://|www\.)[^\s<>\"]+)", re.IGNORECASE)
ALNUM_CHUNK_PATTERN = re.compile(r"[A-Za-z0-9]+|[^A-Za-z0-9]")
MIXED_CHUNK_PATTERN = re.compile(r"\d+|[A-Za-z]+")

URL_SEPARATOR_WORDS = {
    ":": "двоеточие",
    "/": "слэш",
    ".": "точка",
    "?": "вопрос",
    "&": "амперсанд",
    "=": "равно",
    "-": "дефис",
    "_": "нижнее подчёркивание",
    "#": "решётка",
    "%": "процент",
    "+": "плюс",
    "@": "собака",
    "~": "тильда",
}

DIGIT_WORDS = {
    "0": "ноль",
    "1": "один",
    "2": "два",
    "3": "три",
    "4": "четыре",
    "5": "пять",
    "6": "шесть",
    "7": "семь",
    "8": "восемь",
    "9": "девять",
}

TRAILING_URL_PUNCTUATION = ".,;:!?"
UNBALANCED_CLOSERS = {
    ")": "(",
    "]": "[",
    "}": "{",
}


def _split_trailing_punctuation(url: str) -> tuple[str, str]:
    suffix: list[str] = []

    while url and url[-1] in TRAILING_URL_PUNCTUATION:
        suffix.append(url[-1])
        url = url[:-1]

    while url and url[-1] in UNBALANCED_CLOSERS:
        closer = url[-1]
        opener = UNBALANCED_CLOSERS[closer]
        if url.count(closer) > url.count(opener):
            suffix.append(closer)
            url = url[:-1]
            continue
        break

    return url, "".join(reversed(suffix))


def _read_digit_run(chunk: str) -> str:
    return " ".join(DIGIT_WORDS[digit] for digit in chunk)


def _normalize_alnum_chunk(chunk: str) -> str:
    if chunk.isdigit():
        return _read_digit_run(chunk)
    if chunk.isalpha():
        return chunk

    pieces: list[str] = []
    for part in MIXED_CHUNK_PATTERN.findall(chunk):
        if part.isdigit():
            pieces.append(_read_digit_run(part))
        else:
            pieces.append(part)
    return " ".join(piece for piece in pieces if piece)


def _normalize_url(url: str) -> str:
    pieces: list[str] = []
    for chunk in ALNUM_CHUNK_PATTERN.findall(url):
        if not chunk:
            continue
        if chunk.isalnum():
            pieces.append(_normalize_alnum_chunk(chunk))
            continue
        for char in chunk:
            pieces.append(URL_SEPARATOR_WORDS.get(char, char))
    return re.sub(r"\s+", " ", " ".join(piece for piece in pieces if piece)).strip()


def normalize_urls(text: str, *, enabled: bool) -> str:
    if not enabled or not URL_PATTERN.search(text):
        return text

    def repl(match: re.Match[str]) -> str:
        raw_url = match.group("url")
        url, suffix = _split_trailing_punctuation(raw_url)
        if not url:
            return raw_url
        return f"{_normalize_url(url)}{suffix}"

    return URL_PATTERN.sub(repl, text)
