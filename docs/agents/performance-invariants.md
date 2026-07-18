# Performance invariants

- Build numeral token context once per tokenized document. Per-number scans must
  stay bounded by the local grammar window or use the precomputed barrier map.
- To decide whether a dotted unit ends a sentence, inspect the next token only.
  Detokenizing the remaining suffix for every unit makes long books quadratic.
- Word-level morphology and latinization caches must remain bounded; large batch
  paths should populate the same reusable per-word results as small paths.
