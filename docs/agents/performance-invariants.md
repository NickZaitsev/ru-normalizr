# Performance invariants

- Build numeral token context once per tokenized document. Per-number scans must
  stay bounded by the local grammar window or use the precomputed barrier map.
- To decide whether a dotted unit ends a sentence, inspect the next token only.
  Detokenizing the remaining suffix for every unit makes long books quadratic.
- Word-level morphology and latinization caches must remain bounded; large batch
  paths should populate the same reusable per-word results as small paths.
- Unit resolution, unit inflection, and grammar canonicalization caches must
  remain bounded and keyed only by immutable semantic inputs.
- Regex callbacks must match against the source with a start position; slicing
  the remaining document inside every callback makes full-book scans quadratic.

## Автоматическая проверка регрессий

`scripts/benchmark.py` измеряет полный пайплайн на синтетических книгах размером
500 000 символов: обычном тексте, смешанном тексте и насыщенном числами тексте.
Через повторяемый `--book` можно добавить одну или несколько реальных UTF-8 книг
или каталогов с `text.txt`. `--manifest MANIFEST.json --real-only` загружает
выбранные `--corpus` из манифеста по одному и перед замером проверяет SHA-256,
размер и число символов; хэш каждого входа и результата, размер результата и
peak RSS попадают в отчёт и участвуют в проверке baseline.
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
uv run python scripts/benchmark.py --manifest benchmarks/corpus/MANIFEST.json \
  --corpus 03_karamzin_history_of_russian_state \
  --corpus 06_semenov_tyan_shansky_tien_shan_travel \
  --real-only --mode tts --samples 3 --warmups 1 \
  --partial-json .benchmarks/real.partial.json
```

Зафиксированный public-domain корпус находится в `benchmarks/corpus`; его
лицензия, источники и SHA-256 указаны в `DATA_LICENSE.md` и `MANIFEST.json`.
Для scaling-профиля используйте `--prefix-chars`; для длинных запусков
`--partial-json` сохраняет результат после каждого сценария.
