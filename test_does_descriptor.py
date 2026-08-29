import unittest

from min0_core_forth_dictionary import (
    KIND_DOES,
    DictionaryError,
    DictionaryFull,
    RuntimeDictionary,
)
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Min0CoreForthVM, MemoryRegion, Op, RegionMemory


def make_split_dictionary(*, dictionary_limit: int = 0x8000):
    bus = RegionMemory(
        0x10000,
        [
            MemoryRegion("CODE", 0x0000, 0x4000, "rwx", programmable=True),
            MemoryRegion("DICTIONARY", 0x4000, 0x4000, "rw"),
            MemoryRegion("DATA", 0x8000, 0x8000, "rw"),
        ],
    )
    vm = Min0CoreForthVM(memory_bus=bus)
    dictionary = RuntimeDictionary(
        vm,
        base=0x4000,
        limit=dictionary_limit,
        body_base=0x8000,
        body_limit=0x10000,
    )
    return vm, dictionary


class DoesDescriptorTests(unittest.TestCase):
    def test_flat_dictionary_uses_the_same_descriptor_semantics(self) -> None:
        vm = Min0CoreForthVM()
        dictionary = RuntimeDictionary(vm)
        install_core_primitives(dictionary)
        outer = OuterInterpreter(vm, dictionary)
        outer.interpret("CREATE ITEM 5 , : TWICE-BODY @ 2 * ;")
        item = dictionary.find("ITEM")
        behavior = dictionary.find("TWICE-BODY")
        assert item is not None and behavior is not None

        transformed = dictionary.set_does(item, behavior.payload)

        self.assertEqual(dictionary.read_does_descriptor(transformed)[0], item.payload)
        self.assertEqual(outer.interpret("ITEM"), [10])

    def test_interpret_and_compiled_calls_use_separate_body_and_code(self) -> None:
        vm, dictionary = make_split_dictionary()
        install_core_primitives(dictionary)
        outer = OuterInterpreter(vm, dictionary)
        outer.interpret("CREATE COUNTER 41 , : READ-PLUS-ONE @ 1 + ;")
        counter = dictionary.find("COUNTER")
        behavior = dictionary.find("READ-PLUS-ONE")
        assert counter is not None and behavior is not None

        transformed = dictionary.set_does(counter, behavior.payload)
        body_address, code_address = dictionary.read_does_descriptor(transformed)

        self.assertEqual(transformed.kind, KIND_DOES)
        self.assertEqual(body_address, 0x8000)
        self.assertEqual(code_address, behavior.payload)
        self.assertTrue(0x4000 <= transformed.payload < 0x8000)
        self.assertTrue(0x0000 <= code_address < 0x4000)
        self.assertEqual(outer.interpret("COUNTER"), [42])

        vm.data_stack.clear()
        self.assertEqual(
            outer.interpret(": USE-COUNTER COUNTER ; USE-COUNTER"), [42]
        )

    def test_non_created_and_non_executable_targets_are_rejected(self) -> None:
        vm, dictionary = make_split_dictionary()
        install_core_primitives(dictionary)
        outer = OuterInterpreter(vm, dictionary)
        outer.interpret("CREATE ITEM 7 , : BEHAVIOR @ ; 9 CONSTANT NINE")
        item = dictionary.find("ITEM")
        nine = dictionary.find("NINE")
        assert item is not None and nine is not None
        saved = (dictionary.here, dictionary.latest, vm.read_bytes(item.xt, 8))

        with self.assertRaises(DictionaryError):
            dictionary.set_does(item, 0x4000)
        self.assertEqual(
            (dictionary.here, dictionary.latest, vm.read_bytes(item.xt, 8)), saved
        )

        with self.assertRaises(DictionaryError):
            dictionary.set_does(nine, 0x1000)

    def test_descriptor_full_leaves_created_word_unchanged(self) -> None:
        vm, dictionary = make_split_dictionary(dictionary_limit=0x4014)
        vm.write_u8(0x1000, int(Op.EXIT))
        created = dictionary.add_created("X")
        saved = (dictionary.here, dictionary.latest, vm.read_bytes(created.xt, 8))

        with self.assertRaises(DictionaryFull):
            dictionary.set_does(created, 0x1000)

        self.assertEqual(
            (dictionary.here, dictionary.latest, vm.read_bytes(created.xt, 8)), saved
        )
        self.assertEqual(dictionary.find("X").kind, created.kind)


if __name__ == "__main__":
    unittest.main(verbosity=2)
