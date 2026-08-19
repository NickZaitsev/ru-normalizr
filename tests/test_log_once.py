"""Тесты дедупликации предупреждений о сбоях рендеринга числительных."""

from __future__ import annotations

import logging
import threading

import pytest

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr._log_once import (
    _MAX_REMEMBERED,
    reset_warn_once_cache,
    warn_once,
)


@pytest.fixture(autouse=True)
def _clean_cache() -> None:
    reset_warn_once_cache()


def test_repeated_key_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("ru_normalizr.test_log_once")

    with caplog.at_level(logging.WARNING, logger=logger.name):
        for _ in range(5):
            warn_once(logger, "num2words:17", "num2words failed for %r", 17)

    assert [record.getMessage() for record in caplog.records] == ["num2words failed for 17"]


def test_different_keys_each_warn(caplog: pytest.LogCaptureFixture) -> None:
    """Один токен может сорваться по двум причинам — вторую нельзя терять."""
    logger = logging.getLogger("ru_normalizr.test_log_once")

    with caplog.at_level(logging.WARNING, logger=logger.name):
        warn_once(logger, "num2words:17", "num2words failed for %r", 17)
        warn_once(logger, "inflect:17", "inflect failed for %r", 17)

    assert len(caplog.records) == 2


def test_cache_is_bounded(caplog: pytest.LogCaptureFixture) -> None:
    """Набор запомненных токенов не растёт линейно от их количества."""
    logger = logging.getLogger("ru_normalizr.test_log_once")

    with caplog.at_level(logging.WARNING, logger=logger.name):
        for index in range(_MAX_REMEMBERED + 1):
            warn_once(logger, f"num2words:{index}", "failed for %d", index)
        # Набор сбросился на переполнении, поэтому самый первый токен
        # предупреждает о себе снова — но лог всё равно ограничен.
        warn_once(logger, "num2words:0", "failed for %d", 0)

    assert len(caplog.records) == _MAX_REMEMBERED + 2

    from ru_normalizr._log_once import _warned

    assert len(_warned) <= _MAX_REMEMBERED


def test_reset_lets_the_same_key_warn_again(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("ru_normalizr.test_log_once")

    with caplog.at_level(logging.WARNING, logger=logger.name):
        warn_once(logger, "num2words:17", "failed")
        reset_warn_once_cache()
        warn_once(logger, "num2words:17", "failed")

    assert len(caplog.records) == 2


def test_concurrent_callers_emit_one_warning_per_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("ru_normalizr.test_log_once")
    barrier = threading.Barrier(8)

    def hammer() -> None:
        barrier.wait()
        warn_once(logger, "num2words:17", "failed")

    with caplog.at_level(logging.WARNING, logger=logger.name):
        threads = [threading.Thread(target=hammer) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    assert len(caplog.records) == 1


def test_num2words_failure_is_visible_at_warning_level(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Сбой зависимости больше не тонет в DEBUG: токен не переписан — есть WARNING."""
    import num2words

    from ru_normalizr.numerals import _helpers

    def always_fails(*args: object, **kwargs: object) -> str:
        raise RuntimeError("num2words is broken")

    monkeypatch.setattr(num2words, "num2words", always_fails)
    monkeypatch.setattr(_helpers.num2words, "num2words", always_fails, raising=False)

    # Рендеринг числительных запоминается на весь процесс. Если «17» уже отрендерил
    # какой-то тест раньше, `num2words` для него больше не вызовут и сбоя не будет —
    # тест зависел бы от порядка. Сбросить нужно и после: иначе в кэше останется
    # результат сорванного рендеринга и «17» перестанет читаться у соседних тестов.
    _helpers._inflect_numeral_string_cached.cache_clear()
    try:
        with caplog.at_level(logging.WARNING, logger="ru_normalizr"):
            # Одно и то же число трижды: каждое место сбоя предупреждает один раз,
            # а не по разу на каждое вхождение.
            normalize("Прошло 17 лет, потом ещё 17 лет и снова 17 лет.", NormalizeOptions.tts())
    finally:
        _helpers._inflect_numeral_string_cached.cache_clear()

    messages = [
        record.getMessage()
        for record in caplog.records
        if "num2words failed" in record.getMessage()
    ]
    assert messages, "сбой num2words не виден на уровне WARNING"
    assert len(messages) == len(set(messages)), messages
