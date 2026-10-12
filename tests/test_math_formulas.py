"""Озвучивание формул: команды TeX становятся словами, доллары остаются деньгами."""

import pytest

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.math_formulas import is_math_body, math_block_count, speak_formula


@pytest.mark.parametrize(
    "body, expected",
    [
        (r"\omega", "омега"),
        (r"\varphi", "фи"),
        (r"\Delta", "дельта"),
        (r"\frac{3}{4}", "3 дробь 4"),
        (r"\frac{a + b}{c}", "a плюс b дробь c"),
        (r"\sqrt{ar}", "корень из ar"),
        (r"\sqrt[3]{8}", "корень степени 3 из 8"),
        (r"2 \times 3", "2 умножить на 3"),
        (r"a \cdot b", "a умножить на b"),
        (r"x \in A", "x принадлежит A"),
        (r"A \subset B", "A подмножество B"),
        (r"n \le 5", "n меньше или равно 5"),
        (r"x \neq y", "x не равно y"),
        (r"\text{опоры}", "опоры"),
        (r"\mathsf{для}", "для"),
        (r"r^2", "r в степени 2"),
        (r"L_n", "L индекс n"),
        (r"L_\omega", "L индекс омега"),
        # Цифры остаются цифрами: их читает стадия числительных.
        (r"0^\sharp", "0 в степени диез"),
        (r"90^\circ", "90 градусов"),
        (r"60X", "60 X"),
        (r"a = b", "a равно b"),
    ],
)
def test_speak_formula(body: str, expected: str) -> None:
    assert speak_formula(body) == expected


def test_unknown_command_drops_the_name_but_keeps_the_argument() -> None:
    """Иначе слушатель получает «мэсзфрак» вместо содержимого."""
    assert speak_formula(r"\unknowncmd{опоры}") == "опоры"
    assert speak_formula(r"x \unknownop y") == "x y"


@pytest.mark.parametrize(
    "body",
    [
        r"\omega",
        "x",
        "E",
        "2400 - 60X",
        "a = b",
        "r^2",
    ],
)
def test_is_math_body_accepts_formulas(body: str) -> None:
    assert is_math_body(body) is True


@pytest.mark.parametrize(
    "body",
    [
        "",
        ", 1 ",
        "100 - ",
        "40 тыс. до ",
        "100 до ",
        "1,1",
        "текст между двумя суммами",
    ],
)
def test_is_math_body_rejects_prose_and_money(body: str) -> None:
    assert is_math_body(body) is False


@pytest.mark.parametrize(
    "source, expected_fragment",
    [
        (r"есть $\omega$, — это бесконечность", "есть омега, — это бесконечность"),
        (r"равно $\frac{2400}{84}$ шефелям", "две тысячи четыреста дробь"),
        (r"знак $\sqrt{ar}$, формула", "знак корень из ar, формула"),
        (r"Пусть $\varphi$ — угол", "Пусть фи — угол"),
    ],
)
def test_tts_mode_speaks_formulas(source: str, expected_fragment: str) -> None:
    result = normalize(source, NormalizeOptions.tts(enable_latinization=False))
    assert expected_fragment in result


@pytest.mark.parametrize(
    "source, expected_fragment",
    [
        ("цена выросла с $100 до $200 за баррель", "ста долларов"),
        ("фермы от $40 тыс. до $250 тыс. в год", "долларов"),
    ],
)
def test_money_is_not_read_as_a_formula(source: str, expected_fragment: str) -> None:
    result = normalize(source, NormalizeOptions.tts(enable_latinization=False))
    assert expected_fragment in result
    assert "дробь" not in result
    assert "минус" not in result


def test_safe_mode_leaves_formulas_alone() -> None:
    source = r"есть $\omega$ здесь"
    assert normalize(source, NormalizeOptions.safe()) == source


def test_math_block_count_separates_simple_from_complex() -> None:
    text = (
        r"тут $\omega$ и $\tau$, а также "
        r"$\frac{2400 - 60X}{84} \times 1,5 = \frac{1200 - 30X}{28}$."
    )
    total, complex_blocks = math_block_count(text)
    assert total == 3
    assert complex_blocks == 1


def test_math_block_count_ignores_money() -> None:
    assert math_block_count("с $100 до $200") == (0, 0)
    assert math_block_count("без знака доллара") == (0, 0)


def test_nested_fraction_keeps_the_outer_division() -> None:
    """Внешняя дробь пропадала: обёртка \text внутри мешала правилу совпасть."""
    body = r"\frac{\frac{3}{4} - \text{ шеф.}}{\frac{5}{6}}"
    assert speak_formula(body) == "3 дробь 4 минус шеф. дробь 5 дробь 6"


def test_root_of_a_fraction() -> None:
    assert speak_formula(r"\sqrt{\frac{1}{2}}") == "корень из 1 дробь 2"
