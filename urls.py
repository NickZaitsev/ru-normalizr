from __future__ import annotations

import re

URL_PATTERN = re.compile(r"(?P<url>(?:https?://|www\.)[^\s<>\"]+)", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_PATTERN = re.compile(
    r"(?P<phone>(?<![\w/])(?:\+?\d[\d()\-\s]{8,}\d)(?![\w/]))"
)
ALNUM_CHUNK_PATTERN = re.compile(r"[A-Za-z0-9]+|[^A-Za-z0-9]")
MIXED_CHUNK_PATTERN = re.compile(r"\d+|[A-Za-z]+")

URL_SPECIAL_TOKENS = {
    "http": "эйч ти ти пи",
    "https": "эйч ти ти пи эс",
    "www": "три дабл ю",
    "com": "ком",
    "org": "орг",
    "net": "нэт",
    "ru": "ру",
    "mail": "мэил",
    "email": "имэил",
    "gmail": "джимэил",
    "me":"ми"
}

URL_SEPARATOR_WORDS = {
    ":": "двоеточие",
    "/": "слэш",
    ".": "точка",
    "?": "знак вопроса",
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


def _normalize_phone(phone: str) -> str:
    digits = "".join(char for char in phone if char.isdigit())
    if len(digits) < 10 or len(digits) > 15:
        return phone
    if phone.count("-") == 1 and "(" not in phone and ")" not in phone and "+" not in phone:
        return phone

    rendered = _read_digit_run(digits)
    if phone.lstrip().startswith("+"):
        return f"плюс {rendered}"
    return rendered


def _normalize_email(email: str) -> str:
    pieces: list[str] = []
    for chunk in ALNUM_CHUNK_PATTERN.findall(email):
        if not chunk:
            continue
        if chunk.isalnum():
            pieces.append(_normalize_alnum_chunk(chunk))
            continue
        for char in chunk:
            pieces.append(URL_SEPARATOR_WORDS.get(char, char))
    return re.sub(r"\s+", " ", " ".join(piece for piece in pieces if piece)).strip()


def _normalize_alnum_chunk(chunk: str) -> str:
    lowered = chunk.lower()
    if lowered in URL_SPECIAL_TOKENS:
        return URL_SPECIAL_TOKENS[lowered]
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
    if not enabled:
        return text

    def phone_repl(match: re.Match[str]) -> str:
        raw_phone = match.group("phone")
        return _normalize_phone(raw_phone)

    def email_repl(match: re.Match[str]) -> str:
        raw_email = match.group("email")
        return _normalize_email(raw_email)

    def repl(match: re.Match[str]) -> str:
        raw_url = match.group("url")
        url, suffix = _split_trailing_punctuation(raw_url)
        if not url:
            return raw_url
        return f"{_normalize_url(url)}{suffix}"

    text = PHONE_PATTERN.sub(phone_repl, text)
    text = EMAIL_PATTERN.sub(email_repl, text)
    return URL_PATTERN.sub(repl, text)
