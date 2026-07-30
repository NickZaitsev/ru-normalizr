from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
CLEAN_PATHS = (
    ROOT / "build",
    ROOT / "dist",
    ROOT / ".tmp_dist",
    ROOT / ".pytest_cache",
    ROOT / ".ruff_cache",
    ROOT / "__pycache__",
    ROOT / "ru_normalizr.egg-info",
    ROOT / "src" / "ru_normalizr.egg-info",
)
CLEAN_GLOBS = (
    "**/__pycache__",
    "src/ru_normalizr/dictionaries/**/dictionaries_*.pkl",
)
PUBLISH_IGNORED_PREFIXES = (
    "build/",
    "dist/",
    ".tmp_dist/",
    ".pytest_cache/",
    ".ruff_cache/",
    "ru_normalizr.egg-info/",
    "src/ru_normalizr.egg-info/",
)


def run(*args: str) -> int:
    print(f"> {' '.join(args)}")
    completed = subprocess.run(args, cwd=ROOT)
    return completed.returncode


def capture(*args: str) -> subprocess.CompletedProcess[str]:
    print(f"> {' '.join(args)}")
    return subprocess.run(
        args,
        cwd=ROOT,
        encoding="utf-8",
        capture_output=True,
    )


def clean() -> int:
    for path in CLEAN_PATHS:
        if path.exists():
            shutil.rmtree(path)
    for pattern in CLEAN_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
    return 0


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def package_version() -> str:
    init_text = (ROOT / "src" / "ru_normalizr" / "__init__.py").read_text(
        encoding="utf-8"
    )
    match = re.search(r'^__version__ = "([^"]+)"$', init_text, re.MULTILINE)
    if not match:
        raise RuntimeError("Could not find __version__ in __init__.py")
    return match.group(1)


def check_versions() -> int:
    pyproject_version = project_version()
    init_version = package_version()
    if pyproject_version != init_version:
        sys.stderr.write(
            "Version mismatch:\n"
            f"  pyproject.toml: {pyproject_version}\n"
            f"  __init__.py:    {init_version}\n"
        )
        return 1
    print(f"Version OK: {pyproject_version}")
    return 0


def release_tag_name() -> str | None:
    """Return the git tag name for the current GitHub Actions release run."""
    ref_name = os.environ.get("GITHUB_REF_NAME", "").strip()
    ref = os.environ.get("GITHUB_REF", "").strip()
    if ref_name:
        return ref_name
    if ref.startswith("refs/tags/"):
        return ref.removeprefix("refs/tags/")
    return None


def check_release_tag() -> int:
    """Fail if the push tag (without leading v) does not match package version."""
    code = check_versions()
    if code:
        return code

    tag_name = release_tag_name()
    if not tag_name:
        sys.stderr.write(
            "Release tag check requires GITHUB_REF_NAME or GITHUB_REF "
            "(refs/tags/...) from a tag push.\n"
        )
        return 1

    expected = project_version()
    tag_version = tag_name[1:] if tag_name.startswith("v") else tag_name
    if tag_version != expected:
        sys.stderr.write(
            "Release tag does not match package version:\n"
            f"  git tag:          {tag_name}\n"
            f"  package version:  {expected}\n"
            f"  expected tag:     v{expected}\n"
        )
        return 1

    print(f"Release tag OK: {tag_name} == v{expected}")
    return 0


def lint() -> int:
    return run(sys.executable, "-m", "ruff", "check", ".")


def test() -> int:
    return run(sys.executable, "-m", "pytest", "-q")


def build() -> int:
    clean()
    return run(sys.executable, "-m", "build", ".")


def dist_artifacts() -> list[Path]:
    dist_dir = ROOT / "dist"
    if not dist_dir.exists():
        return []
    return sorted(
        path
        for path in dist_dir.iterdir()
        if path.is_file() and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
    )


def twine_check() -> int:
    artifacts = dist_artifacts()
    if not artifacts:
        sys.stderr.write("No distribution artifacts found in dist/.\n")
        return 1
    return run(sys.executable, "-m", "twine", "check", *(str(path) for path in artifacts))


def current_branch() -> str:
    completed = capture("git", "branch", "--show-current")
    if completed.returncode:
        sys.stderr.write(completed.stderr)
        raise RuntimeError("Failed to read current git branch")
    return completed.stdout.strip()


def _normalize_git_path(path: str) -> str:
    return path.replace("\\", "/")


def _is_expected_generated_path(path: str) -> bool:
    normalized = _normalize_git_path(path)
    if normalized == "__pycache__" or "/__pycache__/" in f"/{normalized}/":
        return True
    return normalized.startswith(PUBLISH_IGNORED_PREFIXES)


def ensure_clean_worktree(tag_name: str) -> int:
    completed = capture("git", "status", "--porcelain")
    if completed.returncode:
        sys.stderr.write(completed.stderr)
        return 1
    dirty_lines: list[str] = []
    for line in completed.stdout.splitlines():
        path = line[3:]
        if _is_expected_generated_path(path):
            continue
        dirty_lines.append(line)
    if dirty_lines:
        sys.stderr.write(
            "Working tree is not clean. Commit or stash changes before publish.\n"
        )
        return 1

    local_tag = capture("git", "rev-parse", "-q", "--verify", f"refs/tags/{tag_name}")
    if local_tag.returncode == 0:
        sys.stderr.write(f"Tag already exists locally: {tag_name}\n")
        return 1

    remote_tag = capture("git", "ls-remote", "--tags", "origin", tag_name)
    if remote_tag.returncode:
        sys.stderr.write(remote_tag.stderr)
        return 1
    if remote_tag.stdout.strip():
        sys.stderr.write(f"Tag already exists on origin: {tag_name}\n")
        return 1
    return 0


def publish(
    *,
    remote: str,
    branch: str,
    skip_check: bool,
    skip_main_push: bool,
) -> int:
    version = project_version()
    tag_name = f"v{version}"

    if not skip_check:
        code = check()
        if code:
            return code
    else:
        code = check_versions()
        if code:
            return code

    branch_name = current_branch()
    if branch_name != branch:
        sys.stderr.write(
            f"Publish must run from branch '{branch}'. Current branch: '{branch_name}'.\n"
        )
        return 1

    code = ensure_clean_worktree(tag_name)
    if code:
        return code

    print(f"Preparing GitHub release for version {version} via tag {tag_name}")

    if not skip_main_push:
        code = run("git", "push", remote, branch)
        if code:
            return code

    code = run("git", "tag", tag_name)
    if code:
        return code
    return run("git", "push", remote, tag_name)


def check() -> int:
    steps: list[tuple[str, Callable[[], int]]] = [
        ("clean", clean),
        ("version", check_versions),
        ("lint", lint),
        ("test", test),
        ("build", lambda: run(sys.executable, "-m", "build", ".")),
        ("twine-check", twine_check),
    ]
    for name, step in steps:
        print(f"\n== {name} ==")
        code = step()
        if code:
            return code
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local developer and release helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("clean", "lint", "test", "build", "check", "check-release-tag"):
        subparsers.add_parser(command)

    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument(
        "--remote",
        default="origin",
        help="Git remote to push branch and tag to. Defaults to origin.",
    )
    publish_parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Create and push the release tag without rerunning local checks.",
    )
    publish_parser.add_argument(
        "--branch",
        default="main",
        help="Branch that must be current and will be pushed before tagging. Defaults to main.",
    )
    publish_parser.add_argument(
        "--skip-main-push",
        action="store_true",
        help="Create and push only the release tag without pushing the branch first.",
    )

    args = parser.parse_args(argv or sys.argv[1:])
    if args.command == "clean":
        return clean()
    if args.command == "lint":
        return lint()
    if args.command == "test":
        return test()
    if args.command == "build":
        return build()
    if args.command == "check":
        return check()
    if args.command == "check-release-tag":
        return check_release_tag()
    return publish(
        remote=args.remote,
        branch=args.branch,
        skip_check=args.skip_check,
        skip_main_push=args.skip_main_push,
    )


if __name__ == "__main__":
    raise SystemExit(main())
