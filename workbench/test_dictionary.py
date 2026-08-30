import unittest

from min0_core_forth_dictionary import (
    DICTIONARY_BASE,
    FLAG_HIDDEN,
    KIND_COLON,
    KIND_PRIMITIVE,
    DictionaryError,
    DictionaryFull,
    RuntimeDictionary,
)
from min0_core_forth_vm import Min0CoreForthVM, Op


class RuntimeDictionaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.vm = Min0CoreForthVM()
        self.dictionary = RuntimeDictionary(self.vm)

    def test_entry_layout_and_link_chain(self) -> None:
        dup = self.dictionary.add_primitive("dup", Op.DUP)
        star = self.dictionary.add_primitive("*", Op.MUL)
        square = self.dictionary.add_colon("square", 0x120)
        self.assertEqual(dup.header_address, DICTIONARY_BASE)
        self.assertEqual(dup.xt, 0x800C)
        self.assertEqual(star.header_address, 0x8014)
        self.assertEqual(star.xt, 0x8020)
        self.assertEqual(square.header_address, 0x8028)
        self.assertEqual(square.xt, 0x8038)
        self.assertEqual(self.dictionary.here, 0x8040)
        self.assertEqual(self.dictionary.latest, square.header_address)
        self.assertEqual(star.link, dup.header_address)
        self.assertEqual(square.link, star.header_address)
        self.assertEqual(dup.kind, KIND_PRIMITIVE)
        self.assertEqual(square.kind, KIND_COLON)

    def test_find_is_case_insensitive_and_latest_wins(self) -> None:
        old = self.dictionary.add_colon("TEST", 0x100)
        new = self.dictionary.add_colon("test", 0x200)
        self.assertNotEqual(old.xt, new.xt)
        self.assertEqual(self.dictionary.find("TeSt"), new)

    def test_hidden_entry_is_skipped(self) -> None:
        visible = self.dictionary.add_colon("WORD", 0x100)
        hidden = self.dictionary.add_colon("WORD", 0x200, hidden=True)
        self.assertTrue(hidden.flags & FLAG_HIDDEN)
        self.assertEqual(self.dictionary.find("WORD"), visible)
        self.assertEqual(self.dictionary.find("WORD", include_hidden=True), hidden)

    def test_immediate_flag_is_preserved(self) -> None:
        entry = self.dictionary.add_primitive("IMMEDIATE-WORD", Op.NOP, immediate=True)
        self.assertTrue(entry.immediate)

    def test_unknown_word_returns_none(self) -> None:
        self.assertIsNone(self.dictionary.find("MISSING"))

    def test_invalid_name_is_rejected(self) -> None:
        with self.assertRaises(DictionaryError):
            self.dictionary.add_primitive("", Op.NOP)
        with self.assertRaises(DictionaryError):
            self.dictionary.add_primitive("日本語", Op.NOP)

    def test_dictionary_limit_is_enforced(self) -> None:
        dictionary = RuntimeDictionary(self.vm, base=0x8000, limit=0x8010)
        with self.assertRaises(DictionaryFull):
            dictionary.add_primitive("TOO-LARGE", Op.NOP)

    def test_hidden_flag_can_be_cleared(self) -> None:
        entry = self.dictionary.add_colon("BUILDING", 0x100, hidden=True)
        self.assertIsNone(self.dictionary.find("BUILDING"))
        entry = self.dictionary.set_hidden(entry, False)
        self.assertFalse(entry.hidden)
        self.assertEqual(self.dictionary.find("BUILDING"), entry)

    def test_restore_removes_new_entries(self) -> None:
        keep = self.dictionary.add_primitive("KEEP", Op.NOP)
        saved_here = self.dictionary.here
        saved_latest = self.dictionary.latest
        self.dictionary.add_primitive("REMOVE", Op.NOP)
        self.dictionary.restore(here=saved_here, latest=saved_latest)
        self.assertEqual(self.dictionary.find("KEEP"), keep)
        self.assertIsNone(self.dictionary.find("REMOVE"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
