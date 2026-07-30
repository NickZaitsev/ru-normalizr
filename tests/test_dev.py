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
