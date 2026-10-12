import unittest

from ru_normalizr import NormalizeOptions, Normalizer, normalize


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

    def test_latinized_word_gets_one_stress_mark(self):
        # eng_to_ipa marks both parts of a compound as primary; two "+" in one word
        # are read as two stresses and break it.
        for source, expected in (
            ("microsoft", "м+айкроусофт"),
            ("windows", "в+индоуз"),
            ("engineering", "+энджэнирин"),
        ):
            with self.subTest(source=source):
                self.assertEqual(
                    normalize(
                        source,
                        NormalizeOptions.tts(enable_latinization_stress_marks=True),
                    ),
                    expected,
                )

    def test_each_word_keeps_its_own_mark(self):
        self.assertEqual(
            normalize(
                "microsoft windows",
                NormalizeOptions.tts(enable_latinization_stress_marks=True),
            ),
            "м+айкроусофт в+индоуз",
        )


if __name__ == "__main__":
    unittest.main()
