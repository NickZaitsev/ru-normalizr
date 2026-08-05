import pytest

from ru_normalizr import normalize
from ru_normalizr.numerals.unit_expressions import resolve_unit_expression


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Лампа мощностью 9 Вт потребляет 0,075 кВт·ч за 8 ч.",
            "Лампа мощностью девять ватт потребляет ноль целых семьдесят пять тысячных "
            "киловатт-часа за восемь часов.",
        ),
        (
            "Введите 0,25 мл раствора со скоростью 2 мл/мин.",
            "Введите ноль целых двадцать пять сотых миллилитра раствора со скоростью двух "
            "миллилитров в минуту.",
        ),
        (
            "Датчик зарегистрировал давление 5 мПа, силу 2 мН и частоту 3 мГц.",
            "Датчик зарегистрировал давление пять миллипаскалей, силу два миллиньютона "
            "и частоту три миллигерца.",
        ),
        (
            "В повреждённом источнике указано значение 5 М без пояснений.",
            "В повреждённом источнике указано значение пять М без пояснений.",
        ),
        (
            "Первый канал передаёт 5 Mb/s, второй — 2 kBps, третий — 3 GBps.",
            "Первый канал передаёт пять мегабит в секунду, второй — два килобайта "
            "в секунду, третий — три гигабайта в секунду.",
        ),
        (
            "Препарат назначают по 5 мг/кг массы тела 2 раза в сутки.",
            "Препарат назначают по пять миллиграммов на килограмм массы тела два раза в сутки.",
        ),
        (
            "Лазер работает на длине волны 532 нм, толщина покрытия — 2,5 мкм.",
            "Лазер работает на длине волны пятьсот тридцать два нанометра, "
            "толщина покрытия — две целых пять десятых микрометра.",
        ),
    ],
)
def test_fixed_unit_regressions(source: str, expected: str) -> None:
    assert normalize(source) == expected


@pytest.mark.parametrize("raw", ["мг/кг", "мл / мин", "кВт · ч", "моль/л"])
def test_bounded_expression_parser_accepts_registered_expressions(raw: str) -> None:
    assert resolve_unit_expression(raw) is not None


@pytest.mark.parametrize("raw", ["foo/bar", "мг/кг/сут", "м^4", "5/7"])
def test_bounded_expression_parser_rejects_unknown_or_nested_expressions(raw: str) -> None:
    assert resolve_unit_expression(raw) is None
