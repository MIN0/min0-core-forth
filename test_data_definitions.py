import unittest

from min0_core_forth_dictionary import (
    ALIGNMENT,
    DICTIONARY_BASE,
    KIND_CONSTANT,
    KIND_VARIABLE,
    DictionaryError,
    DictionaryFull,
    RuntimeDictionary,
)
from min0_core_forth_outer import (
    STATE_INTERPRET,
    CompileStateError,
    OuterInterpreter,
    install_core_primitives,
)
from min0_core_forth_vm import CELL_MASK, Min0CoreForthVM, StackUnderflow


def aligned(address: int) -> int:
    return (address + ALIGNMENT - 1) & ~(ALIGNMENT - 1)


def build_outer(
    *, limit: int | None = None, install_primitives: bool = True
) -> tuple[Min0CoreForthVM, RuntimeDictionary, OuterInterpreter]:
    vm = Min0CoreForthVM()
    dictionary = RuntimeDictionary(vm, limit=limit)
    if install_primitives:
        install_core_primitives(dictionary)
    return vm, dictionary, OuterInterpreter(vm, dictionary)


class DataDefinitionTests(unittest.TestCase):
    def test_constant_interprets_and_compiles_as_literal(self) -> None:
        _vm, dictionary, outer = build_outer()
        outer.interpret("123 CONSTANT ANSWER")
        entry = dictionary.find("answer")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual((entry.kind, entry.payload), (KIND_CONSTANT, 123))
        self.assertEqual(outer.interpret("ANSWER"), [123])
        outer.vm.data_stack.clear()
        outer.interpret(": DOUBLE-ANSWER ANSWER ANSWER + ;")
        self.assertEqual(outer.interpret("DOUBLE-ANSWER"), [246])

    def test_variable_is_zeroed_and_pushes_stable_address(self) -> None:
        vm, dictionary, outer = build_outer()
        outer.interpret("VARIABLE SLOT")
        entry = dictionary.find("SLOT")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.kind, KIND_VARIABLE)
        self.assertEqual(entry.payload % ALIGNMENT, 0)
        self.assertEqual(vm.read_cell(entry.payload), 0)
        self.assertEqual(outer.interpret("42 SLOT ! SLOT @"), [42])
        vm.data_stack.clear()
        outer.interpret(": SETGET 99 SLOT ! SLOT @ ;")
        self.assertEqual(outer.interpret("SETGET"), [99])
        self.assertEqual(entry.payload, dictionary.find("SLOT").payload)

    def test_allot_is_byte_granular_and_comma_realigns(self) -> None:
        vm, dictionary, outer = build_outer()
        before = dictionary.here
        self.assertEqual(outer.interpret("3 ALLOT HERE"), [before + 3])
        outer.interpret("0x12345678 , HERE")
        cell_address = aligned(before + 3)
        self.assertEqual(vm.read_cell(cell_address), 0x12345678)
        self.assertEqual(vm.data_stack, [before + 3, cell_address + 4])
        self.assertEqual(bytes(vm.memory[before:cell_address]), b"\x00" * 4)

    def test_variable_data_field_follows_aligned_header(self) -> None:
        vm, dictionary, outer = build_outer()
        before = dictionary.here
        outer.interpret("3 ALLOT VARIABLE ODD")
        entry = dictionary.find("ODD")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertGreaterEqual(entry.header_address, aligned(before + 3))
        self.assertEqual(entry.payload, entry.xt + 8)
        self.assertEqual(vm.read_cell(entry.payload), 0)
        self.assertEqual(entry.header_address % ALIGNMENT, 0)

    def test_negative_allot_is_rejected_without_consuming_argument(self) -> None:
        _vm, dictionary, outer = build_outer()
        saved_here = dictionary.here
        with self.assertRaises(DictionaryError):
            outer.interpret("-1 ALLOT")
        self.assertEqual(outer.vm.data_stack, [CELL_MASK])
        self.assertEqual(dictionary.here, saved_here)

    def test_comma_full_preserves_value_and_existing_data(self) -> None:
        vm, dictionary, outer = build_outer(
            limit=DICTIONARY_BASE + 4, install_primitives=False
        )
        outer.interpret("7 ,")
        self.assertEqual(vm.read_cell(DICTIONARY_BASE), 7)
        with self.assertRaises(DictionaryFull):
            outer.interpret("8 ,")
        self.assertEqual(vm.data_stack, [8])
        self.assertEqual(dictionary.here, DICTIONARY_BASE + 4)
        self.assertEqual(vm.read_cell(DICTIONARY_BASE), 7)

    def test_failed_variable_definition_rolls_back_allocated_cell(self) -> None:
        vm, dictionary, outer = build_outer(
            limit=DICTIONARY_BASE + 20, install_primitives=False
        )
        with self.assertRaises(DictionaryFull):
            outer.interpret("VARIABLE X")
        self.assertEqual(dictionary.here, DICTIONARY_BASE)
        self.assertEqual(dictionary.latest, 0)
        self.assertEqual(dictionary.image(), b"")
        self.assertEqual(vm.read_cell(DICTIONARY_BASE), 0)

    def test_failed_constant_definition_preserves_value(self) -> None:
        _vm, dictionary, outer = build_outer(
            limit=DICTIONARY_BASE, install_primitives=False
        )
        with self.assertRaises(DictionaryFull):
            outer.interpret("9 CONSTANT X")
        self.assertEqual(outer.vm.data_stack, [9])
        self.assertEqual(dictionary.here, DICTIONARY_BASE)
        self.assertEqual(dictionary.latest, 0)

    def test_data_words_validate_state_names_and_stack(self) -> None:
        _vm, dictionary, outer = build_outer()
        for source in ("CONSTANT", "VARIABLE", "CREATE"):
            with self.subTest(source=source), self.assertRaises(CompileStateError):
                outer.interpret(source)
        for source in (",", "C,", "ALLOT", "CONSTANT X"):
            with self.subTest(source=source), self.assertRaises(StackUnderflow):
                outer.interpret(source)
        outer.interpret("1")
        with self.assertRaises(CompileStateError):
            outer.interpret("CONSTANT HERE")
        self.assertEqual(outer.vm.data_stack, [1])
        self.assertIsNone(dictionary.find("HERE"))

    def test_data_words_inside_colon_roll_back_definition(self) -> None:
        for word in ("HERE", ",", "C,", "ALLOT", "ALIGN", "CONSTANT", "VARIABLE"):
            with self.subTest(word=word):
                _vm, dictionary, outer = build_outer()
                saved_here = dictionary.here
                saved_code_here = outer.code_here
                with self.assertRaises(CompileStateError):
                    outer.interpret(f": BAD {word} ;")
                self.assertEqual(outer.state, STATE_INTERPRET)
                self.assertEqual(dictionary.here, saved_here)
                self.assertEqual(outer.code_here, saved_code_here)
                self.assertIsNone(dictionary.find("BAD", include_hidden=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
