# Выпуск на PyPI

## Перед созданием тега

- Убедитесь, что рабочее дерево содержит только изменения, предназначенные для
  выпуска.
- Проверьте `CHANGELOG.md` и добавьте запись о версии.
- Обновите версию в `__init__.py` пакета и в `pyproject.toml`.
- Убедитесь, что примеры в `README.md` соответствуют фактическому результату.
- Убедитесь, что файл `LICENSE` присутствует.

## Установка инструментов

```bash
uv sync --frozen
```

## Основная проверка

```bash
uv run python scripts/dev.py check
uv run python scripts/dev.py check-release-tag
```

Команда `check` выполняет полный цикл проверки выпуска:

- `clean`;
- сверку версии между `__init__.py` пакета и `pyproject.toml`;
- `ruff check .`;
- `pytest -q`;
- чистую сборку `dist/*`;
- `twine check dist/*`.

`check-release-tag` дополнительно проверяет, что текущий тег `v*` совпадает с
версией пакета. Команда предназначена для release workflow и требует запуска
на коммите с тегом.

Встроенный в `check` этап `clean` удаляет локальные результаты сборки и кеши:

- `build/`;
- `dist/`;
- `.tmp_dist/`;
- `src/ru_normalizr.egg-info/` и старый `ru_normalizr.egg-info/`;
- `.pytest_cache/`;
- `.ruff_cache/`;
- все `__pycache__/`;
- кеши словарей вида
  `src/ru_normalizr/dictionaries/**/dictionaries_*.pkl`.

## Отдельные команды

Используйте их, когда требуется выполнить только один этап:

```bash
uv run python scripts/dev.py clean
uv run python scripts/dev.py build
uv run python scripts/dev.py test
uv run python scripts/dev.py lint
```

## Публикация

```bash
uv run python scripts/dev.py publish
```

`publish` использует GitHub release flow вместо локального `twine upload`.
Команда:

- запускает `check`, если не передан `--skip-check`;
- сверяет версии в `__init__.py` пакета и `pyproject.toml`;
- требует чистое рабочее дерево;
- отправляет текущую ветку `main` в `origin`;
- создаёт git-тег вида `v0.1.2`;
- отправляет тег в GitHub;
- передаёт публикацию в PyPI workflow
  `.github/workflows/release.yml`.

Дополнительные варианты:

```bash
uv run python scripts/dev.py publish --skip-check
uv run python scripts/dev.py publish --remote origin --branch main
uv run python scripts/dev.py publish --skip-main-push
```

## Ручная проверка

- Сгенерированные кеши не добавлены в репозиторий.
- Каталоги `build/`, `dist/` и `*.egg-info/` не добавлены в репозиторий.
- `scripts/` и `tests/` отсутствуют в собранном колесе.
- `eng_to_ipa` остаётся зависимостью по умолчанию; при ошибке её импорта
  IPA-бэкенд корректно переключается на словарный.
- CLI работает со стандартным вводом и текстом в аргументе.
- GitHub workflow `Release` успешно завершился для отправленного тега версии.
