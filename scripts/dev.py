from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLEAN_PATHS = (
    ROOT / "build",
    ROOT / "dist",
    ROOT / ".tmp_dist",
    ROOT / ".pytest_cache",
    ROOT / ".ruff_cache",
    ROOT / "__pycache__",
    ROOT / "ru_normalizr.egg-info",
)


def run(*args: str) -> int:
    completed = subprocess.run(args, cwd=ROOT)
    return completed.returncode


def clean() -> int:
    for path in CLEAN_PATHS:
        if path.exists():
            shutil.rmtree(path)
    for path in ROOT.rglob("__pycache__"):
        shutil.rmtree(path)
    return 0


def lint() -> int:
    return run(sys.executable, "-m", "ruff", "check", ".")


def test() -> int:
    return run(sys.executable, "-m", "pytest", "-q")


def build() -> int:
    clean()
    return run(sys.executable, "-m", "build", ".")


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if len(args) != 1 or args[0] not in {"clean", "lint", "test", "build"}:
        sys.stderr.write("Usage: python dev.py [clean|lint|test|build]\n")
        return 2

    command = args[0]
    if command == "clean":
        return clean()
    if command == "lint":
        return lint()
    if command == "test":
        return test()
    return build()


if __name__ == "__main__":
    raise SystemExit(main())
