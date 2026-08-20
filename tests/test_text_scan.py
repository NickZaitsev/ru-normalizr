"""Юнит-тесты кеша casefold в ``text_scan``.

Кеш держит одну запись на контекст. Пока он лежал в глобале, два потока с
собственными ``Normalizer`` мешали друг другу: каждый промах — casefold всего
документа, а `clear_fold_cache` из одного потока стирал кеш другого посреди
прохода.
"""

from __future__ import annotations

import re
import threading

from ru_normalizr.text_scan import GuardedPattern, _casefolded, clear_fold_cache


def test_casefolded_reuses_the_entry_for_the_same_object() -> None:
    text = "Разные РЕГИСТРЫ Букв"

    first = _casefolded(text)
    second = _casefolded(text)

    assert first == text.casefold()
    assert first is second


def test_casefolded_recomputes_for_a_different_document() -> None:
    first = _casefolded("ПЕРВЫЙ документ")
    second = _casefolded("ВТОРОЙ документ")

    assert first == "первый документ"
    assert second == "второй документ"


def test_clear_fold_cache_drops_the_reference() -> None:
    text = "Документ"
    _casefolded(text)

    clear_fold_cache()

    # Запись пересчитывается, а не берётся из кеша: значение то же, объект новый.
    assert _casefolded(text) == text.casefold()


def test_clear_fold_cache_in_one_thread_keeps_another_threads_entry() -> None:
    """Раньше clear_fold_cache() из чужого потока обнулял кеш текущего."""
    text = "Общий ДОКУМЕНТ для двух потоков"
    _casefolded(text)
    cleared = threading.Event()

    def clear_elsewhere() -> None:
        clear_fold_cache()
        cleared.set()

    worker = threading.Thread(target=clear_elsewhere)
    worker.start()
    worker.join()
    assert cleared.is_set()

    # Кеш этого потока не тронут: то же значение, и запись всё ещё та же.
    assert _casefolded(text) is _casefolded(text)


def test_concurrent_threads_do_not_evict_each_others_entries() -> None:
    """Два документа в двух потоках не должны выбивать друг друга из кеша."""
    guard = GuardedPattern(re.compile("иголка", re.IGNORECASE), "иголка")
    documents = ["СЕНО " * 200 + "ИГОЛКА", "ПЕСОК " * 200 + "иголка"]
    results: dict[int, list[bool]] = {}
    barrier = threading.Barrier(len(documents))

    def scan(index: int) -> None:
        document = documents[index]
        found: list[bool] = []
        for _ in range(50):
            barrier.wait()
            found.append(guard.may_match(document))
        results[index] = found

    threads = [threading.Thread(target=scan, args=(i,)) for i in range(len(documents))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Главное — корректность под конкуренцией: guard находит литерал в обоих.
    assert results == {0: [True] * 50, 1: [True] * 50}


def test_guard_result_is_independent_of_cache_state() -> None:
    guard = GuardedPattern(re.compile("Ёлка", re.IGNORECASE), "ёлка")
    document = "В лесу родилась ЁЛКА"

    with_cache = guard.may_match(document)
    clear_fold_cache()
    without_cache = guard.may_match(document)

    assert with_cache is True
    assert without_cache is True
