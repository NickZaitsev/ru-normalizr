from __future__ import annotations

import concurrent.futures

import num2words
import pytest

from ru_normalizr import normalize
from ru_normalizr._morph import (
    _parse_word_lower,
    canonicalize_case,
    canonicalize_grammemes,
    parse_word,
    select_parse,
)


@pytest.mark.parametrize(
    ("rare", "primary"),
    [
        ("gen1", "gent"),
        ("gen2", "gent"),
        ("acc1", "accs"),
        ("acc2", "accs"),
        ("loc1", "loct"),
        ("loc2", "loct"),
        ("voct", "nomn"),
    ],
)
def test_all_upstream_rare_cases_are_canonicalized(rare: str, primary: str) -> None:
    assert canonicalize_case(rare) == primary
    assert canonicalize_grammemes({rare, "plur"}) == frozenset({primary, "plur"})


def test_parse_cache_uses_lowercase_key_without_folding_yo() -> None:
    _parse_word_lower.cache_clear()
    assert parse_word("Фёдор") == parse_word("фёдор")
    assert _parse_word_lower.cache_info().currsize == 1
    assert parse_word("Федор") != parse_word("Фёдор")
    assert _parse_word_lower.cache_info().currsize == 2


def test_selector_prefers_domain_compatible_lira_parse() -> None:
    selected = select_parse(
        "лира",
        pos="NOUN",
        normal_forms={"лира"},
        gender="femn",
        required_grammemes={"inan"},
        forbidden_grammemes={"Name", "Surn", "Geox"},
    )
    assert selected is not None
    assert selected.normal_form == "лира"
    assert selected.tag.gender == "femn"
    assert "inan" in selected.tag


def test_selector_respects_score_order_only_after_preferences() -> None:
    selected = select_parse(
        "часовой",
        pos={"ADJF", "NOUN"},
        preferred_grammemes={"ADJF"},
    )
    assert selected is not None
    assert selected.tag.POS == "ADJF"


def test_selector_returns_none_for_shape_barrier() -> None:
    assert select_parse("hello", pos="NOUN") is None


def test_shared_analyzer_is_safe_under_concurrent_parse_and_normalize() -> None:
    inputs = ["Фёдор", "лира", "сутки", "достигаем"] * 8

    def exercise(word: str) -> tuple[int, str]:
        return len(parse_word(word)), normalize(f"В сообщении есть 2 слова: {word}.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(exercise, inputs))
    assert all(parse_count > 0 and normalized for parse_count, normalized in results)


def test_generated_ordinal_final_words_keep_adjective_first_parse_invariant() -> None:
    for value in range(1, 10_000):
        final_word = num2words.num2words(value, lang="ru", to="ordinal").split()[-1]
        first = parse_word(final_word)[0]
        assert first.tag.POS == "ADJF" or "Anum" in first.tag, (value, final_word, first.tag)
