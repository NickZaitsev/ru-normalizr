# Output conventions

- A parameter noun before a measurement (`при температуре 660 °C`, `со
  скоростью 60 км/ч`, `диаметром 5 м`) is named by that measurement, so the
  measurement is an apposition and stays nominative in any case the parameter
  itself carries. The genitive reading needs an explicit `в` in the source:
  `при температуре в 660 градусов`. The closed list of these nouns lives in
  `MEASURE_PARAMETER_HEADS`.
- A relational quantity noun in the `в …` frame governs a genitive instead,
  because the quantity is its complement, not an apposition: `в возрасте
  двадцати пяти лет`, `в количестве пяти штук`, `в размере пятисот рублей`
  (`LOCATIVE_GENITIVE_QUANTITY_HEADS`).
- A counted unit is never oblique. `двухстах метрах`, `двух атмосферах` and
  `пяти километрах в час` are ungrammatical in every construction, so no case
  from the surrounding phrase may reach the unit; `tests/test_morphology_policy.py`
  asserts this as an invariant.
- Government from outside the quantity is unaffected: `в 200 м от реки` →
  `в двухстах метрах от реки`, `в 12 городах` → `в двенадцати городах`.
- Ranges with `с … по …` end in singular `год` / `век`; `до … века` is also
  singular.
- Byte-family units use ordinary Russian counting forms consistently:
  `1 байт`, `2–4 байта`, `5 байтов`, including prefixed units.
- Регистр латинских информационных обозначений является частью смысла:
  `Mb`, `Mbps`, `Mb/s` — мегабиты, а `MB`, `MBps`, `MB/s` — мегабайты.
  Неизвестный неоднозначный вариант регистра не угадывается.
- Ограниченные составные единицы читаются целиком: `/` задаёт сохранённое в
  реестре отношение (`мг/кг` → «миллиграммов на килограмм», `мл/мин` →
  «миллилитров в минуту»), а `·` — лексикализованное произведение
  (`кВт·ч` → «киловатт-час»). Вложенные и неизвестные выражения не разбираются.
- References governed by `см.` / `смотри` use an accusative reference noun and
  a cardinal label: `смотри рисунок два, таблицу три, страницу четыре`.
- Default and safe initial settings use ordinary Russian letter names (`Е. → е`)
  and preserve source punctuation, including when initial expansion is enabled.
- TTS initial settings double isolated vowel names (`Е. → ее`) and surround a
  non-final surname-first initial with comma pauses (`Рихтер Ч. разработал →
  Рихтер, чэ, разработал`); both settings can be overridden independently.
- Latin `A` is read as `эй`.
