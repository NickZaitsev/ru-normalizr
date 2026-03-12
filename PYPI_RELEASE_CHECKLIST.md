# PyPI Release Checklist

## Before tagging

- Ensure `py -3.12 -m pytest -q` passes.
- Ensure `ru_normalizr/tests` passes in isolation.
- Review `CHANGELOG.md` and add a release entry.
- Update version in:
  - `ru_normalizr/__init__.py`
  - `ru_normalizr/pyproject.toml`
- Confirm `README.md` examples still match actual output.
- Confirm `LICENSE` is present.

## Build validation

- Build a wheel:

```bash
py -3.12 -m pip wheel --no-deps ./ru_normalizr
```

- Build source and wheel distributions:

```bash
py -3.12 -m pip install -r ./ru_normalizr/requirements-dev.txt
py -3.12 -m build ./ru_normalizr
```

- Validate artifacts:

```bash
py -3.12 -m twine check ./ru_normalizr/dist/*
```

## Final publish flow

```bash
py -3.12 -m twine upload ./ru_normalizr/dist/*
```

## Manual review items

- No generated cache files are committed.
- No `build/`, `dist/`, or `*.egg-info/` directories are committed.
- `examples/your_rules.dic` is not present in the built wheel.
- `scripts/` and `tests/` are absent from the built wheel.
- Optional `eng_to_ipa` behavior degrades gracefully when not installed.
- CLI works from stdin and inline text.
