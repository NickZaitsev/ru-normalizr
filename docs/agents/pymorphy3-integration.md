# pymorphy3 integration constraints

## Parse ordering and selection

`MorphAnalyzer.parse()` orders candidates by a non-contextual dictionary score.
The first candidate is therefore only a fallback, never contextual
disambiguation. Callers that know a syntactic role or domain lexeme must use
the shared linear `select_parse()` policy and constrain POS, normal form,
gender, animacy, number, case, or grammemes as appropriate. Unknown Cyrillic
words remain valid input; Latin, numeric, Roman, punctuation, and `UNKN` shape
parses are barriers only for scanners that specifically need Russian syntax.

Pymorphy grammemes are typed string-like values. Convert external collections
to ordinary strings and canonicalize them before comparison or cache lookup.
Rare cases must be converted through
`MorphAnalyzer.TagClass.fix_rare_cases()`; local copies of `RARE_CASES` are not
authoritative.

## Domain unit morphology

The packaged OpenCorpora dictionary is old enough to contain semantic
homonyms and missing measurement paradigms: names and geography entries can
rank above units, while some supported units have no usable productive parse.
The typed unit descriptor records expected lemma, gender, animacy,
indeclinability, preferred or forbidden grammemes, and—where necessary—a
validated complete paradigm. A declared seed or paradigm must be validated
before use; failure logs at `DEBUG` and returns the established safe fallback
instead of fabricating endings.

Case-sensitive SI and information symbols are resolved exactly before any
case-folded aliases. In particular, milli and mega prefixes, bit `b` versus
byte `B`, and Cyrillic gray `Гр` versus gram `гр` are distinct. Exact tokens
made solely of Roman letters are protected before Roman-numeral recognition.

`Parse.make_agree_with_number()` is not used globally. It cannot preserve the
project's external-case decisions, exact unit metadata, or the documented
ordinary byte-family forms, and it does not render the numeral itself. It is
appropriate only as a test oracle for narrow dictionary-compatible cases.

## DAWG backend parity and default

Supported CPython installations use the compiled `DAWG2` backend by default
through `pymorphy3[fast]>=2.0,<3`. `DAWG2-Python` remains an upstream portable
dependency, but a false `pymorphy3.dawg.EXTENSION_AVAILABLE` flag on the
supported CI matrix is an installation failure, not a production runtime
mode. Runtime normalization has no backend-specific branches.

Before changing the default, `scripts/pymorphy3_parity.py` produced stable
UTF-8 snapshots in clean portable and compiled environments. Public
normalization, ordered parse signatures, inflections, lexemes, exceptions,
and complete pytest outcomes matched exactly; only the expected backend flag
differed. Diagnostic JSON artifacts are intentionally ignored.

Benchmark recorded on 2026-07-30 with CPython 3.11.15, pymorphy3 2.0.6, and
the same packaged Russian dictionary on Windows x86-64:

```text
python -c "import itertools,time,sys,pymorphy3; from pymorphy3 import dawg; m=pymorphy3.MorphAnalyzer(); words=list(itertools.islice(m.dictionary.words.iterkeys(),10000)); start=time.perf_counter(); [m.parse(w) for w in words]; elapsed=time.perf_counter()-start; print(sys.version.split()[0],dawg.EXTENSION_AVAILABLE,f'{elapsed:.6f}',f'{len(words)/elapsed:.0f}')"

portable: extension=False, 0.810622 s, 12,336 words/s
compiled: extension=True, 0.157345 s, 63,555 words/s
```

This is a short single-machine methodology record, not a universal
performance promise. Correctness parity is the migration gate.
