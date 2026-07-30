from __future__ import annotations

import subprocess
import sys
from unittest import TestCase, mock

from scripts import dev


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
