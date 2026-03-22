import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.abbreviations import expand_abbreviations
from ru_normalizr.dictionary import DictionaryNormalizer
from ru_normalizr.latinization import (
    _resolve_unknown_latin_fallback,
    apply_latinization,
)
from ru_normalizr.numerals import _constants, get_numeral_case, simple_tokenize


class _FakeTag:
    def __init__(self, *grammemes: str):
        self.grammemes = frozenset(grammemes)
        self.POS = None

    def __contains__(self, grammeme: str) -> bool:
        if grammeme == "PNCT":
            raise ValueError(f"Grammeme is unknown: {grammeme}")
        return grammeme in self.grammemes


class _FakeParse:
    def __init__(self, *grammemes: str):
        self.tag = _FakeTag(*grammemes)


class _FakeMorph:
    def parse(self, token: str):
        if token == "Петербург":
            return [_FakeParse("Geox")]
        return []


class RuNormalizrRegressionTests(unittest.TestCase):
    COMPARATIVE_GENITIVE_MARKERS = (
        "не более",
        "не менее",
        "не больше",
        "не меньше",
        "более",
        "менее",
        "больше",
        "меньше",
    )

    def test_single_initial_geographical_name_check_does_not_call_tag_contains_for_pnct(self):
        with patch("ru_normalizr.abbreviations.get_morph", return_value=_FakeMorph()):
            self.assertEqual(
                expand_abbreviations("С. Петербург", NormalizeOptions.tts()),
                "С. Петербург",
            )

    def test_dictionary_latinization_expected_output_for_long_english_text(self):
        text = (
            "Windows Server updates improve browser security, download archives, "
            "and home page access for mobile devices."
        )

        self.assertEqual(
            apply_latinization(text, enabled=True, backend="dictionary"),
            "виндаус сервэр апдэйтс импров браусэр секюрити, даунлооад "
            "аркхивэс, энд хоум пэйдж эксесс фор мобил дэвисес.",
        )

    def test_dictionary_latinization_rewrites_all_ascii_letters_in_long_english_text(self):
        text = (
            "Windows Server updates improve browser security, download archives, "
            "and home page access for mobile devices. Creative teams write code, "
            "share knowledge, monitor metrics, and support online services for "
            "global users."
        )

        result = apply_latinization(text, enabled=True, backend="dictionary")

        self.assertNotEqual(result, text)
        self.assertNotRegex(result, r"[A-Za-z]")

    def test_thousands_abbreviation_does_not_force_prepositional_case_after_na(self):
        tokens = simple_tokenize("выписал чек на сумму 100 тыс. долл.")
        self.assertEqual(get_numeral_case(tokens, tokens.index("100")), "accs")

    def test_money_amount_after_za_uses_accusative_case(self):
        tokens = simple_tokenize("продал корову за 1000 долл.")
        self.assertEqual(get_numeral_case(tokens, tokens.index("1000")), "accs")

    def test_multiword_preposition_po_povodu_uses_genitive_case(self):
        tokens = simple_tokenize("спорили по поводу 5 вопросов")
        self.assertEqual(get_numeral_case(tokens, tokens.index("5")), "gent")

    def test_multiword_preposition_v_svyazi_s_uses_instrumental_case(self):
        tokens = simple_tokenize("сообщение в связи с 5 случаями")
        self.assertEqual(get_numeral_case(tokens, tokens.index("5")), "ablt")

    def test_hyphenated_preposition_iz_za_uses_genitive_case(self):
        tokens = simple_tokenize("отмена из-за 5 ошибок")
        self.assertEqual(get_numeral_case(tokens, tokens.index("5")), "gent")

    def test_comparative_quantifiers_use_genitive_case(self):
        for marker in self.COMPARATIVE_GENITIVE_MARKERS:
            with self.subTest(marker=marker):
                tokens = simple_tokenize(f"скорость {marker} 8 км/ч")
                self.assertEqual(get_numeral_case(tokens, tokens.index("8")), "gent")

    def test_normalize_amount_with_thousands_abbreviation_after_na_summu(self):
        self.assertEqual(
            normalize(
                "Энди Бехтольшайм, заинтересовавшийся этим проектом, сразу же выписал чек на сумму 100 тыс. долл."
            ),
            "Энди Бехтольшайм, заинтересовавшийся этим проектом, сразу же выписал чек на сумму сто тысяч долларов.",
        )

    def test_normalize_amount_with_dollar_abbreviation_before_comma(self):
        self.assertEqual(
            normalize("Например, я продал корову за 1000 долл., а потом ушёл."),
            "Например, я продал корову за одну тысячу долларов, а потом ушёл.",
        )

    def test_normalize_amount_after_imet_uses_accusative_case(self):
        self.assertEqual(
            normalize("Мне лучше иметь 1000 долл., чем корову."),
            "Мне лучше иметь одну тысячу долларов, чем корову.",
        )

    def test_normalize_numeral_after_multiword_preposition(self):
        self.assertEqual(
            normalize("Они говорили по поводу 5 вопросов."),
            "Они говорили по поводу пяти вопросов.",
        )

    def test_normalize_numeral_after_instrumental_multiword_preposition(self):
        self.assertEqual(
            normalize("Заявление подали в связи с 5 случаями."),
            "Заявление подали в связи с пятью случаями.",
        )

    def test_normalize_comparative_speed_quantifiers(self):
        for marker in self.COMPARATIVE_GENITIVE_MARKERS:
            with self.subTest(marker=marker):
                self.assertEqual(
                    normalize(f"со скоростью {marker} 8 км/ч"),
                    f"со скоростью {marker} восьми километров в час",
                )

    def test_hyphenated_bolee_menee_does_not_trigger_genitive_marker(self):
        self.assertEqual(
            normalize("более-менее 5 минут"),
            "более-менее пять минут",
        )

    def test_quantifier_with_chem_can_follow_instrumental_case(self):
        self.assertEqual(
            normalize("не менее чем 5 процентами"),
            "не менее чем пятью процентами",
        )
        self.assertEqual(
            normalize("больше чем 2 людьми"),
            "больше чем двумя людьми",
        )
        self.assertEqual(
            normalize("менее чем 3 случаями"),
            "менее чем тремя случаями",
        )

    def test_external_case_can_flow_past_quantifier_with_chem(self):
        self.assertEqual(
            normalize("в более чем 60 странах"),
            "в более чем шестидесяти странах",
        )

    def test_dictionary_latinization_regressions_keep_current_duplicate_rule_behavior(self):
        options = NormalizeOptions(enable_latinization=True, latinization_backend="dictionary")

        self.assertEqual(
            apply_latinization("engineering", enabled=True, backend="dictionary"),
            "энджинИаинг",
        )
        self.assertEqual(
            apply_latinization("school", enabled=True, backend="dictionary"),
            "скул",
        )
        self.assertEqual(
            apply_latinization("server", enabled=True, backend="dictionary"),
            "сервэр",
        )
        self.assertEqual(normalize("engineering", options), "энджинИаинг")

    def test_normalize_with_dictionary_backend_removes_ascii_letters_from_long_english_text(self):
        options = NormalizeOptions(
            enable_latinization=True,
            latinization_backend="dictionary",
        )
        text = (
            "Browser updates improve network security and home storage systems, "
            "while engineering teams download source archives, review server logs, "
            "and write stable code for remote support platforms."
        )

        result = normalize(text, options)

        self.assertNotEqual(result, text)
        self.assertNotRegex(result, r"[A-Za-z]")

    def test_dictionary_latinization_handles_mixed_russian_and_english_text(self):
        text = (
            "Сегодня Windows Server обновил browser security, а support team "
            "review logs и пишет stable code для remote platform."
        )

        result = apply_latinization(text, enabled=True, backend="dictionary")

        self.assertEqual(
            result,
            "Сегодня виндаус сервэр обновил браусэр секюрити, а саппот тим "
            "рэвью логс и пишет стэбл кодэ для рэмоут плэтфом.",
        )
        self.assertNotRegex(result, r"[A-Za-z]")
        self.assertIn("Сегодня", result)
        self.assertIn("обновил", result)
        self.assertIn("для", result)

    def test_ipa_latinization_falls_back_to_bundled_dictionary_when_requested_file_is_missing(self):
        self.assertEqual(
            apply_latinization(
                "Beobachtung",
                enabled=True,
                backend="ipa",
                dictionary_filename="65_ЛАТИНИЦА@.dic",
            ),
            "бэобэчтюнг",
        )

    def test_ipa_unknown_fallback_cache_reuses_resolved_word(self):
        _resolve_unknown_latin_fallback.cache_clear()
        calls: list[str] = []

        def fake_apply(text: str, dictionaries_path: Path, filename: str) -> str:
            del dictionaries_path, filename
            calls.append(text)
            if text == "mystery":
                return "мистери"
            return text

        with patch(
            "ru_normalizr.latinization._apply_dictionary_latinization",
            side_effect=fake_apply,
        ):
            self.assertEqual(
                _resolve_unknown_latin_fallback("mystery", "C:/tmp", "latinization.dic"),
                "мистери",
            )
            self.assertEqual(
                _resolve_unknown_latin_fallback("mystery", "C:/tmp", "latinization.dic"),
                "мистери",
            )

        self.assertEqual(calls, ["mystery", "мистери"])

    def test_dictionary_normalizer_precompiles_simple_chunks_once(self):
        with TemporaryDirectory() as tmp_dir:
            dic_path = Path(tmp_dir) / "bulk.dic"
            dic_path.write_text(
                "\n".join(f"token{i}=replacement{i}" for i in range(1001)),
                encoding="utf-8",
            )
            normalizer = DictionaryNormalizer(dictionaries_path=tmp_dir)

            with patch("ru_normalizr.dictionary._compile_simple_mapping_patterns") as mocked:
                self.assertEqual(
                    normalizer.apply("token1 token999"),
                    "replacement1 replacement999",
                )
                self.assertEqual(
                    normalizer.apply("token2"),
                    "replacement2",
                )

            mocked.assert_not_called()

    def test_unit_candidate_does_not_glue_meter_and_preposition_into_millivolt(self):
        with patch.dict(
            _constants.UNITS_DATA,
            {"мв": ("милливольт", "masc", "measure")},
        ):
            self.assertEqual(
                normalize("1,5 м в секунду (90 м в минуту)"),
                "одна целая пять десятых метра в секунду (девяносто метров в минуту)",
            )

    def test_unit_candidate_does_not_treat_preposition_k_as_unit_after_number(self):
        with patch.dict(
            _constants.UNITS_DATA,
            {"к": ("кулон", "masc", "measure")},
        ):
            self.assertEqual(
                normalize("Соотношение 3 к 1."),
                "Соотношение три к одному.",
            )


if __name__ == "__main__":
    unittest.main()
