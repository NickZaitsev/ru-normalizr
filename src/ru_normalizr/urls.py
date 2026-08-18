from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .text_scan import compile_scan

logger = logging.getLogger(__name__)

URL_PATTERN = compile_scan(
    r"(?P<url>(?:(?<![\w@])https?://|(?<![\w@.-])www\.(?=[^\W_]))[^\s<>\"]+)",
    re.IGNORECASE,
)
EMAIL_PATTERN = compile_scan(
    r"(?<![\w@])(?P<email>[A-Za-z0-9][A-Za-z0-9._%+\-]*@"
    r"(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})(?!\w)",
    re.IGNORECASE,
)
BARE_DOMAIN_PATTERN = compile_scan(
    r"(?<![\w@.-])(?P<domain>(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}"
    r"(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?)(?!\w)",
    re.IGNORECASE,
)
SOCIAL_HANDLE_PATTERN = compile_scan(
    r"(?<![\w@])@(?P<handle>[A-Za-z][A-Za-z0-9_]*)(?!\w)",
    re.IGNORECASE,
)
HASHTAG_PATTERN = compile_scan(
    r"(?<!\w)#(?P<tag>[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_]*)(?!\w)",
    re.IGNORECASE,
)
ALNUM_CHUNK_PATTERN = compile_scan(r"[A-Za-z0-9]+|[^A-Za-z0-9]")
MIXED_CHUNK_PATTERN = compile_scan(r"\d+|[A-Za-z]+")
TAG_CHUNK_PATTERN = compile_scan(r"[A-Za-zА-Яа-яЁё]+|\d+|_")

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
    for match in ALNUM_CHUNK_PATTERN.finditer(url):
        chunk = match.group(0)
        if not chunk:
            continue
        if chunk.isalnum():
            if (
                chunk.casefold() == "ru"
                and match.start() > 0
                and url[match.start() - 1] == "."
            ):
                pieces.append("ру")
            elif chunk.casefold() == "docs":
                pieces.append("докс")
            else:
                pieces.append(_normalize_alnum_chunk(chunk))
            continue
        for char in chunk:
            pieces.append(URL_SEPARATOR_WORDS.get(char) or char)
    return re.sub(r"\s+", " ", " ".join(piece for piece in pieces if piece)).strip()


def normalize_urls(text: str, *, enabled: bool) -> str:
    if not enabled or not (
        URL_PATTERN.search(text)
        or EMAIL_PATTERN.search(text)
        or BARE_DOMAIN_PATTERN.search(text)
        or SOCIAL_HANDLE_PATTERN.search(text)
        or HASHTAG_PATTERN.search(text)
    ):
        return text

    def repl(match: re.Match[str]) -> str:
        raw_url = match.group("url")
        url, suffix = _split_trailing_punctuation(raw_url)
        if not url:
            return raw_url
        return f"{_normalize_url(url)}{suffix}"

    text = URL_PATTERN.sub(repl, text)

    def normalize_bare(match: re.Match[str]) -> str:
        raw_url = match.group("email") if "email" in match.groupdict() else match.group("domain")
        url, suffix = _split_trailing_punctuation(raw_url)
        if not url:
            return match.group(0)
        return f"{_normalize_url(url)}{suffix}"

    text = EMAIL_PATTERN.sub(normalize_bare, text)
    text = BARE_DOMAIN_PATTERN.sub(normalize_bare, text)

    def normalize_handle(match: re.Match[str]) -> str:
        parts = [part for part in re.split(r"(_)", match.group("handle")) if part]
        return "собака " + " ".join(
            "подчёркивание" if part == "_" else part for part in parts
        )

    def normalize_hashtag(match: re.Match[str]) -> str:
        parts: list[str] = []
        for part in TAG_CHUNK_PATTERN.findall(match.group("tag")):
            if part == "_":
                parts.append("подчёркивание")
            elif any("А" <= char <= "я" or char in "Ёё" for char in part):
                parts.append(part.casefold())
            else:
                parts.append(part)
        return "решётка " + " ".join(parts)

    text = SOCIAL_HANDLE_PATTERN.sub(normalize_handle, text)
    return HASHTAG_PATTERN.sub(normalize_hashtag, text)
