from __future__ import annotations

import subprocess
import sys
from unittest import TestCase, mock

from scripts import dev


class CommandDispatchTests(TestCase):
    def test_empty_argv_is_a_usage_error_instead_of_reading_sys_argv(self):
        # `main([])` used to fall through to sys.argv, so a caller passing no
        # arguments silently ran whatever the surrounding process was invoked
        # with — including `publish`.
        with (
            mock.patch.object(sys, "argv", ["dev.py", "publish"]),
            self.assertRaises(SystemExit) as raised,
        ):
            dev.main([])

        self.assertEqual(raised.exception.code, 2)

    def test_release_check_runs_the_type_checker(self):
        # CI and AGENTS.md both require pyright, so the release gate must not be
        # weaker than the commit gate.
        calls: list[str] = []

        def record(name):
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
            self.assertEqual(dev.check(), 0)

        self.assertIn("typecheck", calls)
        self.assertLess(calls.index("typecheck"), calls.index("test"))


class CaptureTests(TestCase):
    def test_capture_decodes_output_as_utf8_independently_of_system_locale(self) -> None:
        expected = "ветка/путь-日本語"
        command = (
            "import sys; "
            f"sys.stdout.buffer.write({expected.encode('utf-8')!r})"
        )

        with mock.patch.object(subprocess, "_text_encoding", return_value="ascii"):
            completed = dev.capture(sys.executable, "-c", command)

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, expected)

    def test_capture_decodes_utf8_stderr_and_preserves_nonzero_exit_code(self) -> None:
        expected = "ошибка для 日本語"
        command = (
            "import sys; "
            f"sys.stderr.buffer.write({expected.encode('utf-8')!r}); "
            "raise SystemExit(7)"
        )

        with mock.patch.object(subprocess, "_text_encoding", return_value="ascii"):
            completed = dev.capture(sys.executable, "-c", command)

        self.assertEqual(completed.returncode, 7)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.stderr, expected)

    def test_capture_replaces_malformed_external_output(self) -> None:
        command = "import sys; sys.stdout.buffer.write(b'path-\\xff')"

        completed = dev.capture(sys.executable, "-c", command)

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "path-\N{REPLACEMENT CHARACTER}")


class ProjectMetadataTests(TestCase):
    def test_project_version_matches_package_version(self) -> None:
        # Importing scripts.dev and reading TOML exercises the tomli fallback
        # in the Python 3.10 CI cell and stdlib tomllib on Python 3.11+.
        self.assertEqual(dev.project_version(), dev.package_version())
