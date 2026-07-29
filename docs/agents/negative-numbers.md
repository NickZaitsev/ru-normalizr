# Unary minus vs. hyphen

`protect_negative_numbers` (preprocess, `preprocess_utils.py`) is the single
place that decides whether an ASCII `-` or Unicode `−` in front of a number is
a unary minus. It only accepts the sign at the start of the text, after an
opening bracket, or after whitespace, and it rewrites the accepted ones to
`NEGATIVE_NUMBER_PLACEHOLDER` (``). Everything downstream runs after this
stage, so by the time the numerals stage sees the text, *every* genuine minus is
already a placeholder and every surviving bare `-` is a hyphen joining the
number to the previous token.

## The failure mode

Number-matching regexes in the numerals stage tend to be written as

```python
(?P<num>(?:-|PLACEHOLDER)?\d+...)
```

That bare `-` alternative re-admits exactly the hyphens the preprocessor
deliberately refused. It produced issue #7: `GLM-5.2` matched with `num="-5.2"`,
so the hyphen was consumed into `минус` and the separator vanished
(`GLMминус пять целых две десятых`), while the integer path rendered the same
shape correctly as `GLM-пять`.

`DECIMAL_PATTERN` now guards the alternative with `(?<![^\W_])-`, which asserts
the character before the sign is not word-like — the same positions
`protect_negative_numbers` accepts. `NUMERIC_UNIT_HYPHEN_PATTERN` in
`numerals/_hyphen.py` still carries the unguarded alternative; it is not
reachable today because `is_safe_numeric_hyphen_unit` rejects the affected
inputs first, but it is the same latent bug.

## Rule for new patterns

When adding a regex that matches a signed number in the numerals stage, prefer
matching only `NEGATIVE_NUMBER_PLACEHOLDER`. If a bare `-` must be accepted
(e.g. so the stage still works when invoked directly via `run_stage` without
preprocess), guard it with `(?<![^\W_])`. Cover both `-5.2` and `X-5.2` in the
tests — the two are one character apart and only one of them is a minus.
