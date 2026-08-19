import string
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.abbreviations import expand_abbreviations
from ru_normalizr.dictionary import DictionaryNormalizer
from ru_normalizr.latinization import (
    _clear_latinization_word_caches,
    _ipa_convert_batch,
    _ipa_convert_words,
    _resolve_unknown_latin_fallback,
    _resolve_unknown_latin_fallbacks,
    apply_latinization,
)
from ru_normalizr.numerals import _constants, _helpers, get_numeral_case, simple_tokenize
from ru_normalizr.numerals.cardinals import normalize_cardinal_numerals


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
    def test_genitive_plural_heuristic_preserves_all_caps_for_every_ending(self):
        cases = (
            ("НОВЫЕ", "ADJF", "НОВЫХ"),
            ("СИНИЕ", "ADJF", "СИНИХ"),
            ("НОВЫЙ", "ADJF", "НОВОГО"),
            ("МОЛОДОЙ", "ADJF", "МОЛОДОГО"),
            ("СИНИЙ", "ADJF", "СИНЕГО"),
            ("СИНЕЕ", "ADJF", "СИНЕГО"),
            ("НОВАЯ", "ADJF", "НОВОЙ"),
            ("СИНЯЯ", "ADJF", "СИНЕЙ"),
            ("КРАТКОЕ", "ADJF", "КРАТКОЕ"),
            ("НОВЫЕ", "NOUN", "НОВЫЕ"),
        )
        for word, pos, expected in cases:
            with self.subTest(word=word, pos=pos):
                self.assertEqual(
                    _helpers.apply_genitive_plural_heuristic(word, pos),
                    expected,
                )

    def test_dictionary_normalizer_does_not_write_pickle_cache(self):
        with TemporaryDirectory() as tmp_dir:
            dictionaries_path = Path(tmp_dir)
            (dictionaries_path / "custom.dic").write_text(
                "исходник=замена\n", encoding="utf-8"
            )

            first = DictionaryNormalizer(dictionaries_path=dictionaries_path)
            second = DictionaryNormalizer(dictionaries_path=dictionaries_path)

            self.assertEqual(first.apply("исходник"), "замена")
            self.assertEqual(second.apply("исходник"), "замена")
            self.assertEqual(list(dictionaries_path.glob("*.pkl")), [])

    def test_dictionary_rules_win_over_latinization_guesses(self):
        # A dictionary rule is an explicit instruction, latinization is a guess.
        # While the dictionary stage ran last it could never match a Latin token
        # in TTS mode, because latinization had already rewritten it: the rule
        # for "WireGuard" was silently ignored and the guess "вээгюад" won.
        with TemporaryDirectory() as tmp_dir:
            dictionaries_path = Path(tmp_dir)
            (dictionaries_path / "custom.dic").write_text(
                "WireGuard=вайргард\nOAuth=оауф\n", encoding="utf-8"
            )
            for mode in (NormalizeOptions.safe(), NormalizeOptions.tts()):
                options = replace(mode, dictionaries_path=dictionaries_path)
                with self.subTest(mode=options.mode):
                    self.assertEqual(normalize("WireGuard", options), "вайргард")
                    self.assertEqual(normalize("OAuth", options), "оауф")
                    self.assertEqual(
                        normalize("туннель WireGuard поднят", options),
                        "туннель вайргард поднят",
                    )
            # Latin without a rule still reaches latinization in TTS mode.
            tts = replace(NormalizeOptions.tts(), dictionaries_path=dictionaries_path)
            self.assertNotRegex(normalize("Kubernetes", tts), r"[A-Za-z]")

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

    @staticmethod
    def _alpha_word(index: int) -> str:
        letters: list[str] = []
        current = index
        while True:
            current, remainder = divmod(current, 26)
            letters.append(chr(ord("a") + remainder))
            if current == 0:
                break
            current -= 1
        return "token" + "".join(reversed(letters))

    def test_single_initial_geographical_name_check_does_not_call_tag_contains_for_pnct(self):
        with patch(
            "ru_normalizr.abbreviations.parse_word",
            side_effect=lambda token: tuple(_FakeMorph().parse(token)),
        ):
            self.assertEqual(
                expand_abbreviations("С. Петербург", NormalizeOptions.tts()),
                "С. Петербург",
            )

    def test_dictionary_latinization_expected_output_for_long_english_text(self):
        # TASK-12 option (a): fallback output is checked against deliberate
        # pronunciations, not snapshots of the productive rules' mistakes.
        text = (
            "Windows Server updates improve browser security, download archives, "
            "and home page access for mobile devices."
        )

        self.assertEqual(
            apply_latinization(text, backend="dictionary"),
            "виндоус сервер апдейтс импрув браузер секьюрити, даунлоуд "
            "аркайвз, энд хоум пэйдж эксесс фор мобайл дивайсиз.",
        )

    def test_dictionary_latinization_common_word_ground_truth(self):
        pronunciations = {
            "support": "сапорт",
            "platform": "платформ",
            "download": "даунлоуд",
            "device": "дивайс",
            "code": "коуд",
            "improve": "импрув",
            "engineering": "энджиниринг",
            "browser": "браузер",
            "security": "секьюрити",
            "mobile": "мобайл",
            "archives": "аркайвз",
            "windows": "виндоус",
            "server": "сервер",
            "network": "нетворк",
            "review": "ривью",
        }

        for word, expected in pronunciations.items():
            with self.subTest(word=word):
                self.assertEqual(
                    apply_latinization(word, backend="dictionary"),
                    expected,
                )

    def test_dictionary_latinization_rewrites_all_ascii_letters_in_long_english_text(self):
        text = (
            "Windows Server updates improve browser security, download archives, "
            "and home page access for mobile devices. Creative teams write code, "
            "share knowledge, monitor metrics, and support online services for "
            "global users."
        )

        result = apply_latinization(text, backend="dictionary")

        self.assertNotEqual(result, text)
        self.assertNotRegex(result, r"[A-Za-z]")

    def test_latinization_leaves_no_ascii_letter_for_any_grapheme(self):
        # The rule file ends with a last-resort layer that maps every ASCII
        # letter, but "q" was missing from it, so any token eng_to_ipa could
        # not resolve leaked a raw Latin "q" ("PostgreSQL" -> "постгрэсqл").
        # Checking the invariant against a prose corpus cannot catch that: the
        # paragraph simply never contained the missing letter. Drive every
        # letter through the fallback explicitly instead.
        letters = string.ascii_lowercase
        probes = [
            template.format(letter=letter)
            for letter in letters
            # Nonsense tokens so eng_to_ipa misses and the .dic fallback runs.
            for template in ("{letter}", "{letter}{letter}{letter}", "zz{letter}xq")
        ]
        probes += ["PostgreSQL", "SQL", "QR", "FAQ", "Qwerty", "Iraq", "quiz"]

        for backend in ("ipa", "dictionary"):
            for probe in probes:
                with self.subTest(backend=backend, probe=probe):
                    result = apply_latinization(probe, backend=backend)
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

    def test_preposition_case_does_not_cross_a_verb(self):
        tokens = simple_tokenize("из-за которой упустили 150 тысяч долларов")
        # The numeral is the direct object of "упустили", so the accusative is
        # correct; what must never happen is inheriting the genitive of "из-за"
        # from behind the verb. For an ending other than 1 the accusative and
        # the nominative render identically, which the assertion below pins.
        self.assertEqual(get_numeral_case(tokens, tokens.index("150")), "accs")
        self.assertEqual(
            normalize("из-за которой упустили 150 тысяч долларов."),
            "из-за которой упустили сто пятьдесят тысяч долларов.",
        )

    def test_quantity_governing_noun_requests_genitive(self):
        tokens = simple_tokenize("огорчение от потери 100 долларов")
        self.assertEqual(get_numeral_case(tokens, tokens.index("100")), "gent")
        self.assertEqual(
            normalize("огорчение от потери 100 долларов"),
            "огорчение от потери ста долларов",
        )

    def test_unrelated_genitive_noun_does_not_govern_measurement(self):
        self.assertEqual(
            normalize("рост человека 180 см"),
            "рост человека сто восемьдесят сантиметров",
        )

    def test_comparative_quantifiers_use_genitive_case(self):
        for marker in self.COMPARATIVE_GENITIVE_MARKERS:
            with self.subTest(marker=marker):
                tokens = simple_tokenize(f"скорость {marker} 8 км/ч")
                self.assertEqual(get_numeral_case(tokens, tokens.index("8")), "gent")

    def test_number_dense_context_normalization_is_linear_in_token_count(self):
        text = "В 1995 году 125 человек купили 25 книг. " * 100

        with patch.object(
            _helpers,
            "normalize_context_token",
            wraps=_helpers.normalize_context_token,
        ) as normalize_token:
            normalize_cardinal_numerals(text)

        self.assertLess(normalize_token.call_count, 10_000)

    def test_cardinal_stage_only_parses_numeric_token_candidates(self):
        self.assertEqual(
            normalize_cardinal_numerals(
                "Слова не должны попадать в числовой парсер 125 раз подряд."
            ),
            "Слова не должны попадать в числовой парсер сто двадцать пять раз подряд.",
        )

    def test_sentence_caps_normalization_uses_one_batched_substitution(self):
        self.assertEqual(
            normalize("первая. вторая\nтретья. четвёртая"),
            "первая. Вторая третья. Четвёртая",
        )

    def test_rendered_numeral_forms_are_cached(self):
        _helpers.inflect_numeral_string.cache_clear()
        try:
            first = _helpers.inflect_numeral_string("125", "nomn", "masc")
            second = _helpers.inflect_numeral_string("125", "nomn", "masc")

            self.assertEqual(first, second)
            self.assertEqual(_helpers.inflect_numeral_string.cache_info().hits, 1)
        finally:
            _helpers.inflect_numeral_string.cache_clear()

    def test_typed_gender_grammeme_does_not_poison_numeral_cache(self):
        typed_gender = _helpers.parse_word("долларов")[0].tag.gender
        self.assertIsNot(type(typed_gender), str)

        _helpers.inflect_numeral_string.cache_clear()
        try:
            self.assertEqual(
                _helpers.inflect_numeral_string("100", "gent", typed_gender),
                "ста",
            )
            self.assertEqual(
                _helpers.inflect_numeral_string("100", "gent", "masc"),
                "ста",
            )
            self.assertEqual(_helpers.inflect_numeral_string.cache_info().hits, 1)
        finally:
            _helpers.inflect_numeral_string.cache_clear()

    def test_accusative_animacy_is_explicit_for_gendered_cardinals(self):
        self.assertEqual(
            _helpers.inflect_numeral_string("1", "accs", "masc", False), "один"
        )
        self.assertEqual(
            _helpers.inflect_numeral_string("1", "accs", "masc", True), "одного"
        )

    def test_numeral_output_is_independent_of_prior_normalization(self):
        paragraph = (
            "Он утверждал, что подарок в 10 дукатов обладает той же полезностью для "
            "человека, уже имеющего 100 дукатов. Если функция точна, одна и та же "
            "психологическая дистанция отделяет 100 тысяч долларов от 1 миллиона, "
            "а 10 миллионов — от 100 миллионов долларов."
        )
        tail = paragraph.split(". ", 1)[1]

        _helpers.inflect_numeral_string.cache_clear()
        try:
            paragraph_first = normalize(paragraph)
            _helpers.inflect_numeral_string.cache_clear()
            normalize(tail)
            tail_first = normalize(paragraph)
        finally:
            _helpers.inflect_numeral_string.cache_clear()

        self.assertEqual(paragraph_first, tail_first)
        self.assertIn("от ста миллионов долларов", paragraph_first)

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

    def test_dictionary_latinization_keeps_productive_and_lexical_rules_working(self):
        options = NormalizeOptions(enable_latinization=True, latinization_backend="dictionary")

        self.assertEqual(
            apply_latinization("engineering", backend="dictionary"),
            "энджиниринг",
        )
        self.assertEqual(
            apply_latinization("school", backend="dictionary"),
            "скул",
        )
        self.assertEqual(
            apply_latinization("server", backend="dictionary"),
            "сервер",
        )
        self.assertEqual(normalize("engineering", options), "энджиниринг")

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

        result = apply_latinization(text, backend="dictionary")

        self.assertEqual(
            result,
            "Сегодня виндоус сервер обновил браузер секьюрити, а сапорт тим "
            "ривью логс и пишет стейбл коуд для римоут платформ.",
        )
        self.assertNotRegex(result, r"[A-Za-z]")
        self.assertIn("Сегодня", result)
        self.assertIn("обновил", result)
        self.assertIn("для", result)

    def test_ipa_latinization_falls_back_to_bundled_dictionary_when_requested_file_is_missing(self):
        self.assertEqual(
            apply_latinization(
                "Beobachtung",
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

    def test_ipa_latinization_batches_large_eng_to_ipa_lookups(self):
        _clear_latinization_word_caches()
        words = [self._alpha_word(index) for index in range(1700)]
        calls: list[list[str]] = []

        def fake_ipa_list(
            words_in, keep_punct=True, stress_marks="both", db_type="sql"
        ):
            del keep_punct, stress_marks, db_type
            chunk = list(words_in)
            calls.append(chunk)
            return [["ˈmɪstəri"] for _ in chunk]

        with patch("eng_to_ipa.ipa_list", side_effect=fake_ipa_list):
            result = apply_latinization(
                " ".join(words),
                backend="ipa",
            )
            repeated_result = apply_latinization(
                " ".join(words),
                backend="ipa",
            )

        self.assertEqual(len(calls), 3)
        self.assertTrue(all(len(chunk) <= 800 for chunk in calls))
        self.assertEqual(repeated_result, result)
        self.assertEqual(len(result.split()), len(words))
        self.assertNotRegex(result, r"[A-Za-z]")

    def test_ipa_batch_handles_every_backend_result_shape(self):
        with patch(
            "eng_to_ipa.ipa_list",
            return_value=[
                "direct-result",
                ["first-variant", "preferred-variant"],
                [],
            ],
        ):
            result = _ipa_convert_batch(("direct", "variants", "missing"))

        self.assertEqual(result, ("direct-result", "preferred-variant", ""))

    def test_ipa_single_lookup_handles_every_backend_result_shape(self):
        cases = (
            ("direct-result", "direct-result"),
            (["first-variant", "preferred-variant"], "preferred-variant"),
            ([], ""),
        )
        self.addCleanup(_clear_latinization_word_caches)
        for backend_result, expected in cases:
            with self.subTest(backend_result=backend_result):
                _clear_latinization_word_caches()
                with patch("eng_to_ipa.convert", return_value=backend_result):
                    result = _ipa_convert_words(("word",))

                self.assertEqual(result, {"word": expected})

    def test_ipa_empty_input_skips_backend_calls(self):
        _clear_latinization_word_caches()
        with (
            patch("eng_to_ipa.ipa_list") as ipa_list,
            patch("eng_to_ipa.convert") as convert,
        ):
            self.assertEqual(_ipa_convert_batch(()), ())
            self.assertEqual(_ipa_convert_words(()), {})

        ipa_list.assert_not_called()
        convert.assert_not_called()

    def test_unknown_latin_fallback_batches_dictionary_rewrite_for_many_words(self):
        _clear_latinization_word_caches()
        words = tuple(self._alpha_word(index) for index in range(12))
        calls: list[str] = []

        def fake_apply(text: str, dictionaries_path: Path, filename: str) -> str:
            del dictionaries_path, filename
            calls.append(text)
            return "\n".join(
                line if line.endswith("_ru") else f"{line}_ru"
                for line in text.split("\n")
            )

        with patch(
            "ru_normalizr.latinization._apply_dictionary_latinization",
            side_effect=fake_apply,
        ):
            result = _resolve_unknown_latin_fallbacks(
                words,
                "C:/tmp",
                "latinization.dic",
            )
            repeated_result = _resolve_unknown_latin_fallbacks(
                words,
                "C:/tmp",
                "latinization.dic",
            )

        self.assertEqual(
            result,
            {word: f"{word}_ru" for word in words},
        )
        self.assertEqual(len(calls), 2)
        self.assertIn("\n", calls[0])
        self.assertEqual(repeated_result, result)

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

    def test_dictionary_regex_rules_store_required_literal_hints(self):
        with TemporaryDirectory() as tmp_dir:
            dic_path = Path(tmp_dir) / "rules.dic"
            dic_path.write_text(
                "*needle*=игла\n*definitely-absent*=нет\n",
                encoding="utf-8",
            )
            normalizer = DictionaryNormalizer(dictionaries_path=tmp_dir)

            regex_chunks = [
                chunk
                for file_type, chunks in normalizer._runtime_file_rules
                if file_type == "dic"
                for chunk_type, chunk in chunks
                if chunk_type == "regex"
            ]

            self.assertTrue(regex_chunks)
            self.assertTrue(
                all(rule[2] for chunk in regex_chunks for rule in chunk)
            )
            self.assertEqual(normalizer.apply("a needle appears"), "a игла appears")

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


#: Регрессии, пришедшие из отчётов пользователей: каждая проверка — полная
#: фраза, потому что дефект был замечен именно на ней.
class RuNormalizrReportedRegressionTests(unittest.TestCase):
    def test_equals_blocks_case_leak_onto_arithmetic_result(self):
        # The decimal multiplier after "×" must stay nominative itself and must
        # not leak its case onto the "= 73 ₽" result. Assert full strings so a
        # regression in either the fraction ("две десятых" vs "двух десятых")
        # or the result ("рубля" vs "рублей") is caught.
        cases = {
            "9 × 11 = 73 ₽": "девять умножить на одиннадцать равно семьдесят три рубля",
            "9 × 11.01 = 73 ₽": (
                "девять умножить на одиннадцать целых одна сотая "
                "равно семьдесят три рубля"
            ),
            "9 × 11.1 = 73 ₽": (
                "девять умножить на одиннадцать целых одна десятая "
                "равно семьдесят три рубля"
            ),
            "9 × 11.0 = 73 ₽": (
                "девять умножить на одиннадцать целых ноль десятых "
                "равно семьдесят три рубля"
            ),
            "9 × 11.2 = 73 ₽": (
                "девять умножить на одиннадцать целых две десятых "
                "равно семьдесят три рубля"
            ),
            "9 × 11.02 = 73 ₽": (
                "девять умножить на одиннадцать целых две сотых "
                "равно семьдесят три рубля"
            ),
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(normalize(expression), expected)

        self.assertEqual(normalize("не более 73 рублей"), "не более семидесяти трёх рублей")

    def test_copyright_symbol_does_not_create_sentence_dot(self):
        self.assertEqual(normalize("© 2024 Компания"), "две тысячи двадцать четыре Компания")
        self.assertEqual(normalize("Текст © автора"), "Текст автора")

    def test_abbreviated_chapter_number_is_inflected_before_abbreviation_stage(self):
        self.assertEqual(
            normalize("См. гл. 5 и рис. 3."),
            "смотри главу пятую и рисунок три.",
        )
        self.assertEqual(normalize("гл. без номера"), "глава без номера")

    def test_contextual_abbreviation_uses_governing_case_for_ambiguous_head(self):
        self.assertEqual(
            normalize("Восстановили гос. пути сообщения."),
            "Восстановили государственные пути сообщения.",
        )

    def test_contextual_abbreviation_ignores_adverb_homonyms_in_case_context(self):
        cases = (
            (
                "Избегали порой гос. пути сообщения.",
                "Избегали порой государственного пути сообщения.",
            ),
            (
                "Восстановили часто гос. пути сообщения.",
                "Восстановили часто государственные пути сообщения.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(normalize(source), expected)

    def test_mixed_case_cyrillic_units_are_reachable(self):
        self.assertIn("градусов Цельсия", normalize("Температура 25 °С сегодня."))
        self.assertEqual(normalize("Ток 5 мА в цепи."), "Ток пять миллиампер в цепи.")
        self.assertEqual(
            normalize("Батарея на 3000 мАч."),
            "Батарея на три тысячи миллиампер-часов.",
        )

    def test_lowercase_words_do_not_become_case_sensitive_units(self):
        self.assertEqual(normalize("Пришли 5 ма."), "Пришли пять ма.")
        self.assertEqual(normalize("Назвали 5 ка."), "Назвали пять ка.")

    def test_case_insensitive_unit_table_keys_are_lowercase(self):
        self.assertTrue(all(key == key.lower() for key in _constants.UNITS_DATA))

    def test_year_and_gram_abbreviations_keep_sentence_terminal_dots(self):
        self.assertIn(
            "году. Потом",
            normalize("Он родился в 1672 г. Потом вырос.", NormalizeOptions.safe()),
        )
        self.assertTrue(
            normalize("Он родился в 1672 г.", NormalizeOptions.safe()).endswith("году.")
        )
        self.assertIn(
            "грамм. Далее",
            normalize("Вес 5 г. Далее текст.", NormalizeOptions.safe()),
        )

    def test_year_abbreviation_dot_remains_nonterminal_mid_sentence(self):
        result = normalize("Это случилось в 1990 г. в Москве.", NormalizeOptions.safe())

        self.assertIn("году в Москве", result)
        self.assertNotIn("году. В Москве", result)

    def test_stressed_year_word_is_inflected_as_one_word(self):
        cases = (
            (
                "Между 1999 и 2000 года́ми разница велика.",
                "Между тысяча девятьсот девяносто девятым и двухтысячным годами разница велика.",
            ),
            (
                "Период между 2020 и 2025 года́ми оказался насыщенным.",
                "Период между две тысячи двадцатым и две тысячи двадцать пятым "
                "годами оказался насыщенным.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(normalize(source), expected)

    def test_years_ago_expansion_does_not_destroy_person_initials(self):
        safe = NormalizeOptions.safe()

        self.assertNotIn("лет назад", normalize("Л. Н. Толстой родился в 1828 году.", safe))
        self.assertNotIn("лет назад", normalize("Роман написал Л.Н. Толстой.", safe))
        self.assertNotIn("лет назад", normalize("л. н. Толстой", safe))
        self.assertIn(
            "пять миллионов лет назад",
            normalize("Это было 5 млн л. н. примерно.", safe),
        )

    def test_years_ago_expansion_can_be_disabled(self):
        options = NormalizeOptions.safe(enable_years_ago_expansion=False)

        self.assertNotIn("лет назад", normalize("Это было 5 млн л. н. примерно.", options))

    def test_tts_person_initials_are_not_rewritten_as_years_ago(self):
        result = normalize("Л. Н. Толстой", NormalizeOptions.tts())

        self.assertNotIn("лет назад", result)
        self.assertIn("Толстой", result)

    def test_tts_initials_after_role_title_do_not_insert_dot_before_surname(self):
        self.assertEqual(
            normalize("Редактор Е. Харитонова", NormalizeOptions.tts()),
            "Редактор ее Харитонова.",
        )
        self.assertEqual(
            normalize(
                "Редактор Е. Харитонова\n\nКорректор Е. Харитонова",
                NormalizeOptions.tts(),
            ),
            "Редактор ее Харитонова.\n\nКорректор ее Харитонова.",
        )

    def test_tts_single_initials_add_surname_first_speech_pauses(self):
        self.assertEqual(
            normalize(
                "американский сейсмолог Ч. Рихтер для определения",
                NormalizeOptions.tts(),
            ),
            "американский сейсмолог чэ Рихтер для определения",
        )

    def test_tts_single_initial_lists_keep_commas_and_double_vowel_initials(self):
        self.assertEqual(
            normalize(
                "В АПРЕЛЕ 1982 ГОДА были арестованы «молодые социалисты» Б. Кагарлицкий[10], П. Кудюкин, А. Фадин, Ю. Хавкин, В. Чернецкий, А. Шилков, а позже – М. Ривкин.",
                NormalizeOptions.tts(),
            ),
            'В АПРЕЛЕ тысяча девятьсот восемьдесят второго ГОДА были арестованы "молодые социалисты" бэ Кагарлицкий, пэ Кудюкин, аа Фадин, юю Хавкин, вэ Чернецкий, аа Шилков, а позже — эм Ривкин.',
        )

    def test_tts_initials_before_quoted_title_do_not_inject_sentence_dot(self):
        self.assertEqual(
            normalize(
                'О книге Л. Мизеса "Либерализм в классической традиции".',
                NormalizeOptions.tts(),
            ),
            'О книге эл Мизеса "Либерализм в классической традиции".',
        )

    def test_tts_initials_do_not_duplicate_following_clause_punctuation(self):
        cases = (
            (
                "Отчёт сдал Иванов А. Б.; проверил Петров.",
                "Отчёт сдал Иванов, аа, бэ; проверил Петров.",
            ),
            (
                "Акт подписал Иванов А. Б.: копия у Петрова.",
                "Акт подписал Иванов, аа, бэ: копия у Петрова.",
            ),
            (
                "Список: Иванов А. Б. — далее по тексту.",
                "Список: Иванов, аа, бэ — далее по тексту.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(normalize(source, NormalizeOptions.tts()), expected)

    def test_normalize_keeps_exact_todo_examples_stable(self):
        self.assertEqual(
            normalize(
                "ШКАЛА ЧИСЛОВАЯ СИЛЫ ЗЕМЛЕТРЯСЕНИЙ, разработал американский сейсмолог Ч. Рихтер для определения силы подземного толчка, вызывающего землетрясение. Шкала содержит условные единицы (от 1 до 9) – магнитуды, которые вычисляются по десятичным логарифмам. В ее основе лежит логарифм максимальной амплитуды записанной ударной волны и расстояние от эпицентра."
            ),
            "ШКАЛА ЧИСЛОВАЯ СИЛЫ ЗЕМЛЕТРЯСЕНИЙ, разработал американский сейсмолог Ч. Рихтер для определения силы подземного толчка, вызывающего землетрясение. Шкала содержит условные единицы (от одного до девяти) — магнитуды, которые вычисляются по десятичным логарифмам. В ее основе лежит логарифм максимальной амплитуды записанной ударной волны и расстояние от эпицентра.",
        )
        self.assertEqual(
            normalize("Фри́дрих А́вгуст фон Ха́йек."),
            "Фр+идрих +Август фон Х+айек.",
        )
        self.assertEqual(
            normalize(
                "Такие меры приносят голоса избирателей, но, с точки зрения многих бизнесменов, было бы куда лучше, если бы правительство оставило все деньги им. Они откроют новые заводы, и безработным найдется занятие."
            ),
            "Такие меры приносят голоса избирателей, но, с точки зрения многих бизнесменов, было бы куда лучше, если бы правительство оставило все деньги им. Они откроют новые заводы, и безработным найдется занятие.",
        )

    def test_normalize_preserves_zero_width_stress_garbage(self):
        self.assertEqual(
            normalize("Фри\u200cдрих А\u200cвгуст фон Ха\u200cйек."),
            "Фридрих Август фон Хайек.",
        )

    def test_normalize_fixes_reported_numeric_unit_range(self):
        self.assertEqual(
            normalize("Предполагается, что идеальные сферы диаметром 2-6 футов"),
            "Предполагается, что идеальные сферы диаметром два — шесть футов",
        )
        self.assertEqual(
            normalize("мозг объемом 1200-1400 кубических сантиметров"),
            "мозг объемом одна тысяча двести — одна тысяча четыреста кубических сантиметров",
        )

    def test_normalize_expands_page_reference_before_numeric_range(self):
        self.assertEqual(
            normalize("радиационные пояса [Земля и Вселенная, 1980, N2, с.22-25]"),
            "радиационные пояса (Земля и Вселенная, одна тысяча девятьсот восемьдесят, N два, страницы двадцать два — двадцать пять)",
        )

    def test_normalize_fixes_bce_and_ce_year_phrases(self):
        self.assertEqual(
            normalize(
                "Согласно буддистской традиции, Гаутама, родившийся около 500 года до н. э., был принцем небольшого гималайского королевства."
            ),
            "Согласно буддистской традиции, Гаутама, родившийся около пятисотого года до нашей эры, был принцем небольшого гималайского королевства.",
        )
        self.assertEqual(
            normalize("Натуфийская культура(12500-9500 до н.э.)."),
            "Натуфийская культура (двенадцать тысяч пятисотый — девять тысяч пятисотый год до нашей эры).",
        )
        self.assertEqual(
            normalize("Натуфийская культура (12500–9500 до н. э.)."),
            "Натуфийская культура (двенадцать тысяч пятисотый — девять тысяч пятисотый год до нашей эры).",
        )
        self.assertEqual(
            normalize("Натуфийская культура (12500 — 9500 до н. э.)."),
            "Натуфийская культура (двенадцать тысяч пятисотый — девять тысяч пятисотый год до нашей эры).",
        )
        self.assertEqual(
            normalize("Натуфийская культура (12500-9500 до нашей эры)."),
            "Натуфийская культура (двенадцать тысяч пятисотый — девять тысяч пятисотый год до нашей эры).",
        )
        self.assertEqual(
            normalize("Период с 12500 по 9500 до н. э."),
            "Период с двенадцати тысяч пятисотого по девять тысяч пятисотый год до нашей эры.",
        )
        self.assertEqual(
            normalize("Период от 500 до 400 BCE."),
            "Период от пятисотого до четырёхсотого года до нашей эры.",
        )
        self.assertEqual(
            normalize("Около 500 CE."),
            "Около пятисотого года нашей эры.",
        )
        self.assertEqual(
            normalize("Около 500 A.D."),
            "Около пятисотого года нашей эры.",
        )
        self.assertEqual(
            normalize(
                "(ок. 120 до н. э.), Галлию ради безопасности Прованса (ок. 50 до н. э.) и Британию ради безопасности Галлии (ок. 50 н. э.)."
            ),
            "(около сто двадцатого года до нашей эры), Галлию ради безопасности Прованса (около пятидесятого года до нашей эры) и Британию ради безопасности Галлии (около пятидесятого года нашей эры).",
        )

    def test_normalize_fixes_parenthesized_years_and_regnal_names(self):
        self.assertEqual(
            normalize(
                "Наполеоновская военная машина, сокрушившая армии всей Европы под Аустерлицем (1805), была вооружена примерно так же, как армия казненного Людовика XVI."
            ),
            "Наполеоновская военная машина, сокрушившая армии всей Европы под Аустерлицем (тысяча восемьсот пятый), была вооружена примерно так же, как армия казненного Людовика шестнадцатого.",
        )

    def test_normalize_fixes_century_ranges(self):
        self.assertEqual(
            normalize("С XVI по XVIII век цинга унесла жизни примерно двух миллионов моряков."),
            "С шестнадцатого по восемнадцатый век цинга унесла жизни примерно двух миллионов моряков.",
        )
        self.assertEqual(
            normalize("С XVI по XVIII в. цинга унесла жизни примерно двух миллионов моряков."),
            "С шестнадцатого по восемнадцатый век цинга унесла жизни примерно двух миллионов моряков.",
        )
        self.assertEqual(
            normalize("С XVI по XIX век из Африки в Америку завезли примерно десять миллионов рабов."),
            "С шестнадцатого по девятнадцатый век из Африки в Америку завезли примерно десять миллионов рабов.",
        )
        self.assertEqual(
            normalize("За XV и XVI века европейцы успели проплыть вокруг Африки."),
            "За пятнадцатый и шестнадцатый века европейцы успели проплыть вокруг Африки.",
        )
        self.assertEqual(
            normalize("К XV и XVI векам сложились новые маршруты."),
            "К пятнадцатому и шестнадцатому векам сложились новые маршруты.",
        )
        self.assertEqual(
            normalize(
                "Страшную память оставили по себе религиозные войны между католиками и протестантами, опустошавшие Европу в XVI и XVII веках."
            ),
            "Страшную память оставили по себе религиозные войны между католиками и протестантами, опустошавшие Европу в шестнадцатом и семнадцатом веках.",
        )
        self.assertEqual(
            normalize("В XV в. начались перемены."),
            "В пятнадцатом веке начались перемены.",
        )
        self.assertEqual(
            normalize("За XV в. многое изменилось."),
            "За пятнадцатый век многое изменилось.",
        )
        self.assertEqual(
            normalize("О XV в. часто спорят историки."),
            "О пятнадцатом веке часто спорят историки.",
        )
        self.assertEqual(
            normalize("К XV в. сложились новые маршруты."),
            "К пятнадцатому веку сложились новые маршруты.",
        )
        self.assertEqual(
            normalize("Между XV и XVI веками усилилась морская конкуренция."),
            "Между пятнадцатым и шестнадцатым веками усилилась морская конкуренция.",
        )
        self.assertEqual(
            normalize("О XV и XVI веках часто спорят историки."),
            "О пятнадцатом и шестнадцатом веках часто спорят историки.",
        )
        self.assertEqual(
            normalize(
                "В III-IV веках н.э. манихейство распространялось со скоростью лесного пожара от Китая до Северной Африки и в какой-то момент даже соперничало с христианством за популярность в Римской империи."
            ),
            "В третьем — четвёртом веках нашей эры манихейство распространялось со скоростью лесного пожара от Китая до Северной Африки и в какой-то момент даже соперничало с христианством за популярность в Римской империи.",
        )
        self.assertEqual(
            normalize(
                "В XVII-XVIII веках связь крепла, но неразрывный узел завязался лишь в XIX столетии."
            ),
            "В семнадцатом — восемнадцатом веках связь крепла, но неразрывный узел завязался лишь в девятнадцатом столетии.",
        )
        self.assertEqual(
            normalize(
                "Неудивительно, что наука и капитализм стали главным наследием, которое европейский империализм передал постевропейскому миру XXI века."
            ),
            "Неудивительно, что наука и капитализм стали главным наследием, которое европейский империализм передал постевропейскому миру двадцать первого века.",
        )
        self.assertEqual(
            normalize(
                "Джеймс Кук был не первым исследователем такого склада. Схожим образом мыслили испанские и португальские моряки XV-XVI веков."
            ),
            "Джеймс Кук был не первым исследователем такого склада. Схожим образом мыслили испанские и португальские моряки пятнадцатого — шестнадцатого веков.",
        )
        self.assertEqual(
            normalize("Моряки XV и XVI веков хорошо знали маршруты."),
            "Моряки пятнадцатого и шестнадцатого веков хорошо знали маршруты.",
        )
        self.assertEqual(
            normalize("От XVI до XVIII в. менялись маршруты."),
            "От шестнадцатого до восемнадцатого века менялись маршруты.",
        )
        self.assertEqual(
            normalize("В XV-XVI вв. менялись маршруты."),
            "В пятнадцатом — шестнадцатом веках менялись маршруты.",
        )
        self.assertEqual(
            normalize("XV и XVI вв."),
            "пятнадцатый и шестнадцатый века",
        )
        self.assertEqual(
            normalize("XV-XVI вв."),
            "пятнадцатый — шестнадцатый века",
        )
        self.assertEqual(
            normalize("С XVI по XVIII вв. менялись маршруты."),
            "С шестнадцатого по восемнадцатый век менялись маршруты.",
        )
        self.assertEqual(
            normalize("От XVI до XVIII вв. менялись маршруты."),
            "От шестнадцатого до восемнадцатого века менялись маршруты.",
        )

    def test_normalize_reads_quarter_abbreviations_in_context(self):
        self.assertEqual(
            normalize("В IV кв. выросла выручка."),
            "В четвёртом квартале выросла выручка.",
        )
        self.assertEqual(
            normalize("О IV кв. говорили долго."),
            "О четвёртом квартале говорили долго.",
        )
        self.assertEqual(
            normalize("К IV кв. подготовят отчет."),
            "К четвёртому кварталу подготовят отчет.",
        )

    def test_normalize_fixes_millennium_and_era_years(self):
        self.assertEqual(
            normalize(
                "Ее расцвет пришелся на III тысячелетие до н. э., а около 1900 года до н. э. эта цивилизация погибла."
            ),
            "Ее расцвет пришелся на третье тысячелетие до нашей эры, а около тысяча девятисотого года до нашей эры эта цивилизация погибла.",
        )
        self.assertEqual(
            normalize(
                "В V и IV тысячелетиях до н. э. в Плодородном полумесяце один за другим возникают города."
            ),
            "В пятом и четвёртом тысячелетиях до нашей эры в Плодородном полумесяце один за другим возникают города.",
        )
        self.assertEqual(
            normalize("В V и IV веках до н. э. такие случаи были редки."),
            "В пятом и четвёртом веках до нашей эры такие случаи были редки.",
        )
        self.assertEqual(
            normalize(
                "В V и IV тысячелетиях до н.э. в Плодородном полумесяце{5} один за другим возникают города с десятками тысяч жителей.",
                NormalizeOptions.tts(),
            ),
            "В пятом и четвёртом тысячелетиях до нашей эры в Плодородном полумесяце один за другим возникают города с десятками тысяч жителей.",
        )

    def test_normalize_fixes_suffixed_era_year_and_keeps_terminal_dot(self):
        self.assertEqual(
            normalize(
                "Монументальная Бехистунская надпись высотой 15 метров и 25 метров шириной была выбита в скале по приказу царя Дария I примерно в 500-м году до н. э."
            ),
            "Монументальная Бехистунская надпись высотой пятнадцать метров и двадцать пять метров шириной была выбита в скале по приказу царя Дария первого примерно в пятисотом году до нашей эры.",
        )
        self.assertEqual(
            normalize("Перенеситесь мысленно в 1776 год до н. э."),
            "Перенеситесь мысленно в тысяча семьсот семьдесят шестой год до нашей эры.",
        )

    def test_normalize_keeps_plain_cardinal_limit_after_do(self):
        self.assertEqual(
            normalize("Цена одной акции упала с 10 000 ливров до 1000"),
            "Цена одной акции упала с десяти тысяч ливров до одной тысячи",
        )

    def test_normalize_supports_dotted_clock_times(self):
        self.assertEqual(
            normalize(
                "В 8.00 утром 26 сентября 1943 года сотни вспышек озарили горизонт."
            ),
            "В восемь, ноль ноль утром двадцать шестого сентября тысяча девятьсот сорок третьего года сотни вспышек озарили горизонт.",
        )

    def test_normalize_dotted_clock_times_do_not_hijack_plain_decimals(self):
        self.assertEqual(
            normalize("Цена: 3.50 руб."),
            "Цена: три рубля пятьдесят копеек.",
        )
        self.assertEqual(
            normalize("масса 2.15 кг"),
            "масса две целых пятнадцать сотых килограмма",
        )

    def test_normalize_keeps_era_terminal_punctuation_only_when_present(self):
        self.assertEqual(
            normalize("около 50 н. э"),
            "около пятидесятого года нашей эры",
        )
        self.assertEqual(
            normalize("около 50 н. э."),
            "около пятидесятого года нашей эры.",
        )
        self.assertEqual(
            normalize("Инцидент случился около 50 н. э. Никто не пострадал."),
            "Инцидент случился около пятидесятого года нашей эры. Никто не пострадал.",
        )

    def test_normalize_keeps_military_ordinals_out_of_year_rules(self):
        self.assertEqual(
            normalize(
                "В 3-й горнострелковой дивизии подобный стиль руководства был частью ее боевого характера."
            ),
            "В третьей горнострелковой дивизии подобный стиль руководства был частью ее боевого характера.",
        )

    def test_normalize_keeps_inanimate_accusative_ordinals_non_animate(self):
        self.assertEqual(
            normalize("За весь XX век этот уровень не превысил 5% — в самом кровавом веке,"),
            "За весь двадцатый век этот уровень не превысил пять процентов — в самом кровавом веке,",
        )
        self.assertEqual(
            normalize("Он видел 3-й фильм подряд."),
            "Он видел третий фильм подряд.",
        )

    def test_normalize_reads_left_shared_heading_series(self):
        self.assertEqual(
            normalize("Главы IV и V были переработаны."),
            "Четвёртая и пятая главы были переработаны.",
        )
        self.assertEqual(
            normalize("В главах IV и V описаны реформы."),
            "В четвёртой и пятой главах описаны реформы.",
        )
        self.assertEqual(
            normalize("Из глав IV и V убрали примечания."),
            "Из четвёртой и пятой глав убрали примечания.",
        )
        self.assertEqual(
            normalize("Разделы IV и V содержат примеры."),
            "Четвёртый и пятый разделы содержат примеры.",
        )
        self.assertEqual(
            normalize("В разделах IV и V приведены примеры."),
            "В четвёртом и пятом разделах приведены примеры.",
        )
        self.assertEqual(
            normalize("Из разделов IV и V убрали повторы."),
            "Из четвёртого и пятого разделов убрали повторы.",
        )
        self.assertEqual(
            normalize("Главы IV-V были переработаны."),
            "Четвёртая — пятая главы были переработаны.",
        )
        self.assertEqual(
            normalize("В главах IV-V описаны реформы."),
            "В четвёртой — пятой главах описаны реформы.",
        )
        self.assertEqual(
            normalize("Из разделов IV-V убрали повторы."),
            "Из четвёртого — пятого разделов убрали повторы.",
        )
        self.assertEqual(
            normalize("Главы IV, V и VI были переработаны."),
            "Четвёртая, пятая и шестая главы были переработаны.",
        )

    def test_normalize_fixes_reported_people_and_long_decimal_denominators(self):
        self.assertEqual(
            normalize("89 человек."),
            "восемьдесят девять человек.",
        )
        self.assertEqual(
            normalize("699 человек... 89 человек... 56 людей..."),
            "шестьсот девяносто девять человек восемьдесят девять человек пятьдесят шесть людей...",
        )
        self.assertEqual(
            normalize("0,000000003."),
            "ноль целых три миллиардных.",
        )
        self.assertEqual(
            normalize("0,000000000003"),
            "ноль целых три триллионных",
        )
        self.assertEqual(
            normalize("4,771455068077"),
            "четыре целых семьсот семьдесят один миллиард четыреста пятьдесят пять миллионов шестьдесят восемь тысяч семьдесят семь триллионных",
        )
        self.assertEqual(
            normalize("4,771068077."),
            "четыре целых семьсот семьдесят один миллион шестьдесят восемь тысяч семьдесят семь миллиардных.",
        )

    def test_normalize_fixes_reported_year_suffix_and_abbreviation_cases(self):
        self.assertEqual(
            normalize("и теперь мне уже 35,"),
            "и теперь мне уже тридцать пять,",
        )
        self.assertEqual(
            normalize("в 41м году,"),
            "в сорок первом году,",
        )
        self.assertEqual(
            normalize("в 41-ом году,"),
            "в сорок первом году,",
        )
        self.assertEqual(
            normalize("в 21м году, в 41м году, в 22м году."),
            "в двадцать первом году, в сорок первом году, в двадцать втором году.",
        )
        self.assertEqual(
            normalize("21 году. в 21ом году. в 21-ом году."),
            "двадцать первом году. В двадцать первом году. В двадцать первом году.",
        )
        self.assertEqual(
            normalize("в лихие 90-е. в лихие 90-ые."),
            "в лихие девяностые. В лихие девяностые.",
        )
        self.assertEqual(
            normalize("55 г.р. 55 г. р."),
            "пятьдесят пятого года рождения. Пятьдесят пятого года рождения.",
        )
        self.assertEqual(
            normalize("вес 123 г. вес 123г."),
            "вес сто двадцать три грамма вес сто двадцать три грамма.",
        )
        self.assertEqual(
            normalize("масса 237 г. масса 237г."),
            "масса двести тридцать семь грамм масса двести тридцать семь грамм.",
        )

    def test_normalize_fixes_reported_suffix_ordinals_and_compounds(self):
        self.assertEqual(
            normalize("Анне 2-ой. Матильде 4-ой."),
            "Анне второй. Матильде четвёртой.",
        )
        self.assertEqual(
            normalize("на 3е число.. 3ее число.. 3-ее число.."),
            "на третье число. Три число. Три число.",
        )
        self.assertEqual(
            normalize("1-ее число.. 5-ее число.. 1ее число.. 5ее число. .1ое число.. 5-ое число.."),
            "одно число. Пять число. Одно число. Пять число. Первое число. Пятое число.",
        )
        self.assertEqual(
            normalize("6е июля. 6-е июля 6ее июля. 6-ее июля. 6-ое июля"),
            "шестое июля. Шестое июля шесть июля. Шесть июля. Шестое июля",
        )
        self.assertEqual(
            normalize("1ое поколение.. 3ее поколение.. 3му поколению... 1му поколению.."),
            "первое поколение. Три поколение. Третьему поколению... Одному поколению.",
        )
        self.assertEqual(
            normalize("6м номере.. 4му номеру.. 3го номера.. 1й номер.. 21-у тысячу."),
            "шестом номере. Четвёртому номеру. Третьего номера. Первый номер. Двадцать одну тысячу.",
        )
        self.assertEqual(
            normalize("1-ую секунду. 2-ую секунду."),
            "первую секунду. Вторую секунду.",
        )
        self.assertEqual(
            normalize("на 5-ой минуте, шёл 1у минуту, полз 2е минуты"),
            "на пятой минуте, шёл одну минуту, полз вторые минуты",
        )
        self.assertEqual(
            normalize("5я группа. 2е группы.. 7й группе.. 4я серия.. 4 серии.."),
            "пятая группа. Вторые группы. Седьмой группе. Четвёртая серия. Четыре серии.",
        )
        self.assertEqual(
            normalize(
                "1 женщина, 2 женщины, стих об 1-ой женщине, играл с 1-ой женщиной, полюбил 1-ю женщину, цветы 7-и женщинам,"
            ),
            "одна женщина, две женщины, стих об одной женщине, играл с одной женщиной, полюбил первую женщину, цветы семи женщинам,",
        )

    def test_normalize_agrees_cardinals_and_ordinals_with_local_context(self):
        self.assertEqual(normalize("3-я глава"), "третья глава")
        self.assertEqual(normalize("2-я мировая война"), "вторая мировая война")
        self.assertEqual(normalize("с 5 книгами"), "с пятью книгами")
        self.assertEqual(normalize("с 3 друзьями"), "с тремя друзьями")
        self.assertEqual(normalize("перед 8 марта"), "перед восьмым марта")

    def test_normalize_keeps_decimal_nominative_after_attributive_participle(self):
        self.assertEqual(
            normalize("ожидаемый процент составляет 12,5%"),
            "ожидаемый процент составляет двенадцать целых пять десятых процента",
        )
        self.assertEqual(
            normalize("требуемый объём 3,5 литра"),
            "требуемый объём три целых пять десятых литра",
        )

    def test_normalize_preserves_people_lexeme_after_decimal_millions(self):
        self.assertEqual(
            normalize("2,5 млн человек"),
            "два с половиной миллиона человек",
        )

    def test_normalize_reads_common_binary_math_symbols(self):
        cases = {
            "2×3": "два умножить на три",
            "2+3": "два плюс три",
            "5−2": "пять минус два",
            "8÷4": "восемь разделить на четыре",
            "2^3": "два в степени три",
            "2*3": "два умножить на три",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(normalize(source), expected)

    def test_normalize_reads_an_ascii_asterisk_as_multiplication(self):
        # The typographic "×" was spoken but its ASCII stand-in was not, so
        # "10 * 2 = 20" left a bare symbol in the output. Unlike "-" and "/",
        # an asterisk between two digits has no competing meaning, so it needs
        # no equation context.
        self.assertEqual(normalize("10 * 2 = 20"), "десять умножить на два равно двадцать")
        self.assertEqual(normalize("2 * 3"), "два умножить на три")
        self.assertEqual(normalize("2*3*4"), "два умножить на три умножить на четыре")
        # Asterisks that are not an operator keep their previous handling.
        self.assertEqual(normalize("текст * сноска"), "текст * сноска")
        self.assertEqual(normalize("2 звезды * 3"), "две звезды * три")
        self.assertEqual(normalize("сноска 5*"), "сноска пять *")
        # A slash between digits is left alone: it is also a date, a fraction
        # and a unit denominator.
        self.assertEqual(normalize("3/4"), "три четвёртых")
        self.assertEqual(normalize("10 / 2 = 5"), "десять / два равно пять")

    def test_normalize_reads_an_ascii_hyphen_as_minus_inside_an_equation(self):
        # An ASCII "-" between two numbers is a range separator everywhere else,
        # so subtraction between two literals could not be written at all: both
        # "7 - 2 = 5" and "10-5 = 5" read as ranges. An equals sign is what
        # distinguishes the two, and "+" already read correctly.
        self.assertEqual(normalize("7 - 2 = 5"), "семь минус два равно пять")
        self.assertEqual(normalize("10-5 = 5"), "десять минус пять равно пять")
        self.assertEqual(
            normalize("10-5.6 = 4.4"),
            "десять минус пять целых шесть десятых равно четыре целых четыре десятых",
        )
        self.assertEqual(normalize("2 + 3 = 5"), "два плюс три равно пять")
        # Without an equals sign the hyphen stays a range separator.
        self.assertEqual(normalize("10-20"), "десять — двадцать")
        self.assertEqual(normalize("возраст 10-20 лет"), "возраст десять — двадцать лет")
        self.assertEqual(normalize("диапазон 10-20"), "диапазон десять — двадцать")
        # An equals sign elsewhere in the text does not reach across to it: the
        # equation ends at the comma because operands must be joined by an
        # operator.
        self.assertEqual(
            normalize("x = 5, возраст 10-20 лет"),
            "x равно пять, возраст десять — двадцать лет",
        )
        self.assertEqual(
            normalize("формула 2+2=4 и диапазон 5-7"),
            "формула два плюс два равно четыре и диапазон пять — семь",
        )
        # Assigning a range to a variable stays ambiguous and is read as
        # subtraction; nothing structural separates it from "y = 10-5".
        self.assertEqual(normalize("x = 10-20"), "x равно десять минус двадцать")

    def test_normalize_preserves_ellipsis_between_adjacent_numbers(self):
        self.assertIn("…", normalize("1…2"))

    def test_normalize_bibliographic_volume_and_number_abbreviations(self):
        self.assertEqual(
            normalize("в журнале (1984. Т. 34)"),
            "в журнале (одна тысяча девятьсот восемьдесят четыре. Том тридцать четыре)",
        )
        self.assertEqual(normalize("Vol. 34, No. 2"), "том тридцать четыре, номер два")
        self.assertEqual(normalize("P. 5, С. 6"), "страница пять, страница шесть")
        self.assertEqual(normalize("масса 5 т"), "масса пять тонн")

    def test_normalize_fixes_reported_compound_numeric_adjectives_and_regnal_suffixes(self):
        self.assertEqual(
            normalize(
                "30%-ная надбавка, 25%-ный риск, при 10%-ном росте, 99%-ный шанс, 100%-ная гарантия"
            ),
            "тридцатипроцентная надбавка, двадцатипятипроцентный риск, при десятипроцентном росте, девяностодевятипроцентный шанс, стопроцентная гарантия",
        )
        self.assertEqual(normalize("50-летний юбилей"), "пятидесятилетний юбилей")
        self.assertEqual(
            normalize("5и ступенчатая. 2х местный. 5и местный. 1ым номером."),
            "пятиступенчатая. Двухместный. Пятиместный. Первым номером.",
        )
        self.assertEqual(
            normalize(
                "квартира 1-комнатная. 1-комнатную квартиру. 1-комнатной. обменял на 1-комнатную."
            ),
            "квартира однокомнатная. Однокомнатную квартиру. Однокомнатной. Обменял на однокомнатную.",
        )
        self.assertEqual(
            normalize("1-ю тонну. 2-ю тонну. 5-ю тонну. 1-тонный, 2х тонный"),
            "первую тонну. Вторую тонну. Пятую тонну. Однотонный, двухтонный",
        )
        self.assertEqual(
            normalize("Пётр 1-ый. Изабелла 3-я. Матильда II-я."),
            "Пётр первый. Изабелла третья. Матильда вторая.",
        )
        self.assertEqual(
            normalize("Дональда VII-го. Альбрехта IV-го. Елизаветы 3-ее. Елизаветы 3-й."),
            "Дональда седьмого. Альбрехта четвёртого. Елизаветы трёх. Елизаветы третьей.",
        )
        self.assertEqual(
            normalize("Ивану 3-му. Вильгельму XIV-му. Екатерину 2-ю."),
            "Ивану третьему. Вильгельму четырнадцатому. Екатерину вторую.",
        )

    def test_hyphen_before_decimal_is_not_read_as_minus(self):
        # "GLM-5.2": the hyphen joins a model name to its version, so it must
        # never be consumed into "минус". The version stage then reads the
        # dotted part component by component, see the dedicated test below.
        self.assertEqual(normalize("GLM-5"), "GLM-пять")
        self.assertEqual(normalize("GLM-5.2"), "GLM пять точка два")
        self.assertEqual(normalize("ГЛМ-5.2"), "ГЛМ пять точка два")
        self.assertEqual(
            normalize("модель-3.5 работает"),
            "модель три точка пять работает",
        )
        self.assertEqual(
            normalize("GLM-5.2", NormalizeOptions.tts()),
            "джи эл эм пять точка два",
        )
        # A real unary minus is still recognised in every position that
        # protect_negative_numbers accepts.
        self.assertEqual(normalize("-5.2"), "минус пять целых две десятых")
        self.assertEqual(normalize("(-5.2)"), "(минус пять целых две десятых)")
        self.assertEqual(
            normalize("5.2 и -5.2"),
            "пять целых две десятых и минус пять целых две десятых",
        )
        self.assertEqual(
            normalize("от -5.2 до 3"),
            "от минус пяти целых двух десятых до трёх",
        )

    def test_numeric_range_keeps_its_separator_when_a_side_is_a_decimal(self):
        # The decimals stage rendered the right operand into words and left the
        # hyphen glued to it, at which point normalize_hyphenated_words treated
        # "10-пять целых…" like "10-этажный" and swapped the hyphen for a space,
        # so the two numbers ran together as one phrase.
        self.assertEqual(normalize("10-5"), "десять — пять")
        self.assertEqual(normalize("10-5.2"), "десять — пять целых две десятых")
        self.assertEqual(
            normalize("3-4.5 кг"),
            "три — четыре целых пять десятых килограмма",
        )
        self.assertEqual(
            normalize("вес 60-65.5 кг"),
            "вес шестьдесят — шестьдесят пять целых пять десятых килограмма",
        )
        # A decimal on the left kept a raw hyphen with no spaces around it, which
        # a TTS engine reads as one continuous token.
        self.assertEqual(
            normalize("1.5-2.5"),
            "одна целая пять десятых — две целых пять десятых",
        )
        self.assertEqual(
            normalize("температура 36.6-37.2"),
            "температура тридцать шесть целых шесть десятых — "
            "тридцать семь целых две десятых",
        )
        # A hyphen after a non-digit is not a range separator, and a genuine
        # unary minus is still recognized.
        self.assertEqual(normalize("GLM-5.2"), "GLM пять точка два")
        self.assertEqual(normalize("-5.2"), "минус пять целых две десятых")
        self.assertEqual(normalize("(-5.2)"), "(минус пять целых две десятых)")
        self.assertEqual(
            normalize("от -5.2 до 3"),
            "от минус пяти целых двух десятых до трёх",
        )

    def test_dotted_date_survives_a_following_era_word(self):
        # The years stage used to run first and take "2021 года" out of the
        # date, stranding "15.03." for the numerals stage to read as a fraction
        # whose trailing dot then became a sentence boundary
        # ("пятнадцать целых три сотых. Две тысячи двадцать первого года").
        expected = "пятнадцатого марта две тысячи двадцать первого года"
        for source in ("15.03.2021", "15.03.2021 года", "15.03.2021 г"):
            with self.subTest(source=source):
                self.assertEqual(normalize(source), expected)
        self.assertEqual(normalize("15.03.2021 г."), expected + ".")
        self.assertEqual(
            normalize("22.06.1941 года началась война"),
            "двадцать второго июня тысяча девятьсот сорок первого года началась война",
        )
        self.assertEqual(
            normalize("договор от 01.01.2020 г. №5"),
            "договор от первого января две тысячи двадцатого года номер пять",
        )
        # Bare years, year ranges and prose dates keep their previous reading.
        self.assertEqual(normalize("в 2021 г."), "в две тысячи двадцать первом году.")
        self.assertEqual(
            normalize("с 2020 по 2024 год"),
            "с две тысячи двадцатого по две тысячи двадцать четвёртый год",
        )
        self.assertEqual(
            normalize("15 марта 2021 года"),
            expected,
        )

    def test_dotted_version_numbers_are_read_component_by_component(self):
        # Three or more components cannot be a fraction, so the decimals stage
        # used to claim the first two and leave the rest as literal text, which
        # turned the orphaned dot into a sentence boundary and leaked the
        # fraction's genitive across it ("три целых двенадцать сотых. Одного").
        self.assertEqual(
            normalize("Python 3.12.1"),
            "Python три точка двенадцать точка один",
        )
        self.assertEqual(normalize("v1.2.3"), "v один точка два точка три")
        self.assertEqual(normalize("1.0.2"), "один точка ноль точка два")
        self.assertEqual(
            normalize("версия 2.03.1"),
            "версия два точка ноль три точка один",
        )
        self.assertEqual(
            normalize("Python 3.12.1.", NormalizeOptions.tts()),
            "пайсан три точка двенадцать точка один.",
        )

        # Two components read as a version only when a name claims them, which
        # also keeps the model number out of the surrounding case agreement
        # ("Ту-154.2" used to inflect to "сто пятьдесят четырёх целых" because
        # pymorphy parses "Ту" as the pronoun "тот").
        self.assertEqual(normalize("GPT-4.5"), "GPT четыре точка пять")
        self.assertEqual(normalize("Ту-154.2"), "Ту сто пятьдесят четыре точка два")

        # A bare two-component number stays a fraction, and so does a named one
        # whose value is followed by a unit, because that is a measurement.
        self.assertEqual(normalize("3.14"), "три целых четырнадцать сотых")
        self.assertEqual(normalize("iOS 18.4"), "iOS восемнадцать целых четыре десятых")
        self.assertEqual(normalize("X-1.5 кг"), "X-одна целая пять десятых килограмма")

        # Integer model numbers keep their hyphen, and neither dotted dates nor
        # European thousands separators are versions.
        self.assertEqual(normalize("Ту-154"), "Ту-сто пятьдесят четыре")
        self.assertEqual(
            normalize("15.03.2021"),
            "пятнадцатого марта две тысячи двадцать первого года",
        )
        self.assertEqual(
            normalize("1.234.567"),
            "один миллион двести тридцать четыре тысячи пятьсот шестьдесят семь",
        )

if __name__ == "__main__":
    unittest.main()
