# PyPI Release Checklist

## Before tagging

- Ensure the working tree is in the state you want to publish.
- Review `CHANGELOG.md` and add a release entry.
- Update version in:
  - `__init__.py`
  - `pyproject.toml`
- Confirm `README.md` examples still match actual output.
- Confirm `LICENSE` is present.

## Install tooling

```bash
py -3.12 -m pip install -r requirements-dev.txt
```

## Preferred validation flow

```bash
py -3.12 scripts/dev.py check
```

`check` already runs the full release validation flow:

- `clean`
- version sync check between `__init__.py` and `pyproject.toml`
- `ruff check .`
- `pytest -q`
- fresh build of `dist/*`
- `twine check dist/*`

`clean` inside `check` removes local build/cache junk:

- `build/`
- `dist/`
- `.tmp_dist/`
- `ru_normalizr.egg-info/`
- `.pytest_cache/`
- `.ruff_cache/`
- all `__pycache__/`
- dictionary cache files like `dictionaries/**/dictionaries_*.pkl`

## Optional manual commands

Use these only when you need a single step:

```bash
py -3.12 scripts/dev.py clean
py -3.12 scripts/dev.py build
py -3.12 scripts/dev.py test
py -3.12 scripts/dev.py lint
```

## Preferred publish flow

```bash
py -3.12 scripts/dev.py publish
```

`publish` now uses the GitHub release flow instead of local `twine upload`.
It will:

- run `check` unless you pass `--skip-check`
- verify that `__init__.py` and `pyproject.toml` versions match
- require a clean git working tree
- push the current `main` branch to `origin`
- create a git tag like `v0.1.2`
- push that tag to GitHub
- let `.github/workflows/release.yml` publish the package to PyPI

Useful variants:

```bash
py -3.12 scripts/dev.py publish --skip-check
py -3.12 scripts/dev.py publish --remote origin --branch main
py -3.12 scripts/dev.py publish --skip-main-push
```

## Manual review items

- No generated cache files are committed.
- No `build/`, `dist/`, or `*.egg-info/` directories are committed.
- `examples/your_dictionary.dic` is not present in the built distributions.
- `scripts/` and `tests/` are absent from the built wheel.
- Optional `eng_to_ipa` behavior degrades gracefully when not installed.
- CLI works from stdin and inline text.
- GitHub `Release` workflow is green for the pushed version tag.
