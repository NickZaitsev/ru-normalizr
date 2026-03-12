from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
    parser.add_argument("text", nargs="?", help="Inline text to normalize.")
    parser.add_argument("--file", help="Read text from file.")
    parser.add_argument(
        "--output", help="Write normalized text to file instead of stdout."
    )
    parser.add_argument(
        "--check", action="store_true", help="Normalize input and print the result."
    )
    parser.add_argument(
        "--latinization-backend",
        choices=["ipa", "dictionary"],
        default="ipa",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    text = _read_input(args)
    options = NormalizeOptions(
        enable_first_word_decap=not args.no_first_word_decap,
        remove_links=not args.keep_links,
        enable_latinization=not args.no_latinization,
        latinization_backend=args.latinization_backend,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
