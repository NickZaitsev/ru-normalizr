# Stage ordering: the specific pattern runs first

Every stage is a set of greedy regexes over the whole text. There is no
arbitration: whichever stage reaches a span of characters first claims it, and
the stage that would have matched a *longer, more specific* span gets whatever
debris is left. Debris is worse than no match at all, because it is usually
still numeric and the numerals stage will happily read it as something.

Three bugs of exactly this shape have been fixed so far:

| Winner took | Loser got | Symptom |
|---|---|---|
| `decimals` took `3.12` | `.1` | `Python 3.12.1` → `три целых двенадцать сотых. Одного` |
| `years` took `2021 года` | `15.03.` | `15.03.2021 года` → `пятнадцать целых три сотых. Две тысячи…` |
| `decimals` took `5.2` | `10-` | `10-5.2` → `десять пять целых две десятых` (separator gone) |

In each case the orphan's trailing dot became a sentence boundary in
`detokenize`, and because `NUMERAL_CONTEXT_BARRIERS` does not include `.`,
`get_numeral_case` scanned straight across it and inflected the stranded number
to agree with words from the previous "sentence".

## The rule

A full date is a special case of a year; a version is a special case of a
decimal; a range is a special case of two numbers. **The special case must run
first.** `normalize_text` therefore runs `dates_time` before `years`, and
`normalize_versions` before `normalize_decimals`.

The same rule applies to authority, not just to span length: an explicit
instruction outranks a guess. `dictionary` therefore runs before
`latinization` — while it ran second it could not match any Latin token in TTS
mode, because latinization had already rewritten the token into Cyrillic, so
user rules were silently ignored in the pipeline's main mode.

## Reordering is usually right, but never free

Putting the specific stage first is the correct fix, not a workaround. But a
stage that has spent its whole life running second can carry latent defects
that only the first position exposes. Reordering `dates_time` before `years`
unmasked two of them at once: the shared year fragment consumed the whitespace
before an optional era word (`…двадцатого годаг.`), and the dotted date pattern
had no era tail at all.

**The test suite will not catch this.** Both the swap and the defects it exposed
passed all 307 tests. Before reordering stages, run a differential over a corpus
of inputs in the affected domain and read every diff by hand; then land the
unmasked fixes as their own commit, verified through
`run_stage("<stage>", ...)`, before flipping the order.
