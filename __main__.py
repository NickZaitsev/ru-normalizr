from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .options import NormalizeOptions
from .pipeline import normalize


def _read_input(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if args.text:
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Provide text, --file, or stdin.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ru-normalizr", description="Normalize Russian text."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Print the installed ru-normalizr version and exit.",
    )
    parser.add_argument("text", nargs="?", help="Inline text to normalize.")
    parser.add_argument("--file", help="Read text from file.")
    parser.add_argument(
        "--output", help="Write normalized text to file instead of stdout."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Print the normalized result to stdout and exit with status 1 if it "
            "differs from the input, 0 if unchanged. Cannot be combined with --output."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["safe", "tts"],
        default="safe",
        help="Preset normalization mode.",
    )
    parser.add_argument(
        "--latinization-backend",
        choices=["ipa", "dictionary"],
        help="Backend for Latin transliteration.",
    )
    parser.add_argument(
        "--no-latinization", action="store_true", help="Disable Latin transliteration."
    )
    parser.add_argument(
        "--no-first-word-decap", action="store_true", help="Disable first-word decap."
    )
    parser.add_argument(
        "--keep-links", action="store_true", help="Keep bracketed numeric links."
    )
    parser.add_argument(
        "--with-latin-stress",
        action="store_true",
        help="Keep '+' stress markers when using IPA latinization.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.check and args.output:
        parser.error("--check cannot be combined with --output")
    text = _read_input(args)
    options = NormalizeOptions(
        mode=args.mode,
        enable_first_word_decap=False if args.no_first_word_decap else None,
        remove_links=False if args.keep_links else None,
        enable_latinization=False if args.no_latinization else None,
        latinization_backend=args.latinization_backend,
        enable_latinization_stress_marks=args.with_latin_stress,
    )
    result = normalize(text, options)
    if args.output:
        output_path = Path(args.output)
        output_text = result if result.endswith("\n") else result + "\n"
        output_path.write_text(output_text, encoding="utf-8")
    else:
        sys.stdout.write(result)
        if not result.endswith("\n"):
            sys.stdout.write("\n")
    if args.check:
        return 1 if result != text else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
