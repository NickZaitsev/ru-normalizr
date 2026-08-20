from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from scripts import dev

# --- Диспетчер команд -------------------------------------------------------


def test_empty_argv_is_a_usage_error_instead_of_reading_sys_argv() -> None:
    # `main([])` used to fall through to sys.argv, so a caller passing no
    # arguments silently ran whatever the surrounding process was invoked
    # with — including `publish`.
    with (
        mock.patch.object(sys, "argv", ["dev.py", "publish"]),
        pytest.raises(SystemExit) as raised,
    ):
        dev.main([])

    assert raised.value.code == 2


def test_release_check_runs_the_type_checker() -> None:
    # CI and AGENTS.md both require pyright, so the release gate must not be
    # weaker than the commit gate.
    calls: list[str] = []

    def record(name: str):
        def step() -> int:
            calls.append(name)
            return 0

        return step

    with (
        mock.patch.object(dev, "clean", record("clean")),
        mock.patch.object(dev, "check_versions", record("version")),
        mock.patch.object(dev, "lint", record("lint")),
        mock.patch.object(dev, "typecheck", record("typecheck")),
        mock.patch.object(dev, "test", record("test")),
        mock.patch.object(dev, "run", return_value=0),
        mock.patch.object(dev, "twine_check", record("twine-check")),
    ):
        assert dev.check() == 0

    assert "typecheck" in calls
    assert calls.index("typecheck") < calls.index("test")


# --- Декодирование вывода внешних процессов ---------------------------------


def test_capture_decodes_output_as_utf8_independently_of_system_locale() -> None:
    expected = "ветка/путь-日本語"
    command = f"import sys; sys.stdout.buffer.write({expected.encode('utf-8')!r})"

    with mock.patch.object(subprocess, "_text_encoding", return_value="ascii", create=True):
        completed = dev.capture(sys.executable, "-c", command)

    assert completed.returncode == 0
    assert completed.stdout == expected


def test_capture_decodes_utf8_stderr_and_preserves_nonzero_exit_code() -> None:
    expected = "ошибка для 日本語"
    command = (
        "import sys; "
        f"sys.stderr.buffer.write({expected.encode('utf-8')!r}); "
        "raise SystemExit(7)"
    )

    with mock.patch.object(subprocess, "_text_encoding", return_value="ascii", create=True):
        completed = dev.capture(sys.executable, "-c", command)

    assert completed.returncode == 7
    assert completed.stdout == ""
    assert completed.stderr == expected


def test_capture_replaces_malformed_external_output() -> None:
    command = "import sys; sys.stdout.buffer.write(b'path-\\xff')"

    completed = dev.capture(sys.executable, "-c", command)

    assert completed.returncode == 0
    assert completed.stdout == "path-\N{REPLACEMENT CHARACTER}"


# --- Синхронность версий ----------------------------------------------------


def test_project_version_matches_package_version() -> None:
    # Importing scripts.dev and reading TOML exercises the tomli fallback
    # in the Python 3.10 CI cell and stdlib tomllib on Python 3.11+.
    assert dev.project_version() == dev.package_version()


def test_changelog_documents_the_current_version() -> None:
    """VERSIONING.md требует держать в синхроне три файла, а не два."""
    assert dev.changelog_has_version(dev.project_version())


def test_changelog_has_version_rejects_an_undocumented_version() -> None:
    assert not dev.changelog_has_version("9.9.9")


def test_changelog_has_version_ignores_the_unreleased_section() -> None:
    """«## Unreleased» не должен считаться записью о выпуске."""
    assert not dev.changelog_has_version("Unreleased")


def test_check_versions_fails_when_changelog_lacks_the_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Релизный гейт check-release-tag опирается на check_versions."""
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## Unreleased\n\n## [0.2.0] - 2026-01-01\n", encoding="utf-8"
    )
    monkeypatch.setattr(dev, "ROOT", tmp_path)
    monkeypatch.setattr(dev, "project_version", lambda: "0.3.0")
    monkeypatch.setattr(dev, "package_version", lambda: "0.3.0")

    assert dev.check_versions() == 1
    assert "CHANGELOG.md has no section for version 0.3.0" in capsys.readouterr().err


def test_check_versions_passes_when_all_three_files_agree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## Unreleased\n\n## [0.3.0] - 2026-01-01\n", encoding="utf-8"
    )
    monkeypatch.setattr(dev, "ROOT", tmp_path)
    monkeypatch.setattr(dev, "project_version", lambda: "0.3.0")
    monkeypatch.setattr(dev, "package_version", lambda: "0.3.0")

    assert dev.check_versions() == 0


def test_changelog_is_read_as_utf8_regardless_of_locale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ячейка Windows в CI — cp1252, поэтому кодировку нельзя брать из локали."""
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.3.0] - 2026-01-01\n\n- Кириллический текст и 日本語\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dev, "ROOT", tmp_path)

    assert dev.changelog_has_version("0.3.0")
