import unittest

from min0_core_forth_dictionary import DICTIONARY_BASE, DictionaryFull, RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import (
    CELL_MASK,
    MemoryFault,
    MemoryRegion,
    Min0CoreForthVM,
    RegionMemory,
    StackUnderflow,
)


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


class CharacterDataTests(unittest.TestCase):
    def test_c_comma_c_fetch_and_char_plus(self) -> None:
        vm, dictionary, outer = build_outer()
        outer.interpret("CREATE BYTES 0x41 C, 0x142 C,")
        entry = dictionary.find("BYTES")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(bytes(vm.memory[entry.payload : entry.payload + 2]), b"AB")
        self.assertEqual(
            outer.interpret("BYTES C@ BYTES CHAR+ C@"), [0x41, 0x42]
        )
        vm.data_stack.clear()
        outer.interpret(": SECOND-BYTE BYTES CHAR+ C@ ;")
        self.assertEqual(outer.interpret("SECOND-BYTE"), [0x42])

    def test_c_store_uses_low_eight_bits(self) -> None:
        vm, dictionary, outer = build_outer()
        outer.interpret("CREATE BYTE 0 C,")
        entry = dictionary.find("BYTE")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(outer.interpret("0x1FF BYTE C! BYTE C@"), [0xFF])
        self.assertEqual(vm.memory[entry.payload], 0xFF)

    def test_chars_is_identity_and_char_plus_wraps(self) -> None:
        vm, _dictionary, outer = build_outer()
        self.assertEqual(outer.interpret("5 CHARS 5 CHAR+"), [5, 6])
        vm.data_stack.clear()
        self.assertEqual(
            outer.interpret("-1 CHARS -1 CHAR+"), [CELL_MASK, 0]
        )

    def test_comma_realigns_after_character_data(self) -> None:
        vm, dictionary, outer = build_outer()
        outer.interpret("CREATE MIXED 0xAA C, 0x11223344 ,")
        entry = dictionary.find("MIXED")
        self.assertIsNotNone(entry)
        assert entry is not None
        cell_address = aligned(entry.payload + 1)
        self.assertEqual(vm.memory[entry.payload], 0xAA)
        self.assertEqual(
            bytes(vm.memory[entry.payload + 1 : cell_address]),
            b"\x00" * (cell_address - entry.payload - 1),
        )
        self.assertEqual(vm.read_cell(cell_address), 0x11223344)

    def test_c_comma_full_preserves_value_and_byte(self) -> None:
        vm, dictionary, outer = build_outer(
            limit=DICTIONARY_BASE + 1, install_primitives=False
        )
        outer.interpret("0x141 C,")
        self.assertEqual(vm.memory[DICTIONARY_BASE], 0x41)
        with self.assertRaises(DictionaryFull):
            outer.interpret("0x142 C,")
        self.assertEqual(vm.data_stack, [0x142])
        self.assertEqual(dictionary.here, DICTIONARY_BASE + 1)
        self.assertEqual(vm.memory[DICTIONARY_BASE], 0x41)

    def test_byte_memory_faults_preserve_stack_arguments(self) -> None:
        vm, _dictionary, outer = build_outer()
        with self.assertRaises(MemoryFault):
            outer.interpret("65536 C@")
        self.assertEqual(vm.data_stack, [65536])

        vm.data_stack.clear()
        with self.assertRaises(MemoryFault):
            outer.interpret("7 65536 C!")
        self.assertEqual(vm.data_stack, [7, 65536])

    def test_cell_memory_faults_also_preserve_stack_arguments(self) -> None:
        vm, _dictionary, outer = build_outer()
        with self.assertRaises(MemoryFault):
            outer.interpret("65536 @")
        self.assertEqual(vm.data_stack, [65536])

        vm.data_stack.clear()
        with self.assertRaises(MemoryFault):
            outer.interpret("7 65536 !")
        self.assertEqual(vm.data_stack, [7, 65536])

    def test_character_words_check_stack_depth(self) -> None:
        for source, expected_stack in (
            ("C@", []),
            ("7 C!", [7]),
            ("CHAR+", []),
            ("CHARS", []),
        ):
            with self.subTest(source=source):
                vm, _dictionary, outer = build_outer()
                with self.assertRaises(StackUnderflow):
                    outer.interpret(source)
                self.assertEqual(vm.data_stack, expected_stack)

    def test_type_emits_a_complete_byte_range(self) -> None:
        vm, dictionary, outer = build_outer()
        outer.interpret("CREATE TEXT 0x46 C, 0x4F C, 0x52 C, 0x54 C, 0x48 C,")
        self.assertEqual(outer.interpret("TEXT 5 TYPE"), [])
        self.assertEqual(outer.output, ["FORTH"])
        self.assertEqual(outer.terminal_text, "FORTH")
        self.assertIsNotNone(dictionary.find("TEXT"))

    def test_type_zero_length_does_not_dereference_address(self) -> None:
        vm, _dictionary, outer = build_outer()
        self.assertEqual(outer.interpret("0xFFFFFFFF 0 TYPE"), [])
        self.assertEqual(outer.output, [])

    def test_type_fault_preserves_stack_and_output(self) -> None:
        vm, _dictionary, outer = build_outer()
        outer.interpret("65 EMIT")
        with self.assertRaises(MemoryFault):
            outer.interpret("65534 4 TYPE")
        self.assertEqual(vm.data_stack, [65534, 4])
        self.assertEqual(outer.output, ["A"])

    def test_type_checks_both_stack_arguments(self) -> None:
        for source, expected_stack in (("TYPE", []), ("7 TYPE", [7])):
            with self.subTest(source=source):
                vm, _dictionary, outer = build_outer()
                with self.assertRaises(StackUnderflow):
                    outer.interpret(source)
                self.assertEqual(vm.data_stack, expected_stack)
                self.assertEqual(outer.output, [])

    def test_type_reads_preloaded_read_only_memory(self) -> None:
        flash = MemoryRegion("FLASH", 0x9000, 0x1000, "r", programmable=True)
        bus = RegionMemory(
            0x10000,
            [
                MemoryRegion("CODE", 0, 0x4000, "rwx", programmable=True),
                MemoryRegion("DICTIONARY", 0x4000, 0x4000, "rw"),
                MemoryRegion("DATA", 0x8000, 0x1000, "rw"),
                flash,
            ],
        )
        bus.program(0x9000, b"FORTH")
        vm = Min0CoreForthVM(memory_bus=bus)
        dictionary = RuntimeDictionary(vm)
        install_core_primitives(dictionary)
        outer = OuterInterpreter(vm, dictionary)
        self.assertEqual(outer.interpret("0x9000 5 TYPE"), [])
        self.assertEqual(outer.terminal_text, "FORTH")
        outer.interpret("65 EMIT")
        with self.assertRaises(MemoryFault):
            outer.interpret("0x8FFF 2 TYPE")
        self.assertEqual(vm.data_stack, [0x8FFF, 2])
        self.assertEqual(outer.output, ["FORTH", "A"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
