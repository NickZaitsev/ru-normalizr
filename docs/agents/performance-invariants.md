# Performance invariants

- Build numeral token context once per tokenized document. Per-number scans must
  stay bounded by the local grammar window or use the precomputed barrier map.
- To decide whether a dotted unit ends a sentence, inspect the next token only.
  Detokenizing the remaining suffix for every unit makes long books quadratic.
- Word-level morphology and latinization caches must remain bounded; large batch
  paths should populate the same reusable per-word results as small paths.
- Regex callbacks must match against the source with a start position; slicing
  the remaining document inside every callback makes full-book scans quadratic.

## Автоматическая проверка регрессий

`scripts/benchmark.py` измеряет полный пайплайн на синтетических книгах размером
500 000 символов: обычном тексте, смешанном тексте и насыщенном числами тексте.
Через `--book` можно добавить реальную UTF-8 книгу или каталог с `text.txt`.
Для каждого сценария выводятся
медиана, p95 и пропускная способность в символах в секунду; перед замерами ленивые
словари и морфологические кеши прогреваются.

Для pull request и push в `main` CI запускает один и тот же benchmark-harness сначала
на base commit, затем на текущем commit в одном Linux runner. Проверка падает, если медиана хотя бы
одного сценария стала хуже более чем на 25%. Сравнение двух commit на одной машине
обязательно: абсолютный порог в миллисекундах нестабилен между локальными и CI-машинами.

Локальный baseline и последующее сравнение:

```bash
uv run python scripts/benchmark.py --mode tts --json .benchmarks/base.json
uv run python scripts/benchmark.py --mode tts --compare .benchmarks/base.json
uv run python scripts/benchmark.py --mode tts --book path/to/book.txt
```
