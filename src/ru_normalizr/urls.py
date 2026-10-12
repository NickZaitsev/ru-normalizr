from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .placeholders import URLS, PlaceholderAllocator
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
#: Домен без схемы узнаётся по домену верхнего уровня, и только по нему:
#: «Pz.IV», «Sd.Kfz», «report.txt» — не адреса, а код, сокращение и имя файла.
#: Реестр закрытый и растёт по требованию; кириллический «рф» недостижим, пока
#: `BARE_DOMAIN_PATTERN` держит латинский хвост.
KNOWN_TLDS = frozenset(
    (
        "ru", "su", "ua", "by", "kz", "com", "net", "org", "info", "biz",
        "io", "ai", "app", "dev", "me", "co", "uk", "de", "fr", "it", "es",
        "pl", "cz", "us", "tv", "fm", "edu", "gov", "mil", "int", "online",
        "site", "store", "blog", "news", "shop", "club", "pro", "xyz",
    )
)


def _bare_domain_tld(domain: str) -> str:
    """Домен верхнего уровня из совпадения без схемы, без пути и регистра."""
    host = domain.split("/", 1)[0]
    _head, _dot, tld = host.rpartition(".")
    return tld.casefold()


SOCIAL_HANDLE_PATTERN = compile_scan(
    r"(?<![\w@])@(?P<handle>[A-Za-z][A-Za-z0-9_]*)(?!\w)",
    re.IGNORECASE,
)
HASHTAG_PATTERN = compile_scan(
    r"(?<!\w)#(?P<tag>[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_]*)(?!\w)",
    re.IGNORECASE,
)
ALNUM_CHUNK_PATTERN = compile_scan(r"[A-Za-z0-9]+|[^A-Za-z0-9]")
# Только ASCII-цифры: таблица DIGIT_WORDS собрана под них, а «\d» в Python
# ловит и арабо-индийские цифры из персидских ссылок.
MIXED_CHUNK_PATTERN = compile_scan(r"[0-9]+|[A-Za-z]+")
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


@dataclass(frozen=True, slots=True)
class ProtectedUrls:
    """Текст со спрятанными URL и средство вернуть их на место.

    Раньше все URL прятались за ОДИН символ, а восстанавливались по порядку
    списка: если стадия переставляла или удаляла фрагменты, второй URL
    подставлялся на место первого. Теперь у каждого URL свой заменитель, и
    восстановление не зависит ни от порядка, ни от числа выживших.
    """

    text: str
    allocator: PlaceholderAllocator | None = None

    def restore(self, text: str) -> str:
        if self.allocator is None:
            return text
        return self.allocator.restore(text)


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


def protect_urls(text: str) -> ProtectedUrls:
    if not URL_PATTERN.search(text):
        return ProtectedUrls(text)

    allocator = PlaceholderAllocator(URLS, text)

    def repl(match: re.Match[str]) -> str:
        raw_url = match.group("url")
        url, suffix = _split_trailing_punctuation(raw_url)
        if not url:
            return raw_url
        placeholder = allocator.allocate(url)
        if placeholder is None:
            return raw_url
        return f"{placeholder}{suffix}"

    protected_text = URL_PATTERN.sub(repl, text)
    if not len(allocator):
        return ProtectedUrls(text)
    return ProtectedUrls(protected_text, allocator)


def _is_ascii_digits(chunk: str) -> bool:
    """`str.isdigit()` верен по Unicode, а DIGIT_WORDS — только по ASCII."""
    return chunk.isascii() and chunk.isdigit()


def _read_digit_run(chunk: str) -> str:
    # Цифра вне таблицы остаётся собой: пропустить незнакомый символ лучше,
    # чем уронить нормализацию всей книги из-за одной ссылки.
    return " ".join(DIGIT_WORDS.get(digit, digit) for digit in chunk)


def _normalize_alnum_chunk(chunk: str) -> str:
    if _is_ascii_digits(chunk):
        return _read_digit_run(chunk)
    if chunk.isalpha():
        return chunk

    pieces: list[str] = []
    for part in MIXED_CHUNK_PATTERN.findall(chunk):
        if _is_ascii_digits(part):
            pieces.append(_read_digit_run(part))
        else:
            pieces.append(part)
    # Чужая письменность (персидские цифры и буквы в ссылке) не даёт ни одного
    # куска — возвращаем как есть, чтобы не потерять кусок адреса молча.
    return " ".join(piece for piece in pieces if piece) or chunk


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


def normalize_urls(text: str) -> str:
    if not (
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

    def normalize_bare_domain(match: re.Match[str]) -> str:
        if _bare_domain_tld(match.group("domain")) not in KNOWN_TLDS:
            return match.group(0)
        return normalize_bare(match)

    text = EMAIL_PATTERN.sub(normalize_bare, text)
    text = BARE_DOMAIN_PATTERN.sub(normalize_bare_domain, text)

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
