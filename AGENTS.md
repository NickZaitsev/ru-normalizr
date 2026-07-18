# ru-normalizr — Russian text normalization for TTS/NLP

## Core principle

Generalizable, morphology-aware rules. Never add a one-off replacement for a
single token or phrase — if a bug reproduces, fix the rule, not the string.
Target production-ready quality: no quick hacks or fragile workarounds unless
explicitly requested.

## Pipeline stages

years/dates/time → numerals → abbreviations/initials → latinization →
preprocess/cleanup. Before fixing, identify the responsible stage and read its
tests in `tests/`. Do not edit unrelated stages.

## Tests and completion

- Bugfix workflow: reproduce → add a failing test → smallest correct fix → validate.
- Full validation: `py -3.12 scripts/dev.py check`; quick iteration:
  `py -3.12 scripts/dev.py test` / `lint`.
- A task is "Done" only when tests pass and the change is verified end-to-end.
- If tests were failing before your change, report which failures are
  pre-existing — do not claim the repo is green.

## Commits

- Commit finished work yourself: atomic conventional commits, linters run first.
- Work directly on the current branch; no feature branches unless asked.
- Maintain `.gitignore` yourself as generated/temp files appear. Never commit
  build outputs, egg-info, caches, or secrets/.env files.

## Changelog and versions

- Any user-visible change goes to `CHANGELOG.md` under `## Unreleased`.
- Never bump the version outside explicit release tasks. On release, keep
  `__init__.py`, `pyproject.toml`, and `CHANGELOG.md` in sync (see `VERSIONING.md`).

## Stability and YAGNI

- Public API, CLI flags, option names, and defaults are stable — do not change
  them unless the task explicitly requires it.
- Do not add infrastructure, integrations, or dependencies nobody asked for;
  propose first.

## Final report

What changed, which checks ran, remaining risks, TL;DR in Russian,
conventional-commit message.

# Gotchas and observations

Record working notes in `docs/agents/`. Before finishing, ask: "would the next
agent make a mistake without knowing this AND is it important enough?" If yes,
add a ≤2-line bullet here (full write-up in `docs/agents/<topic>.md`, linked).
No trivial, obvious, or temporary notes in this file.