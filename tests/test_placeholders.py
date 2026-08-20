"""Тесты реестра служебных заменителей.

Пайплайн прячет URL, пути Windows, структурированные числа и буквенно-цифровые
коды за символы private use. Пока каждый клиент считал кодовые точки сам,
диапазоны пересекались: после 4096 защищённых числовых токенов номера заходили
в диапазон путей Windows, и восстановление подставляло путь на месте числа.
"""

from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

import pytest

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.normalizer import (
    STRUCTURED_NUMERIC_SUFFIX_PATTERN,
    protect_windows_paths,
)
from ru_normalizr.placeholders import (
    GLUED_CODES,
    NUMERAL_TOKENS,
    PREPROCESS_SENTINELS,
    RESERVED_PATTERN,
    RESERVED_RANGES,
    URLS,
    WINDOWS_PATHS,
    PlaceholderAllocator,
    PlaceholderRange,
    reserved_characters_in,
)
from ru_normalizr.urls import protect_urls


def test_reserved_ranges_do_not_overlap() -> None:
    """Пересечение диапазонов — это подстановка чужого фрагмента при восстановлении."""
    ordered = sorted(RESERVED_RANGES, key=lambda item: item.start)

    for earlier, later in pairwise(ordered):
        assert earlier.end < later.start, f"{earlier.name} пересекается с {later.name}"


def test_reserved_ranges_stay_inside_private_use() -> None:
    """Диапазон вне private use означал бы порчу осмысленного текста."""
    private_use = [(0xE000, 0xF8FF), (0xF0000, 0xFFFFD), (0x100000, 0x10FFFD)]

    for reserved in RESERVED_RANGES:
        assert any(
            start <= reserved.start and reserved.end <= end for start, end in private_use
        ), reserved.name


@pytest.mark.parametrize(
    "reserved",
    [PREPROCESS_SENTINELS, GLUED_CODES, NUMERAL_TOKENS, WINDOWS_PATHS, URLS],
    ids=lambda item: item.name,
)
def test_reserved_pattern_matches_range_boundaries(reserved: PlaceholderRange) -> None:
    for codepoint in (reserved.start, reserved.end):
        assert RESERVED_PATTERN.fullmatch(chr(codepoint)) is not None


def test_allocator_hands_out_distinct_placeholders() -> None:
    allocator = PlaceholderAllocator(NUMERAL_TOKENS)

    placeholders = [allocator.allocate(f"токен-{index}") for index in range(100)]

    assert len(set(placeholders)) == 100
    assert all(placeholder in NUMERAL_TOKENS for placeholder in placeholders)


def test_allocator_restores_every_fragment_in_one_pass() -> None:
    allocator = PlaceholderAllocator(NUMERAL_TOKENS)
    originals = ["ГОСТ12-й", "A4-го", "12,5-й"]

    placeholders = [allocator.allocate(original) for original in originals]
    text = " и ".join(str(placeholder) for placeholder in placeholders)

    assert allocator.restore(text) == " и ".join(originals)


def test_allocator_skips_codepoints_already_present_in_the_text() -> None:
    """Символ из диапазона во входе законен, но заменителем стать не должен."""
    occupied = chr(NUMERAL_TOKENS.start)
    allocator = PlaceholderAllocator(NUMERAL_TOKENS, f"маркер {occupied} в тексте")

    placeholder = allocator.allocate("ГОСТ12-й")

    assert placeholder != occupied
    # Собственный символ входа остаётся собой, а не превращается во фрагмент.
    assert allocator.restore(f"{occupied} {placeholder}") == f"{occupied} ГОСТ12-й"


def test_allocator_reports_exhaustion_instead_of_leaving_the_range() -> None:
    """Исчерпание — не ошибка: фрагмент остаётся как есть, но чужой диапазон цел."""
    tiny = PlaceholderRange("tiny", NUMERAL_TOKENS.start, NUMERAL_TOKENS.start + 1)
    allocator = PlaceholderAllocator(tiny)

    assert allocator.allocate("первый") == chr(tiny.start)
    assert allocator.allocate("второй") == chr(tiny.end)
    assert allocator.allocate("третий") is None
    assert allocator.exhausted


def test_allocator_keeps_an_unknown_placeholder_instead_of_dropping_text() -> None:
    allocator = PlaceholderAllocator(NUMERAL_TOKENS)
    placeholder = allocator.allocate("ГОСТ12-й")
    stray = chr(NUMERAL_TOKENS.end)

    assert allocator.restore(f"{placeholder}{stray}") == f"ГОСТ12-й{stray}"


def test_reserved_characters_in_finds_only_reserved_codepoints() -> None:
    text = f"обычный текст {chr(NUMERAL_TOKENS.start)}{chr(URLS.start)} и ещё"

    assert reserved_characters_in(text) == {chr(NUMERAL_TOKENS.start), chr(URLS.start)}
    assert reserved_characters_in("обычный текст без private use") == set()


def test_more_than_four_thousand_tokens_do_not_reach_the_windows_path_range() -> None:
    """Регрессия: заменитель №4096 попадал в диапазон путей Windows.

    Старая арифметика выдавала `chr(0xF0000 + i)`, а пути держали
    `(0xF1000, 0xF1FFD)`, поэтому на большом документе восстановление
    подставляло путь на месте числа.
    """
    allocator = PlaceholderAllocator(NUMERAL_TOKENS)
    count = 5000

    placeholders = [allocator.allocate(f"ГОСТ{index}-й") for index in range(count)]

    assert all(placeholder is not None for placeholder in placeholders)
    assert all(placeholder not in WINDOWS_PATHS for placeholder in placeholders)
    assert all(placeholder not in URLS for placeholder in placeholders)
    assert all(placeholder not in GLUED_CODES for placeholder in placeholders)


def test_many_structured_tokens_survive_a_full_normalization() -> None:
    """Тот же дефект end-to-end: числовых токенов больше, чем вместимость 0xF1000."""
    count = 4500
    sentences = [f"Пункт ГОСТ{index}-й описан отдельно." for index in range(count)]
    source = " ".join(sentences)

    result = normalize(source, NormalizeOptions.tts())

    # Ни один служебный символ не дошёл до выхода.
    assert RESERVED_PATTERN.search(result) is None
    assert STRUCTURED_NUMERIC_SUFFIX_PATTERN.search(source) is not None


def test_urls_and_paths_are_restored_independently_of_their_order() -> None:
    """Раньше все URL прятались за один символ и восстанавливались по порядку."""
    source = (
        "Смотри https://example.org/first и https://example.org/second, "
        "файлы C:\\Users\\test\\a.txt и C:\\Users\\test\\b.txt."
    )

    protected_urls = protect_urls(source)
    protected_paths = protect_windows_paths(protected_urls.text)

    restored = protected_urls.restore(protected_paths.restore(protected_paths.text))
    assert restored == source


def test_url_and_path_placeholders_come_from_different_ranges() -> None:
    source = "Ссылка https://example.org/a и путь C:\\Users\\test\\a.txt."

    protected_urls = protect_urls(source)
    protected_paths = protect_windows_paths(protected_urls.text)

    url_chars = {char for char in protected_urls.text if char in URLS}
    path_chars = {char for char in protected_paths.text if char in WINDOWS_PATHS}
    assert url_chars and path_chars
    assert not (url_chars & path_chars)


def test_no_reserved_character_leaks_into_the_output_on_a_corpus_sample() -> None:
    """Служебный символ в выводе — это не восстановленный фрагмент.

    Побайтовое равенство вывода до и после переезда на реестр проверено A/B-
    прогоном на книге (см. `docs/SPEED_OBSERVATIONS.md`): хеш совпал. Держать
    эталонный хеш в тесте нельзя — он меняется при любой правке правил
    нормализации и давал бы ложные падения.
    """
    corpus = Path("benchmarks/corpus/03_karamzin_history_of_russian_state.txt")
    if not corpus.exists():
        pytest.skip(f"нет корпуса для сравнения вывода: {corpus}")
    sample = corpus.read_text(encoding="utf-8")[:60_000]

    result = normalize(sample, NormalizeOptions.tts())

    # Служебные символы не должны попадать в вывод ни при каких входах.
    assert RESERVED_PATTERN.search(result) is None
    # И вывод не должен быть пустым или обрезанным до неузнаваемости.
    assert len(result) > len(sample) // 2


def test_preprocess_sentinels_keep_their_historic_codepoints() -> None:
    """Метки препроцессинга переехали в реестр — кодовые точки должны совпасть."""
    from ru_normalizr import preprocess_utils as pu

    assert ord(pu.LETTER_HYPHEN_PLACEHOLDER) == 0xE000
    assert ord(pu.NEGATIVE_NUMBER_PLACEHOLDER) == 0xE001
    assert ord(pu.UNIT_SLASH_PLACEHOLDER) == 0xE003
    assert ord(pu.BINARY_PLUS_PLACEHOLDER) == 0xE004
    assert ord(pu.BINARY_MINUS_PLACEHOLDER) == 0xE005
    assert ord(pu.BINARY_POWER_PLACEHOLDER) == 0xE006
    assert all(
        char in PREPROCESS_SENTINELS
        for char in (
            pu.LETTER_HYPHEN_PLACEHOLDER,
            pu.NEGATIVE_NUMBER_PLACEHOLDER,
            pu.UNIT_SLASH_PLACEHOLDER,
        )
    )


def test_private_use_input_survives_normalization() -> None:
    """Символ private use во входе не должен исчезать и не должен ломать разбор."""
    marker = chr(URLS.start)
    source = f"Маркер {marker} и ссылка https://example.org/a."

    result = normalize(source, NormalizeOptions.tts())

    assert marker in result


def test_allocator_pattern_covers_exactly_its_own_range() -> None:
    """Аллокатор не должен восстанавливать чужие заменители."""
    allocator = PlaceholderAllocator(URLS)
    placeholder = allocator.allocate("https://example.org/a")
    foreign = chr(NUMERAL_TOKENS.start)

    assert allocator.restore(f"{placeholder} {foreign}") == f"https://example.org/a {foreign}"
    assert re.fullmatch(r".", str(placeholder)) is not None
