"""Литеральные префильтры перед редкими полнотекстовыми regex-проходами.

Guard обязан быть *необходимым* условием совпадения паттерна: если литерала в
тексте нет, паттерн не может сработать. Проверяется это не рассуждением, а
сравнением вывода при живых и при отключённых guard'ах на текстах, где такие
конструкции встречаются.
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.text_scan import GuardedPattern, guarded_patterns, required_guards

# Тексты подобраны так, чтобы задеть каждый защищённый паттерн: знак номера,
# госномер, телефон, размеры, дюймы, угловые минуты и секунды, неравенства,
# приблизительность, плюс-версии.
GUARD_SENSITIVE_TEXTS = (
    "Дело № 5 передано в суд, а под № 7 лежит второй том.",
    "Со № 12 начинается опись, к № 3 приложены копии.",
    "Машина с номером А123ВС77 стоит во дворе дома 7Б.",
    "Позвоните по номеру +7 (495) 123-45-67 до обеда.",
    "Экран размером 15,6″ и матрица 1920 × 1080 точек.",
    "Угол 45′ и отклонение 30″ зафиксированы прибором.",
    "Если x < 10 и y > 3, то условие выполнено.",
    "Пришло ~500 человек, счёт 2:1 в пользу гостей.",
    "Мы перешли на C++17 и держим f/2.8 на объективе.",
    "Ширина 3 м, глубина 200 м, температура 22 °C.",
    "Обычная проза без единого редкого знака, только слова и числа: в 1812 году.",
)


class GuardedPatternRegistryTests(unittest.TestCase):
    def test_guards_are_registered(self):
        patterns = guarded_patterns()
        self.assertTrue(patterns, "ожидался хотя бы один защищённый паттерн")
        for guarded in patterns:
            self.assertIsInstance(guarded, GuardedPattern)

    def test_guard_rejects_text_without_its_literal(self):
        # Без литерала guard обязан отсечь проход, иначе оптимизации нет.
        skipped = sum(1 for g in guarded_patterns() if not g.may_match("простая проза без знаков"))
        self.assertGreater(skipped, 0)


class GuardNecessityTests(unittest.TestCase):
    """Guard обязан совпадать всюду, где совпадает сам паттерн."""

    def _samples(self) -> list[str]:
        samples = list(GUARD_SENSITIVE_TEXTS)
        path = Path("benchmarks/corpus/03_karamzin_history_of_russian_state.txt")
        if path.exists():
            book = path.read_text(encoding="utf-8")[:200000]
            step = 4000
            samples.extend(book[i : i + step] for i in range(0, len(book), step))
        return samples

    def test_every_guard_matches_wherever_its_pattern_matches(self):
        samples = self._samples()
        for guarded in guarded_patterns():
            raw = guarded.pattern
            for sample in samples:
                if raw.search(sample) is not None and not guarded.may_match(sample):
                    self.fail(
                        f"guard пропускает совпадение паттерна {raw.pattern!r} "
                        f"в тексте {sample[:80]!r}"
                    )


class RequiredGuardsTests(unittest.TestCase):
    def test_mandatory_literal_is_extracted(self):
        self.assertEqual(required_guards(r"(?<!\w)Vol\.\s*(?=\d)"), ("Vol.",))
        self.assertEqual(required_guards(r"(?P<x>КоАП)\s+РФ"), ("КоАП",))
        self.assertEqual(required_guards(r"(?:ab)+c"), ("ab",))

    def test_alternation_yields_one_guard_per_branch(self):
        self.assertEqual(
            required_guards(r"(?<!\w)(?:тыс\.|млн\.|руб\.)(?!\w)"),
            ("тыс.", "млн.", "руб."),
        )

    def test_plain_character_class_yields_its_characters(self):
        self.assertEqual(required_guards(r"(?P<operator>[<>])\s+(?=\d)"), ("<", ">"))

    def test_optional_and_open_ended_parts_are_not_guards(self):
        # Ни одна из этих конструкций не обязана присутствовать в совпадении.
        self.assertEqual(required_guards(r"\d+(?:кг)?"), ())
        self.assertEqual(required_guards(r"[а-я]+\d+"), ())
        self.assertEqual(required_guards(r"(?:абв|\d)"), ())


class GuardEquivalenceTests(unittest.TestCase):
    """Вывод с guard'ами и без них должен совпадать посимвольно."""

    def _compare(self, options: NormalizeOptions) -> None:
        for text in GUARD_SENSITIVE_TEXTS:
            with self.subTest(text=text[:40]):
                guarded_output = normalize(text, options)
                with patch.object(GuardedPattern, "may_match", return_value=True):
                    unguarded_output = normalize(text, options)
                self.assertEqual(guarded_output, unguarded_output)

    def test_tts_mode_output_is_unchanged_by_guards(self):
        self._compare(NormalizeOptions.tts())

    def test_safe_mode_output_is_unchanged_by_guards(self):
        self._compare(NormalizeOptions.safe())


if __name__ == "__main__":
    unittest.main()
