"""The .dic rule format — the contract the README documents for users.

Rules are read from files, so a malformed line must never take the whole
dictionary down: the parser skips what it cannot use and keeps the rest. These
tests build dictionaries on disk and assert the resulting substitutions, not the
internal chunk layout.
"""

import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ru_normalizr import NormalizeOptions, Normalizer, dictionary
from ru_normalizr.dictionary import (
    DictionaryLoadError,
    DictionaryNormalizer,
    apply_dictionary_rules,
)


class DictionaryRuleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write_dic(self, name: str, body: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def normalizer(self, **kwargs) -> DictionaryNormalizer:
        return DictionaryNormalizer(dictionaries_path=self.root, **kwargs)

    @staticmethod
    def _failing_open(failing_name: str):
        """Подменить ``Path.open`` так, чтобы падал только один файл."""
        real_open = Path.open

        def fake_open(self_path, *args, **kwargs):
            if self_path.name == failing_name:
                raise OSError("disk is on fire")
            return real_open(self_path, *args, **kwargs)

        return fake_open


class SimpleRuleTests(DictionaryRuleTestCase):
    def test_simple_rule_replaces_whole_words_case_insensitively(self):
        self.write_dic("a.dic", "YouTube=ютуб\n")
        apply = self.normalizer().apply

        self.assertEqual(apply("Смотри YouTube сейчас"), "Смотри ютуб сейчас")
        self.assertEqual(apply("смотри youtube"), "смотри ютуб")
        self.assertEqual(apply("YOUTUBE"), "ютуб")

    def test_simple_rule_does_not_match_inside_a_longer_word(self):
        self.write_dic("a.dic", "код=code\n")
        apply = self.normalizer().apply

        self.assertEqual(apply("код"), "code")
        self.assertEqual(apply("кодекс"), "кодекс")
        self.assertEqual(apply("перекод"), "перекод")

    def test_longer_key_wins_over_a_shorter_overlapping_one(self):
        # Keys are matched longest-first, otherwise "СССР" would be eaten by "СС".
        self.write_dic("a.dic", "СС=эс эс\nСССР=эс эс эс эр\n")

        self.assertEqual(self.normalizer().apply("СССР"), "эс эс эс эр")

    def test_longer_multi_word_key_wins_over_its_own_first_word(self):
        # Word boundaries alone save single-token keys, because the shorter key
        # cannot end mid-word. Two keys can only really compete when the longer
        # one continues past a space, so ordering has to be asserted here.
        self.write_dic("a.dic", "первый=головной\nпервый класс=высшая категория\n")

        self.assertEqual(
            self.normalizer().apply("Ему достался первый класс до Москвы"),
            "Ему достался высшая категория до Москвы",
        )

    def test_empty_replacement_deletes_the_word(self):
        self.write_dic("a.dic", "мусор=\n")

        self.assertEqual(self.normalizer().apply("слово мусор тут"), "слово  тут")

    def test_single_character_source_rule_loads(self):
        # The shortest possible rule puts "=" at index 1, right next to the
        # "no separator at all" case the parser has to reject.
        self.write_dic("a.dic", "я=аз\n")

        self.assertEqual(self.normalizer().apply("я помню чудное мгновенье"), "аз помню чудное мгновенье")

    def test_latin_source_stays_in_the_simple_batch(self):
        # The source is case-insensitive, but a plain Latin letter is still a
        # simple rule. If it is misclassified as a regex, the following rule
        # sees the replacement and creates an unintended cascade.
        self.write_dic("a.dic", "X=икс\nикс=значок\n")

        self.assertEqual(
            self.normalizer().apply("В отчёте X отмечен."),
            "В отчёте икс отмечен.",
        )

    def test_line_without_a_separator_never_becomes_a_rule(self):
        # A stray note must be dropped, not read as a rule whose source is the
        # line minus its last character and whose target is the whole line.
        self.write_dic("a.dic", "уточнить у заказчика.\nхорошо=ок\n")
        apply = self.normalizer().apply

        self.assertEqual(
            apply("Надо уточнить у заказчика, потом решим"),
            "Надо уточнить у заказчика, потом решим",
        )
        self.assertEqual(apply("хорошо"), "ок")

    def test_commented_out_rule_is_neither_counted_nor_applied(self):
        # Commenting a rule out is how a rule gets disabled, so the line must not
        # come back as a rule whose source starts with the "#".
        self.write_dic("a.dic", "# youtube=ютуб\nхорошо=ок\n")
        normalizer = self.normalizer()

        self.assertEqual(normalizer.get_rule_count(), 1)
        self.assertEqual(normalizer.apply("Смотри youtube вечером"), "Смотри youtube вечером")
        self.assertEqual(normalizer.apply("хорошо"), "ок")

    def test_replacement_keeps_its_last_character_including_a_capital_letter(self):
        # Only the line break is stripped from a rule line, so a replacement is
        # taken verbatim: a trailing capital must not be eaten along with "\r".
        self.write_dic("a.dic", "модель икс=Model X\r\nоблако=Cloud\r\n")
        apply = self.normalizer().apply

        self.assertEqual(
            apply("Он выбрал модель икс для семьи"), "Он выбрал Model X для семьи"
        )
        self.assertEqual(apply("Данные ушли в облако"), "Данные ушли в Cloud")

    def test_malformed_lines_are_skipped_without_losing_valid_rules(self):
        self.write_dic(
            "a.dic",
            "\n".join(
                (
                    "# комментарий",
                    "",
                    "строка без знака равенства",
                    "=цель без источника",
                    "$=только якорь",
                    "хорошо=ок",
                )
            )
            + "\n",
        )

        self.assertEqual(self.normalizer().apply("хорошо"), "ок")

    def test_a_dictionary_with_no_usable_rules_leaves_text_untouched(self):
        self.write_dic("a.dic", "# только комментарии\n\n")
        normalizer = self.normalizer()

        self.assertEqual(normalizer.apply("текст 123"), "текст 123")
        self.assertEqual(normalizer.get_rule_count(), 0)

    def test_rule_count_reports_every_loaded_rule(self):
        self.write_dic("a.dic", "один=1\nдва=2\n")
        self.write_dic("b.dic", "три=3\n")

        self.assertEqual(self.normalizer().get_rule_count(), 3)


class WildcardRuleTests(DictionaryRuleTestCase):
    def test_suffix_wildcard_keeps_the_matched_tail(self):
        self.write_dic("a.dic", "микро*=микро-\n")

        self.assertEqual(self.normalizer().apply("микросхема"), "микро-схема")

    def test_prefix_wildcard_keeps_the_matched_head(self):
        self.write_dic("a.dic", "*ing=инг\n")

        self.assertEqual(self.normalizer().apply("marketing"), "marketинг")

    def test_double_sided_wildcard_replaces_the_substring_everywhere(self):
        # *foo* is an in-word substring rule, so it must hit both occurrences and
        # match in the middle of a word rather than only as a whole token.
        self.write_dic("a.dic", "*ph*=ф\n")

        self.assertEqual(self.normalizer().apply("phone graph"), "фone graф")
        self.assertEqual(
            self.normalizer().apply("В phphone найдено совпадение."),
            "В ффone найдено совпадение.",
        )
        self.assertEqual(
            self.normalizer().apply("В Phone найдено совпадение."),
            "В фone найдено совпадение.",
        )

    def test_multiple_wildcard_groups_preserve_both_matched_tails(self):
        self.write_dic("a.dic", "*foo*bar*=значок\n")

        self.assertEqual(
            self.normalizer().apply("В prefooXXbarpost найдено совпадение."),
            "В preзначокpost найдено совпадение.",
        )

    def test_inner_wildcard_spans_the_middle_of_a_token(self):
        self.write_dic("a.dic", "un*ing=безобразие\n")

        self.assertEqual(self.normalizer().apply("unboxing"), "безобразие")
        self.assertEqual(self.normalizer().apply("unrelated"), "unrelated")

    def test_anchored_rule_only_fires_at_the_start_of_the_text(self):
        self.write_dic("a.dic", "$Глава*=Раздел\n")
        apply = self.normalizer().apply

        self.assertEqual(apply("Глава5"), "Раздел5")
        self.assertEqual(apply("см. Глава5"), "см. Глава5")

    def test_anchored_substring_rule_only_fires_at_the_start_of_the_text(self):
        self.write_dic("a.dic", "$*ph*=ф\n")
        apply = self.normalizer().apply

        self.assertEqual(apply("phone"), "фone")
        self.assertEqual(apply("a phone"), "a phone")

    def test_rule_starting_with_punctuation_matches_mid_token(self):
        # The left word boundary is only added when the pattern starts with an
        # alphanumeric, so a punctuation-led rule stays usable inside a token.
        self.write_dic("a.dic", "(с)=со знаком\n")

        self.assertEqual(self.normalizer().apply("текст(с)"), "текстсо знаком")

    def test_consecutive_wildcards_still_span_the_middle(self):
        self.write_dic("a.dic", "на**ка=слово\n")
        apply = self.normalizer().apply

        self.assertEqual(apply("наклейка"), "слово")
        self.assertEqual(apply("наклейки"), "наклейки")

    def test_regex_metacharacters_in_the_source_are_matched_literally(self):
        # A bracket makes the rule take the regex path, but the literal parts are
        # escaped, so it must match the brackets themselves rather than a class.
        self.write_dic("a.dic", "[тег]*=метка\n")
        apply = self.normalizer().apply

        self.assertEqual(apply("[тег]значение"), "метказначение")
        self.assertEqual(apply("тег"), "тег")

    def test_uncompilable_wildcard_rule_is_skipped_and_the_rest_still_loads(self):
        # Literal parts are escaped, so a rule normally compiles; this covers the
        # guard for the cases that still fail, such as an over-long pattern.
        self.write_dic("a.dic", "плохо*=нет\nхорошо=ок\n")
        real_compile = re.compile

        def fail_for_wildcard(pattern, *args, **kwargs):
            if isinstance(pattern, str) and "плохо" in pattern:
                raise re.error("pattern is too complex")
            return real_compile(pattern, *args, **kwargs)

        with patch.object(re, "compile", fail_for_wildcard):
            normalizer = self.normalizer()

        self.assertEqual(normalizer.apply("плохоXYZ"), "плохоXYZ")
        self.assertEqual(normalizer.apply("хорошо"), "ок")

    def test_rule_whose_substitution_fails_at_runtime_is_skipped(self):
        # An invalid group reference only raises when sub() runs, not at compile
        # time, so this is the guard around the substitution itself.
        self.write_dic("a.dic", "микро*=\\g<9>\nхорошо=ок\n")
        apply = self.normalizer().apply

        self.assertEqual(apply("микросхема"), "микросхема")
        self.assertEqual(apply("хорошо"), "ок")


class RuleOrderingTests(DictionaryRuleTestCase):
    def test_files_apply_in_sorted_filename_order(self):
        self.write_dic("10_first.dic", "слово=первое\n")
        self.write_dic("20_second.dic", "первое=второе\n")

        self.assertEqual(self.normalizer().apply("слово"), "второе")

    def test_simple_and_wildcard_rules_apply_in_file_order(self):
        # Switching between rule kinds splits the file into chunks; the chunks
        # must still run top to bottom.
        self.write_dic("a.dic", "альфа=бета\nбета*=гамма\nгамма=дельта\n")

        self.assertEqual(self.normalizer().apply("альфа"), "дельта")


class FileSelectionTests(DictionaryRuleTestCase):
    def test_missing_dictionaries_directory_is_not_an_error(self):
        normalizer = DictionaryNormalizer(dictionaries_path=self.root / "нет")

        self.assertEqual(normalizer.apply("текст"), "текст")
        self.assertEqual(normalizer.get_rule_count(), 0)

    def test_latinization_directory_is_skipped_unless_requested_explicitly(self):
        self.write_dic("latinization/rules.dic", "phone=фон\n")
        self.write_dic("plain.dic", "слово=ок\n")

        default = self.normalizer()
        self.assertEqual(default.apply("phone"), "phone")
        self.assertEqual(default.apply("слово"), "ок")

        explicit = self.normalizer(include_only_files=["latinization/rules.dic"])
        self.assertEqual(explicit.apply("phone"), "фон")
        self.assertEqual(explicit.apply("слово"), "слово")

    def test_include_only_accepts_a_bare_file_name(self):
        self.write_dic("nested/brands.dic", "YouTube=ютуб\n")
        self.write_dic("other.dic", "слово=ок\n")

        normalizer = self.normalizer(include_only_files=["brands.dic"])

        self.assertEqual(normalizer.apply("YouTube"), "ютуб")
        self.assertEqual(normalizer.apply("слово"), "слово")

    def test_exclude_files_accepts_a_bare_name_and_a_relative_path(self):
        self.write_dic("skip_me.dic", "слово=нет\n")
        self.write_dic("nested/skip_path.dic", "другое=нет\n")
        self.write_dic("keep.dic", "третье=да\n")

        normalizer = self.normalizer(
            exclude_files=["skip_me.dic", "nested/skip_path.dic"]
        )

        self.assertEqual(normalizer.apply("слово другое третье"), "слово другое да")

    def test_excluded_file_does_not_stop_the_files_after_it(self):
        # Files load in sorted order, so the skip has to continue the scan: an
        # excluded dictionary must not silently disable everything below it.
        self.write_dic("a_skipped.dic", "первое=нет\n")
        self.write_dic("z_kept.dic", "второе=да\n")

        normalizer = self.normalizer(exclude_files=["a_skipped.dic"])

        self.assertEqual(normalizer.apply("первое и второе"), "первое и да")

    def test_include_only_keeps_scanning_past_a_non_matching_file(self):
        self.write_dic("a_other.dic", "первое=нет\n")
        self.write_dic("z_wanted.dic", "второе=да\n")

        normalizer = self.normalizer(include_only_files=["z_wanted.dic"])

        self.assertEqual(normalizer.apply("первое и второе"), "первое и да")

    def test_latinization_directory_does_not_stop_the_files_after_it(self):
        # "latinization/..." sorts before "z_plain.dic", so skipping the former
        # must not cost us the latter.
        self.write_dic("latinization/rules.dic", "phone=фон\n")
        self.write_dic("z_plain.dic", "второе=да\n")

        self.assertEqual(self.normalizer().apply("phone и второе"), "phone и да")

    def test_subdirectories_are_searched_recursively(self):
        self.write_dic("deep/deeper/rules.dic", "слово=ок\n")

        self.assertEqual(self.normalizer().apply("слово"), "ок")

    def test_unreadable_user_dictionary_raises_instead_of_dropping_rules(self):
        # Раньше нечитаемый файл просто выпадал из загрузки: нормализация молча
        # становилась неполной, и наружу это выглядело как пропущенное правило.
        self.write_dic("a_broken.dic", "слово=нет\n")
        self.write_dic("b_good.dic", "другое=да\n")

        with (
            patch.object(Path, "open", self._failing_open("a_broken.dic")),
            self.assertRaises(DictionaryLoadError) as raised,
        ):
            self.normalizer()

        self.assertIn("a_broken.dic", str(raised.exception))

    def test_unreadable_bundled_dictionary_is_logged_and_skipped(self):
        # Словари из состава пакета — другой случай: сломать их может только
        # сборка, и отказ на старте хуже частичной функциональности.
        with (
            patch.object(Path, "open", self._failing_open("latinization_rules.dic")),
            self.assertLogs("ru_normalizr.dictionary", level="ERROR") as logs,
        ):
            normalizer = DictionaryNormalizer(
                include_only_files=["latinization/latinization_rules.dic"]
            )

        self.assertEqual(normalizer.get_rule_count(), 0)
        self.assertTrue(any("latinization_rules.dic" in message for message in logs.output))

    def test_invalid_utf8_bytes_are_replaced_instead_of_raising(self):
        (self.root / "a.dic").write_bytes(b"\xff\xfe=bad\n\xd1\x85\xd0\xbe=ok\n")

        self.assertEqual(self.normalizer().apply("хо"), "ok")


class ApplyOptionTests(DictionaryRuleTestCase):
    def test_strip_unmatched_latin_removes_only_latin_letters(self):
        self.write_dic("a.dic", "YouTube=ютуб\n")

        result = self.normalizer().apply(
            "YouTube и Unknown 42!", strip_unmatched_latin=True
        )

        self.assertEqual(result, "ютуб и  42!")

    def test_strip_unmatched_latin_is_off_by_default(self):
        self.write_dic("a.dic", "YouTube=ютуб\n")

        self.assertEqual(self.normalizer().apply("YouTube и Unknown"), "ютуб и Unknown")

    def test_batch_compile_failure_falls_back_to_per_key_patterns(self):
        # The batched alternation is an optimization; its fallback must retain
        # the same one-pass semantics instead of re-reading replacement text.
        self.write_dic("a.dic", "один=два\nдва=2\n")
        real_compile = re.compile
        calls = {"batched": 0}

        def fail_batched(pattern, *args, **kwargs):
            if isinstance(pattern, str) and "(?:" in pattern:
                calls["batched"] += 1
                raise re.error("pattern too complex")
            return real_compile(pattern, *args, **kwargs)

        with patch.object(re, "compile", fail_batched):
            normalizer = self.normalizer()

        self.assertEqual(calls["batched"], 1)
        self.assertEqual(normalizer.apply("один и два"), "два и 2")

    def test_more_than_one_thousand_simple_rules_still_apply(self):
        # Above the batching threshold the loader keeps a plain mapping instead
        # of one compiled alternation.
        body = "".join(f"слово{index}=число{index}\n" for index in range(1200))
        self.write_dic("a.dic", body)
        normalizer = self.normalizer()

        self.assertEqual(normalizer.get_rule_count(), 1200)
        self.assertEqual(normalizer.apply("слово0 и слово1199"), "число0 и число1199")

    def test_exactly_one_thousand_simple_rules_apply_once(self):
        filler = "".join(f"наполнитель{index}=пусто{index}\n" for index in range(998))
        self.write_dic("a.dic", filler + "youtube=ютуб\nютуб=видеосервис\n")

        self.assertEqual(
            self.normalizer().apply("Смотри youtube и ютуб каждый вечер."),
            "Смотри ютуб и видеосервис каждый вечер.",
        )


class LargeDictionaryTests(DictionaryRuleTestCase):
    """The large-dictionary matcher must preserve batched one-pass semantics."""

    def write_bulky_dic(self, *rules: str) -> None:
        filler = "".join(f"наполнитель{index}=пусто{index}\n" for index in range(1200))
        self.write_dic("a.dic", filler + "".join(f"{rule}\n" for rule in rules))

    def test_longest_key_wins_when_keys_are_multi_word(self):
        # Replacing "первый" first would leave "первый класс" unreachable, and a
        # multi-word key is the only way two keys can overlap once each pattern
        # carries its own word boundaries.
        self.write_bulky_dic("первый=головной", "первый класс=высшая категория")

        self.assertEqual(
            self.normalizer().apply("Ему достался первый класс до Москвы"),
            "Ему достался высшая категория до Москвы",
        )

    def test_keys_still_match_regardless_of_case(self):
        # Sources are lower-cased when loaded, so matching capitalised text at
        # all depends on the pattern staying case-insensitive.
        self.write_bulky_dic("линукс=Linux")
        apply = self.normalizer().apply

        self.assertEqual(apply("Он поставил линукс на сервер"), "Он поставил Linux на сервер")
        self.assertEqual(apply("ЛИНУКС победил"), "Linux победил")
        self.assertEqual(apply("Линукс победил"), "Linux победил")

    def test_replacement_is_not_processed_again_by_the_same_simple_block(self):
        self.write_bulky_dic("youtube=ютуб", "ютуб=видеосервис")

        self.assertEqual(
            self.normalizer().apply("Смотри youtube и ютуб каждый вечер."),
            "Смотри ютуб и видеосервис каждый вечер.",
        )


class PackagedDictionaryTests(unittest.TestCase):
    """Constructed without a path, the normalizer must find its own .dic files."""

    def test_default_path_finds_the_packaged_latinization_dictionary(self):
        normalizer = DictionaryNormalizer(include_only_files=["latinization_rules.dic"])

        self.assertGreater(normalizer.get_rule_count(), 0)
        self.assertEqual(normalizer.apply("Модель a"), "Модель Эй,")

    def test_default_path_ships_nothing_outside_latinization(self):
        # The only bundled dictionary lives under latinization/, which the
        # default scan skips, so an unconfigured normalizer is a no-op.
        normalizer = DictionaryNormalizer()

        self.assertEqual(normalizer.get_rule_count(), 0)
        self.assertEqual(normalizer.apply("Модель a"), "Модель a")


class PublicFunctionTests(DictionaryRuleTestCase):
    def test_latin_is_kept_unless_stripping_is_requested(self):
        self.write_dic("a.dic", "линукс=Linux\n")

        self.assertEqual(
            apply_dictionary_rules(
                "Он поставил линукс вместо Windows",
                dictionaries_path=self.root,
            ),
            "Он поставил Linux вместо Windows",
        )

    def test_omitting_the_path_falls_back_to_the_packaged_dictionaries(self):
        # No path means "use the ones shipped with the package"; nothing outside
        # latinization ships, so the text returns untouched rather than raising.
        self.assertEqual(
            apply_dictionary_rules("Он поставил линукс вместо Windows"),
            "Он поставил линукс вместо Windows",
        )

    def test_public_function_can_select_a_packaged_dictionary(self):
        self.assertEqual(
            apply_dictionary_rules(
                "Модель a",
                include_only_files=("latinization_rules.dic",),
            ),
            "Модель Эй,",
        )

    def test_disabled_rules_leave_the_text_alone(self):
        self.write_dic("a.dic", "линукс=Linux\n")

        # Выключение стадии — дело пайплайна: у `apply_dictionary_rules`
        # параметра `enabled` больше нет.
        normalizer = Normalizer(
            NormalizeOptions(
                enable_dictionary_normalization=False,
                dictionaries_path=self.root,
            )
        )
        self.assertEqual(
            normalizer.run_stage("dictionary", "Он поставил линукс вместо Windows"),
            "Он поставил линукс вместо Windows",
        )


class NormalizerRegistryTests(DictionaryRuleTestCase):
    """Реестр ``get_dictionary_normalizer`` ограничен по размеру.

    Долгоживущий сервис, который берёт путь к словарям или include/exclude из
    запроса, раньше накапливал по нормализатору на каждую комбинацию — со всеми
    скомпилированными паттернами — и не отдавал память никогда.
    """

    def setUp(self) -> None:
        super().setUp()
        saved = dictionary._normalizers.copy()
        dictionary._normalizers.clear()

        def restore() -> None:
            dictionary._normalizers.clear()
            dictionary._normalizers.update(saved)

        self.addCleanup(restore)

    def test_same_arguments_reuse_one_normalizer(self):
        self.write_dic("a.dic", "один=1\n")

        first = dictionary.get_dictionary_normalizer(self.root)
        second = dictionary.get_dictionary_normalizer(self.root)

        self.assertIs(first, second)

    def test_registry_never_exceeds_its_bound(self):
        self.write_dic("a.dic", "один=1\n")

        for index in range(dictionary._NORMALIZERS_MAXSIZE * 3):
            dictionary.get_dictionary_normalizer(
                self.root, exclude_files=[f"missing_{index}.dic"]
            )

        self.assertEqual(len(dictionary._normalizers), dictionary._NORMALIZERS_MAXSIZE)

    def test_least_recently_used_entry_is_evicted_first(self):
        self.write_dic("a.dic", "один=1\n")
        first_key_normalizer = dictionary.get_dictionary_normalizer(
            self.root, exclude_files=["keep.dic"]
        )

        # Обращение к первой записи делает её свежей, поэтому вытесняться должны
        # следующие за ней, а не она сама.
        for index in range(dictionary._NORMALIZERS_MAXSIZE - 1):
            dictionary.get_dictionary_normalizer(
                self.root, exclude_files=[f"filler_{index}.dic"]
            )
        self.assertIs(
            dictionary.get_dictionary_normalizer(self.root, exclude_files=["keep.dic"]),
            first_key_normalizer,
        )

        dictionary.get_dictionary_normalizer(self.root, exclude_files=["overflow.dic"])

        self.assertIs(
            dictionary.get_dictionary_normalizer(self.root, exclude_files=["keep.dic"]),
            first_key_normalizer,
        )
        self.assertEqual(len(dictionary._normalizers), dictionary._NORMALIZERS_MAXSIZE)

    def test_different_include_sets_get_different_normalizers(self):
        self.write_dic("a.dic", "один=1\n")
        self.write_dic("b.dic", "два=2\n")

        only_a = dictionary.get_dictionary_normalizer(self.root, include_only_files=["a.dic"])
        only_b = dictionary.get_dictionary_normalizer(self.root, include_only_files=["b.dic"])

        self.assertIsNot(only_a, only_b)
        self.assertEqual(only_a.apply("один два"), "1 два")
        self.assertEqual(only_b.apply("один два"), "один 2")


if __name__ == "__main__":
    unittest.main()
