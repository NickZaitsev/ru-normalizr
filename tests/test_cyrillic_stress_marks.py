import unittest

from ru_normalizr import Normalizer, normalize


class RuNormalizrCyrillicStressMarkTests(unittest.TestCase):
    def test_preprocess_rewrites_combining_stress_marks_to_plus(self):
        normalizer = Normalizer()
        self.assertEqual(
            normalizer.run_stage("preprocess", "Фри\u0301дрих А\u0301вгуст фон Ха\u0301йек."),
            "Фр+идрих +Август фон Х+айек.",
        )

    def test_normalize_preserves_cyrillic_stress_information(self):
        self.assertEqual(
            normalize("Фри\u0301дрих А\u0301вгуст фон Ха\u0301йек."),
            "Фр+идрих +Август фон Х+айек.",
        )


if __name__ == "__main__":
    unittest.main()
