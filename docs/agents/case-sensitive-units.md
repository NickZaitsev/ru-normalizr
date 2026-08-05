# Case-sensitive units

Keep case-insensitive aliases lowercase in `UNITS_DATA`. Put SI symbols whose
case changes their meaning (for example `мА` or `кА`) in
`CASE_SENSITIVE_UNITS_DATA`, and resolve input through `resolve_unit_info`.
Lowercasing those symbols directly would turn ordinary `ма`/`ка` tokens into
measurement units.

## Обнаруженные коллизии

Регистр является частью символа единицы и приставки. Текущий fallback через
`UNITS_DATA.get(original.lower())` уже даёт несколько неверных преобразований:

- `мПа`, `мН`, `мГц` читаются как мега-, а не милли-единицы;
- `Мг`, `Мм`, `Мс`, `Мл`, `МФ` читаются как милли-, а не мега-единицы;
- обозначения концентрации `М`, `мМ`, `нМ` принимаются за `м`, `мм`, `нм`;
- неполный exact-case набор скоростей путает биты и байты: `Mb/s`, `kBps`,
  `GBps` разрешаются неправильно.

Исправление должно переносить неоднозначные символы целыми семействами в
exact-case таблицу. Недостаточно добавить один частный alias: неизвестный
вариант регистра не должен проваливаться обратно в регистронезависимый alias с
другим смыслом. Производные коллекции `ALL_UNITS` и `ENTITY_KEYWORDS` также не
должны терять регистр exact-case ключей; проверки принадлежности должны идти
через общий резолвер или через раздельные exact/folded наборы.
