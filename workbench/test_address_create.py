import unittest

from min0_core_forth_dictionary import (
    DICTIONARY_BASE,
    KIND_CREATED,
    DictionaryFull,
    RuntimeDictionary,
)
from min0_core_forth_outer import CompileStateError, OuterInterpreter, install_core_primitives
from min0_core_forth_vm import CELL_MASK, Min0CoreForthVM, StackUnderflow


def aligned(address: int) -> int:
    return (address + 3) & ~3


def build_outer(
    *, limit: int | None = None, install_primitives: bool = True
) -> tuple[Min0CoreForthVM, RuntimeDictionary, OuterInterpreter]:
    vm = Min0CoreForthVM()
    dictionary = RuntimeDictionary(vm, limit=limit)
    if install_primitives:
        install_core_primitives(dictionary)
    return vm, dictionary, OuterInterpreter(vm, dictionary)


class AddressAndCreateTests(unittest.TestCase):
    def test_cell_address_words_interpret_and_compile(self) -> None:
        vm, _dictionary, outer = build_outer()
        self.assertEqual(
            outer.interpret("1 CELLS 5 CELL+ 5 ALIGNED 4 ALIGNED"),
            [4, 9, 8, 4],
        )
        vm.data_stack.clear()
        outer.interpret(": ADDRESS-OPS 3 CELLS 5 CELL+ 5 ALIGNED ;")
        self.assertEqual(outer.interpret("ADDRESS-OPS"), [12, 9, 8])

    def test_cell_address_words_wrap_as_cells(self) -> None:
        _vm, _dictionary, outer = build_outer()
        self.assertEqual(
            outer.interpret("-1 CELL+ -1 CELLS -1 ALIGNED"),
            [3, CELL_MASK - 3, 0],
        )

    def test_cell_address_words_check_underflow(self) -> None:
        for word in ("CELL+", "CELLS", "ALIGNED"):
            with self.subTest(word=word):
                _vm, _dictionary, outer = build_outer()
                with self.assertRaises(StackUnderflow):
                    outer.interpret(word)

    def test_align_advances_dictionary_here_once(self) -> None:
        vm, dictionary, outer = build_outer()
        before = dictionary.here
        outer.interpret("3 ALLOT HERE ALIGN HERE ALIGN HERE")
        after = aligned(before + 3)
        self.assertEqual(vm.data_stack, [before + 3, after, after])
        self.assertEqual(dictionary.here, after)
        self.assertEqual(bytes(vm.memory[before:after]), b"\x00" * (after - before))

    def test_create_builds_contiguous_data_field(self) -> None:
        vm, dictionary, outer = build_outer()
        outer.interpret("CREATE TABLE 10 , 20 ,")
        entry = dictionary.find("table")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.kind, KIND_CREATED)
        self.assertEqual(entry.payload, entry.xt + 8)
        self.assertEqual(vm.read_cell(entry.payload), 10)
        self.assertEqual(vm.read_cell(entry.payload + 4), 20)
        self.assertEqual(outer.interpret("TABLE"), [entry.payload])
        vm.data_stack.clear()
        outer.interpret(": SECOND TABLE CELL+ @ ;")
        self.assertEqual(outer.interpret("SECOND"), [20])

    def test_create_allot_reserves_body_bytes(self) -> None:
        vm, dictionary, outer = build_outer()
        outer.interpret("CREATE BUFFER 7 ALLOT")
        entry = dictionary.find("BUFFER")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(dictionary.here, entry.payload + 7)
        self.assertEqual(bytes(vm.memory[entry.payload : dictionary.here]), b"\x00" * 7)
        outer.interpret("99 CONSTANT AFTER")
        self.assertEqual(dictionary.find("BUFFER").payload, entry.payload)

    def test_failed_create_does_not_change_dictionary(self) -> None:
        vm, dictionary, outer = build_outer(
            limit=DICTIONARY_BASE + 19, install_primitives=False
        )
        with self.assertRaises(DictionaryFull):
            outer.interpret("CREATE X")
        self.assertEqual(dictionary.here, DICTIONARY_BASE)
        self.assertEqual(dictionary.latest, 0)
        self.assertEqual(dictionary.image(), b"")
        self.assertEqual(vm.read_cell(DICTIONARY_BASE), 0)

    def test_create_rejects_reserved_name(self) -> None:
        _vm, dictionary, outer = build_outer()
        with self.assertRaises(CompileStateError):
            outer.interpret("CREATE CREATE")
        self.assertIsNone(dictionary.find("CREATE"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
