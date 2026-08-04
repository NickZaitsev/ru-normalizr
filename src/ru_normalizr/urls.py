from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(
    r"(?P<url>(?:(?<![\w@])https?://|(?<![\w@.-])www\.(?=[^\W_]))[^\s<>\"]+)",
    re.IGNORECASE,
)
ALNUM_CHUNK_PATTERN = re.compile(r"[A-Za-z0-9]+|[^A-Za-z0-9]")
MIXED_CHUNK_PATTERN = re.compile(r"\d+|[A-Za-z]+")

URL_SEPARATOR_WORDS: dict[str, str] = {
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
URL_PLACEHOLDER_RANGES = (
    (0xF0000, 0xFFFFD),
    (0x100000, 0x10FFFD),
)


@dataclass(frozen=True, slots=True)
class ProtectedUrls:
    text: str
    placeholder: str | None = None
    urls: tuple[str, ...] = ()

    def restore(self, text: str) -> str:
        if self.placeholder is None:
            return text
        for url in self.urls:
            if self.placeholder not in text:
                logger.error("URL placeholder disappeared before restoration")
                break
            text = text.replace(self.placeholder, url, 1)
        return text


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


def _choose_url_placeholder(text: str) -> str | None:
    occupied = set(text)
    for start, end in URL_PLACEHOLDER_RANGES:
        for codepoint in range(start, end + 1):
            candidate = chr(codepoint)
            if candidate not in occupied:
                return candidate
    logger.error("Unable to protect URLs: every private-use placeholder is occupied")
    return None


def protect_urls(text: str) -> ProtectedUrls:
    if not URL_PATTERN.search(text):
        return ProtectedUrls(text)

    placeholder = _choose_url_placeholder(text)
    if placeholder is None:
        return ProtectedUrls(text)

    urls: list[str] = []

    def repl(match: re.Match[str]) -> str:
        raw_url = match.group("url")
        url, suffix = _split_trailing_punctuation(raw_url)
        if not url:
            return raw_url
        urls.append(url)
        return f"{placeholder}{suffix}"

    protected_text = URL_PATTERN.sub(repl, text)
    if not urls:
        return ProtectedUrls(text)
    return ProtectedUrls(protected_text, placeholder, tuple(urls))


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
            pieces.append(URL_SEPARATOR_WORDS.get(char) or char)
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
