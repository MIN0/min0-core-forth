import unittest

from min0_core_forth_dictionary import DictionaryFull, RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import Min0CoreForthVM, MemoryRegion, RegionMemory


def make_split_dictionary(*, body_limit: int = 0x10000):
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
        vm, base=0x4000, limit=0x8000, body_base=0x8000, body_limit=body_limit
    )
    return vm, dictionary


class SplitDictionaryTests(unittest.TestCase):
    def test_created_and_variable_bodies_use_data_region(self) -> None:
        vm, dictionary = make_split_dictionary()
        install_core_primitives(dictionary)
        outer = OuterInterpreter(vm, dictionary)

        stack = outer.interpret(
            "CREATE TABLE 10 , 20 , VARIABLE FLAG "
            ": SUM-TABLE TABLE @ TABLE CELL+ @ + ; "
            "SUM-TABLE DUP FLAG ! FLAG @ TABLE"
        )
        table = dictionary.find("TABLE")
        flag = dictionary.find("FLAG")
        self.assertIsNotNone(table)
        self.assertIsNotNone(flag)
        assert table is not None and flag is not None
        self.assertEqual(table.payload, 0x8000)
        self.assertEqual(flag.payload, 0x8008)
        self.assertLess(table.header_address, 0x8000)
        self.assertLess(flag.header_address, 0x8000)
        self.assertEqual(dictionary.data_here, 0x800C)
        self.assertEqual(dictionary.body_image(), bytes.fromhex("0a000000140000001e000000"))
        self.assertEqual(stack, [30, 30, 0x8000])

    def test_variable_failure_rolls_back_header_and_body_allocators(self) -> None:
        vm, dictionary = make_split_dictionary(body_limit=0x8002)
        saved = (dictionary.here, dictionary.data_here, dictionary.latest)

        with self.assertRaises(DictionaryFull):
            dictionary.add_variable("TOO-BIG")

        self.assertEqual(
            (dictionary.here, dictionary.data_here, dictionary.latest), saved
        )
        self.assertIsNone(dictionary.find("TOO-BIG", include_hidden=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
