import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ru_normalizr import __version__
from ru_normalizr.__main__ import _use_utf8_stdio, main


class _TerminalInput(io.StringIO):
    def isatty(self) -> bool:
        return True


class _ReconfigurableStream(io.StringIO):
    def __init__(self, *, error: Exception | None = None):
        super().__init__()
        self.error = error
        self.encodings: list[str] = []

    def reconfigure(self, *, encoding: str) -> None:
        self.encodings.append(encoding)
        if self.error is not None:
            raise self.error


class RuNormalizrCliTests(unittest.TestCase):
    def test_inline_text_is_normalized_to_stdout(self):
        stdout = io.StringIO()
        with (
            patch("ru_normalizr.__main__.sys.stdout", stdout),
            patch("ru_normalizr.__main__.normalize", return_value="готово") as normalize,
        ):
            code = main(["исходный текст"])

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "готово\n")
        self.assertEqual(normalize.call_args.args[0], "исходный текст")

    def test_result_with_newline_is_not_given_an_extra_newline(self):
        stdout = io.StringIO()
        with (
            patch("ru_normalizr.__main__.sys.stdout", stdout),
            patch("ru_normalizr.__main__.normalize", return_value="готово\n"),
        ):
            code = main(["текст"])

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "готово\n")

    def test_file_input_and_output_are_utf8_with_trailing_newline(self):
        with TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "вход.txt"
            output_path = Path(tmp_dir) / "выход.txt"
            input_path.write_text("Ёжик 2", encoding="utf-8")

            with patch(
                "ru_normalizr.__main__.normalize", return_value="ёжик два"
            ) as normalize:
                code = main(
                    [
                        "--file",
                        str(input_path),
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(normalize.call_args.args[0], "Ёжик 2")
            self.assertEqual(output_path.read_text(encoding="utf-8"), "ёжик два\n")

    def test_check_exit_codes_reflect_whether_text_changed(self):
        cases = (
            ("без изменений", "без изменений", 0),
            ("текст 2", "текст два", 1),
        )
        for source, result, expected_code in cases:
            with (
                self.subTest(source=source),
                patch("ru_normalizr.__main__.sys.stdout", io.StringIO()),
                patch("ru_normalizr.__main__.normalize", return_value=result),
            ):
                self.assertEqual(main(["--check", source]), expected_code)

    def test_check_cannot_be_combined_with_output(self):
        with (
            patch("ru_normalizr.__main__.sys.stderr", io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            main(["--check", "--output", "out.txt", "текст"])

        self.assertEqual(raised.exception.code, 2)

    def test_version_flag_prints_installed_version(self):
        stdout = io.StringIO()
        with (
            patch("ru_normalizr.__main__.sys.stdout", stdout),
            self.assertRaises(SystemExit) as raised,
        ):
            main(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(stdout.getvalue(), f"ru-normalizr {__version__}\n")

    def test_stdin_is_used_when_no_text_or_file_is_given(self):
        stdin = io.StringIO("текст из stdin")
        stdout = io.StringIO()
        with (
            patch("ru_normalizr.__main__.sys.stdin", stdin),
            patch("ru_normalizr.__main__.sys.stdout", stdout),
            patch("ru_normalizr.__main__.normalize", return_value="результат") as normalize,
        ):
            code = main([])

        self.assertEqual(code, 0)
        self.assertEqual(normalize.call_args.args[0], "текст из stdin")

    def test_missing_input_on_terminal_is_an_error(self):
        with (
            patch("ru_normalizr.__main__.sys.stdin", _TerminalInput()),
            patch("ru_normalizr.__main__.sys.stdout", io.StringIO()),
            self.assertRaisesRegex(SystemExit, "Provide text, --file, or stdin"),
        ):
            main([])

    def test_cli_flags_map_to_normalize_options(self):
        cases = (
            (["--mode", "tts"], "mode", "tts"),
            (
                ["--mode", "tts", "--no-latinization"],
                "enable_latinization",
                False,
            ),
            (
                ["--mode", "tts", "--no-first-word-decap"],
                "enable_first_word_decap",
                False,
            ),
            (["--mode", "tts", "--keep-links"], "remove_links", False),
            (
                ["--latinization-backend", "dictionary"],
                "latinization_backend",
                "dictionary",
            ),
            (
                ["--with-latin-stress"],
                "enable_latinization_stress_marks",
                True,
            ),
        )
        for flags, attribute, expected in cases:
            with self.subTest(flags=flags):
                captured_options = []

                def capture_options(
                    text, options, captured_options=captured_options
                ):
                    captured_options.append(options)
                    return text

                with (
                    patch("ru_normalizr.__main__.sys.stdout", io.StringIO()),
                    patch(
                        "ru_normalizr.__main__.normalize",
                        side_effect=capture_options,
                    ),
                ):
                    self.assertEqual(main([*flags, "текст"]), 0)

                self.assertEqual(getattr(captured_options[0], attribute), expected)

    def test_utf8_stdio_reconfigure_is_best_effort(self):
        stdin = _ReconfigurableStream()
        stdout = _ReconfigurableStream(error=OSError("stream is closed"))

        with (
            patch("ru_normalizr.__main__.sys.stdin", stdin),
            patch("ru_normalizr.__main__.sys.stdout", stdout),
        ):
            _use_utf8_stdio()

        self.assertEqual(stdin.encodings, ["utf-8"])
        self.assertEqual(stdout.encodings, ["utf-8"])


if __name__ == "__main__":
    unittest.main()
