# Locale encoding and the Windows CI cell

The `windows-latest` CI runner is an English Windows image, so
`locale.getencoding()` there is **cp1252**, which cannot represent Cyrillic at
all. The primary development machine is a Russian Windows install with
**cp1251**, which can. Ubuntu cells are UTF-8.

This makes a whole class of bugs invisible locally: anything that falls back to
the locale encoding works on cp1251 and on Linux, and fails only on the CI
Windows cell. "It passes on my Windows machine" is therefore not evidence.

It has already happened once. The CLI wrote its result with `sys.stdout`'s
locale encoding while `--file`/`--output` were pinned to UTF-8, so redirecting
CLI output on cp1252 died with `UnicodeEncodeError` and every CLI test failed
on `windows-latest` only.

## Rules

- Always pass `encoding="utf-8"` explicitly to `open()`, `read_text()`,
  `write_text()`, and to `subprocess.run()` when capturing text. Never rely on
  `text=True` alone — it decodes with the locale encoding.
- `__main__.py` calls `_use_utf8_stdio()` first thing in `main()`; keep any new
  stream it touches UTF-8 too.
- To reproduce the CI environment on any platform, force the child's encoding:
  `subprocess.run(..., env=dict(os.environ, PYTHONIOENCODING="cp1252"))`. See
  `test_cli_emits_utf8_under_a_non_cyrillic_locale_encoding` in
  `tests/test_api.py`.
- To find latent cases, run the suite with `PYTHONWARNDEFAULTENCODING=1` and
  look for `EncodingWarning` outside `site-packages`.
