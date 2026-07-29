# Dotted numbers: version vs. fraction

`normalize_versions` (`numerals/versions.py`) runs immediately before
`normalize_decimals` in `PipelineNormalizer.run_numerals`. It has to: the
decimals stage matches `\d+[.,]\d+` unconditionally, so whatever it sees first
it claims. Any new rule about a dot between digits belongs **before** the
decimals stage, not inside it.

## What counts as a version

Two structural signals, no list of product names:

1. **Three or more components** (`3.12.1`, `192.168.1.1`). A fraction cannot
   have two dots, so this is unambiguous.
2. **Two components glued by a hyphen to a name** (`GLM-5.2`, `Ту-154.2`).

Signal 2 needs a guard: a named value followed by a recognized unit is a
measurement, not a version (`X-1.5 кг`), so `_is_followed_by_unit` bails out via
`resolve_unit_info`. Signal 2 still catches genuine measurements written without
a unit — `Mach-2.5`, `pH-7.4` read as "два точка пять" — an accepted trade-off,
since nothing structural separates them from a model number.

## Why the old behaviour was broken

`DECIMAL_PATTERN` took `3.12` out of `Python 3.12.1` and left `.1` as literal
text. `detokenize` then treated that orphaned dot as a sentence boundary, and
because `NUMERAL_CONTEXT_BARRIERS` does not include `.`, `get_numeral_case`
scanned across it, found the fraction's own `сотых` (`ADJF plur gent`) and
inflected the stranded `1` to match — producing `… двенадцать сотых. Одного`.

## The pymorphy trap behind model numbers

`Ту-154.2` used to render `сто пятьдесят четырёх целых`. That is not a genitive
rule: pymorphy parses `Ту` as the pronoun `тот` (`ADJF femn sing accs`), the
adjective-agreement scan in `_helpers.get_numeral_case` picks up that case, and
the accusative of `четыре` is syncretic with the genitive. Reading the model
number as a version sidesteps it, because version components are always
rendered in the nominative. Expect the same trap in any new rule that lets a
number inherit case from a preceding capitalized Latin or abbreviated token.
