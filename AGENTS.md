# AGENTS.md

## Project purpose

This repository contains `ru-normalizr`, a Russian text normalization library for TTS and NLP.

Core goals:
- preserve correctness of Russian numeral and grammar normalization
- prefer generalizable fixes over narrow hardcoded replacements
- avoid regressions in already working normalization cases
- keep packaging, CLI, tests, and release metadata consistent

## How to work in this repo

Before making changes, first inspect:
- `README.md`
- `CHANGELOG.md`
- `VERSIONING.md`
- relevant files in `tests/`

When changing behavior, understand which stage is responsible before editing code:
- years / dates / time
- numerals
- abbreviations / initials
- latinization
- preprocess / cleanup
- pipeline ordering

Do not make broad edits across unrelated stages unless clearly necessary.

## Change philosophy

Prefer the smallest correct fix.

Prefer:
- rule improvements that generalize
- morphology-aware or context-aware fixes
- adding or tightening tests before or together with the fix
- preserving existing public behavior unless the task explicitly requires a change

Avoid:
- one-off replacements for a single phrase if the real issue is in a reusable rule
- silent behavior changes without tests
- changing defaults casually
- unnecessary refactors during bugfix tasks
- adding dependencies unless explicitly justified

If a bug can be reproduced, add or update a test that fails before the fix whenever practical.

Do not add special-case replacements for a single token, phrase, or sentence unless the repository already intentionally handles that class of exceptions and the general rule approach is demonstrably worse.

Before changing normalization behavior, inspect existing tests for that feature area to understand the current intended behavior.

Preferred bugfix workflow:
1. reproduce the issue
2. locate the responsible normalization stage
3. add or update a failing test when practical
4. implement the smallest correct fix
5. run targeted checks
6. run broader validation if the change has wider impact
7. update docs/changelog if needed

## Tests and validation

For behavior changes, add or update tests in `tests/`.

Run the relevant checks before finishing.
Preferred full validation flow:

```bash
py -3.12 scripts/dev.py check
```

If only a quick targeted pass is needed during iteration, you may use:

```bash
py -3.12 scripts/dev.py test
py -3.12 scripts/dev.py lint
```

If tests are already failing before your change, do not claim the repository is fully green. Report which failures were pre-existing and which are caused or fixed by your changes.
If something could not be run, say so explicitly.

## Changelog and release discipline

Follow `VERSIONING.md` and `PYPI_RELEASE_CHECKLIST.md`.

### Update `CHANGELOG.md`

Update `CHANGELOG.md` for any user-visible change, including:

* normalization behavior changes
* bug fixes affecting output
* CLI changes
* packaging / release / CI changes relevant to users or contributors
* meaningful documentation updates

Put unreleased work under `## Unreleased` unless the task is explicitly a release task.

### Version bumps

Do not bump the version unless the task is explicitly about making a release or preparing a release.

When performing a release:

* update version in `__init__.py`
* update version in `pyproject.toml`
* add the release entry in `CHANGELOG.md`
* keep versions synchronized

Any intentional normalization output change must be covered by tests and mentioned in `CHANGELOG.md`.

## Instruction priority

If instructions conflict, follow this order:
1. explicit user task
2. repository safety and correctness
3. this AGENTS.md
4. local optimization or refactoring preferences

Do not change public function signatures, option names, CLI flags, or default behaviors unless the task explicitly requires it.

## Documentation rules

If public behavior changes, update examples and docs that would become outdated, especially:

* `README.md`
* CLI usage examples
* option descriptions
* release notes / changelog

Do not rewrite large parts of the README unless needed for the task.

## Code style

Keep the existing project style.

* keep edits focused
* avoid unnecessary renames
* avoid unrelated formatting churn
* preserve import and module organization unless there is a clear reason to change it

## Packaging and repository hygiene

Do not commit generated artifacts or caches.
Do not commit build outputs, egg-info folders, or temporary files.
Do not add files to distributions unless they are intentionally part of the package.

## When uncertain

If multiple fixes are possible, prefer the one that:

1. preserves current expected behavior
2. is covered by tests
3. is more general and less ad hoc
4. keeps the public API and CLI stable

## Final task output

When finishing a task

1. run
```bash
py -3.12 scripts/dev.py check
````

2. Update CHANGELOG.md
Do not update `CHANGELOG.md` for purely internal refactors or test-only changes unless they affect contributors in a meaningful way.

3. provide:
* what changed
* which files were modified
* which checks/tests were run
* any remaining risks or edge cases
* TL;DR in Russian
* conventional commits commit name

