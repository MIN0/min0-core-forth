import unittest

from min0_core_forth_dictionary import (
    CONSTRUCTOR_ACTION_ALIGN,
    CONSTRUCTOR_ACTION_ALLOT,
    CONSTRUCTOR_ACTION_C_COMMA,
    CONSTRUCTOR_ACTION_COMMA,
    CONSTRUCTOR_ACTION_END,
    KIND_CREATED,
    KIND_DEFINER,
    KIND_DOES,
    DictionaryFull,
    DictionaryError,
    RuntimeDictionary,
)
from min0_core_forth_outer import (
    CompileStateError,
    InvalidExecutionToken,
    OuterInterpreter,
    install_core_primitives,
)
from min0_core_forth_vm import Min0CoreForthVM, MemoryRegion, RegionMemory, StackUnderflow


def make_split_system():
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
        vm, base=0x4000, limit=0x8000, body_base=0x8000, body_limit=0x10000
    )
    install_core_primitives(dictionary)
    return vm, dictionary, OuterInterpreter(vm, dictionary)


class SourceDoesTests(unittest.TestCase):
    def test_defining_word_creates_executable_child(self) -> None:
        vm, dictionary, outer = make_split_system()
        stack = outer.interpret(
            ": MAKER CREATE 7 + DOES> 1 + ; "
            "5 MAKER CHILD CHILD : USE-CHILD CHILD ; USE-CHILD"
        )
        maker = dictionary.find("MAKER")
        child = dictionary.find("CHILD")
        assert maker is not None and child is not None
        plan_address, behavior = dictionary.read_definer_descriptor(maker)
        constructor_steps = dictionary.read_constructor_plan(maker)
        body, child_behavior = dictionary.read_does_descriptor(child)

        self.assertEqual(maker.kind, KIND_DEFINER)
        self.assertEqual(child.kind, KIND_DOES)
        self.assertEqual(body, 0x8000)
        self.assertEqual(child_behavior, behavior)
        self.assertTrue(0x4000 <= plan_address < 0x8000)
        self.assertLess(constructor_steps[0][0], behavior)
        self.assertEqual(constructor_steps[-1][1], CONSTRUCTOR_ACTION_END)
        self.assertEqual(stack, [12, 0x8001, 0x8001])
        self.assertEqual(vm.return_stack, [])
        self.assertEqual(vm.loop_stack, [])

    def test_value_definer_stores_and_fetches_one_cell(self) -> None:
        vm, dictionary, outer = make_split_system()
        stack = outer.interpret(
            ": VALUE: CREATE , DOES> @ ; "
            "123 VALUE: ANSWER ANSWER : GET-ANSWER ANSWER ; GET-ANSWER"
        )
        value_definer = dictionary.find("VALUE:")
        answer = dictionary.find("ANSWER")
        assert value_definer is not None and answer is not None
        plan = dictionary.read_constructor_plan(value_definer)
        body, _behavior = dictionary.read_does_descriptor(answer)

        self.assertEqual(
            [action for _code, action in plan],
            [CONSTRUCTOR_ACTION_COMMA, CONSTRUCTOR_ACTION_END],
        )
        self.assertEqual(body, 0x8000)
        self.assertEqual(vm.read_cell(body), 123)
        self.assertEqual(dictionary.data_here, 0x8004)
        self.assertEqual(stack, [123, 123])

    def test_value_without_initial_value_rolls_back_child(self) -> None:
        vm, dictionary, outer = make_split_system()
        outer.interpret(": VALUE: CREATE , DOES> @ ;")
        saved = (dictionary.here, dictionary.data_here, dictionary.latest)

        with self.assertRaises(StackUnderflow):
            outer.interpret("VALUE: EMPTY")

        self.assertEqual(vm.data_stack, [])
        self.assertEqual((dictionary.here, dictionary.data_here, dictionary.latest), saved)
        self.assertIsNone(dictionary.find("EMPTY", include_hidden=True))

    def test_byte_definer_stores_low_byte_without_alignment(self) -> None:
        vm, dictionary, outer = make_split_system()
        stack = outer.interpret(
            ": BYTE: CREATE C, DOES> C@ ; "
            "0x1AB BYTE: FLAG FLAG"
        )
        byte_definer = dictionary.find("BYTE:")
        flag = dictionary.find("FLAG")
        assert byte_definer is not None and flag is not None
        plan = dictionary.read_constructor_plan(byte_definer)
        body, _behavior = dictionary.read_does_descriptor(flag)

        self.assertEqual(
            [action for _code, action in plan],
            [CONSTRUCTOR_ACTION_C_COMMA, CONSTRUCTOR_ACTION_END],
        )
        self.assertEqual(body, 0x8000)
        self.assertEqual(vm.read_u8(body), 0xAB)
        self.assertEqual(dictionary.data_here, 0x8001)
        self.assertEqual(stack, [0xAB])

    def test_byte_without_initial_value_rolls_back_child(self) -> None:
        vm, dictionary, outer = make_split_system()
        outer.interpret(": BYTE: CREATE C, DOES> C@ ;")
        saved = (dictionary.here, dictionary.data_here, dictionary.latest)

        with self.assertRaises(StackUnderflow):
            outer.interpret("BYTE: EMPTY")

        self.assertEqual(vm.data_stack, [])
        self.assertEqual(
            (dictionary.here, dictionary.data_here, dictionary.latest), saved
        )
        self.assertIsNone(dictionary.find("EMPTY", include_hidden=True))

    def test_buffer_definer_allots_exact_byte_count(self) -> None:
        _vm, dictionary, outer = make_split_system()
        stack = outer.interpret(": BUFFER: CREATE ALLOT ; 5 BUFFER: BUF BUF")
        buffer_definer = dictionary.find("BUFFER:")
        buffer = dictionary.find("BUF")
        assert buffer_definer is not None and buffer is not None
        plan = dictionary.read_constructor_plan(buffer_definer)

        self.assertEqual(
            [action for _code, action in plan],
            [CONSTRUCTOR_ACTION_ALLOT, CONSTRUCTOR_ACTION_END],
        )
        self.assertEqual(buffer.payload, 0x8000)
        self.assertEqual(dictionary.data_here, 0x8005)
        self.assertEqual(stack, [0x8000])

    def test_buffer_rejects_negative_count_and_rolls_back(self) -> None:
        vm, dictionary, outer = make_split_system()
        outer.interpret(": BUFFER: CREATE ALLOT ;")
        saved = (dictionary.here, dictionary.data_here, dictionary.latest)

        with self.assertRaises(DictionaryError):
            outer.interpret("-1 BUFFER: BAD")

        self.assertEqual(vm.data_stack, [0xFFFFFFFF])
        self.assertEqual(
            (dictionary.here, dictionary.data_here, dictionary.latest), saved
        )
        self.assertIsNone(dictionary.find("BAD", include_hidden=True))

    def test_buffer_without_count_rolls_back_child(self) -> None:
        vm, dictionary, outer = make_split_system()
        outer.interpret(": BUFFER: CREATE ALLOT ;")
        saved = (dictionary.here, dictionary.data_here, dictionary.latest)

        with self.assertRaises(StackUnderflow):
            outer.interpret("BUFFER: EMPTY")

        self.assertEqual(vm.data_stack, [])
        self.assertEqual(
            (dictionary.here, dictionary.data_here, dictionary.latest), saved
        )
        self.assertIsNone(dictionary.find("EMPTY", include_hidden=True))

    def test_buffer_capacity_failure_preserves_count_and_rolls_back(self) -> None:
        bus = RegionMemory(
            0x10000,
            [
                MemoryRegion("CODE", 0, 0x4000, "rwx", programmable=True),
                MemoryRegion("DICTIONARY", 0x4000, 0x4000, "rw"),
                MemoryRegion("DATA", 0x8000, 2, "rw"),
            ],
        )
        vm = Min0CoreForthVM(memory_bus=bus)
        dictionary = RuntimeDictionary(
            vm, base=0x4000, limit=0x8000, body_base=0x8000, body_limit=0x8002
        )
        install_core_primitives(dictionary)
        outer = OuterInterpreter(vm, dictionary)
        outer.interpret(": BUFFER: CREATE ALLOT ;")
        saved = (dictionary.here, dictionary.data_here, dictionary.latest)

        with self.assertRaises(DictionaryFull):
            outer.interpret("3 BUFFER: LARGE")

        self.assertEqual(vm.data_stack, [3])
        self.assertEqual(
            (dictionary.here, dictionary.data_here, dictionary.latest), saved
        )
        self.assertIsNone(dictionary.find("LARGE", include_hidden=True))

    def test_record_combines_byte_allocation_and_alignment(self) -> None:
        vm, dictionary, outer = make_split_system()
        stack = outer.interpret(
            ": RECORD: CREATE C, ALLOT ALIGN ; "
            "2 0x1AB RECORD: ITEM ITEM"
        )
        record_definer = dictionary.find("RECORD:")
        item = dictionary.find("ITEM")
        assert record_definer is not None and item is not None
        plan = dictionary.read_constructor_plan(record_definer)

        self.assertEqual(
            [action for _code, action in plan],
            [
                CONSTRUCTOR_ACTION_C_COMMA,
                CONSTRUCTOR_ACTION_ALLOT,
                CONSTRUCTOR_ACTION_ALIGN,
                CONSTRUCTOR_ACTION_END,
            ],
        )
        self.assertEqual(item.payload, 0x8000)
        self.assertEqual(vm.read_u8(item.payload), 0xAB)
        self.assertEqual(vm.read_bytes(0x8001, 3), b"\x00\x00\x00")
        self.assertEqual(dictionary.data_here, 0x8004)
        self.assertEqual(stack, [0x8000])

    def test_alignment_capacity_failure_rolls_back_all_prior_actions(self) -> None:
        bus = RegionMemory(
            0x10000,
            [
                MemoryRegion("CODE", 0, 0x4000, "rwx", programmable=True),
                MemoryRegion("DICTIONARY", 0x4000, 0x4000, "rw"),
                MemoryRegion("DATA", 0x8000, 3, "rw"),
            ],
        )
        vm = Min0CoreForthVM(memory_bus=bus)
        dictionary = RuntimeDictionary(
            vm, base=0x4000, limit=0x8000, body_base=0x8000, body_limit=0x8003
        )
        install_core_primitives(dictionary)
        outer = OuterInterpreter(vm, dictionary)
        outer.interpret(": RECORD: CREATE C, ALLOT ALIGN ;")
        saved = (dictionary.here, dictionary.data_here, dictionary.latest)

        with self.assertRaises(DictionaryFull):
            outer.interpret("2 0x1AB RECORD: BAD")

        self.assertEqual(vm.data_stack, [2, 0x1AB])
        self.assertEqual(vm.read_bytes(0x8000, 3), b"\x00\x00\x00")
        self.assertEqual(
            (dictionary.here, dictionary.data_here, dictionary.latest), saved
        )
        self.assertIsNone(dictionary.find("BAD", include_hidden=True))

    def test_create_without_does_makes_ordinary_created_child(self) -> None:
        _vm, dictionary, outer = make_split_system()
        stack = outer.interpret(": MAKER CREATE ; MAKER PLAIN PLAIN")
        maker = dictionary.find("MAKER")
        plain = dictionary.find("PLAIN")
        assert maker is not None and plain is not None

        self.assertEqual(maker.kind, KIND_DEFINER)
        self.assertEqual(dictionary.read_definer_descriptor(maker)[1], 0)
        self.assertEqual(plain.kind, KIND_CREATED)
        self.assertEqual(stack, [0x8000])

    def test_definer_requires_name_and_cannot_be_compiled(self) -> None:
        _vm, dictionary, outer = make_split_system()
        outer.interpret(": MAKER CREATE DOES> ;")
        maker = dictionary.find("MAKER")
        assert maker is not None

        with self.assertRaises(CompileStateError):
            outer.interpret("MAKER")
        with self.assertRaises(CompileStateError):
            outer.interpret(": BAD MAKER ;")
        with self.assertRaises(InvalidExecutionToken):
            outer.execute(maker)
        self.assertIsNone(dictionary.find("BAD", include_hidden=True))

    def test_malformed_definer_rolls_back_dictionary_and_code(self) -> None:
        _vm, dictionary, outer = make_split_system()
        saved = (dictionary.here, dictionary.data_here, dictionary.latest, outer.code_here)
        for source in (
            ": BAD 1 CREATE DOES> ;",
            ": BAD DOES> ;",
            ": BAD CREATE DOES> DOES> ;",
            ": BAD CREATE IF DOES> THEN ;",
        ):
            with self.subTest(source=source):
                with self.assertRaises(CompileStateError):
                    outer.interpret(source)
                self.assertEqual(
                    (dictionary.here, dictionary.data_here, dictionary.latest, outer.code_here),
                    saved,
                )
                self.assertIsNone(dictionary.find("BAD", include_hidden=True))

    def test_child_allocation_failure_restores_stack_and_dictionary(self) -> None:
        vm = Min0CoreForthVM()
        dictionary = RuntimeDictionary(vm, limit=0x8034)
        outer = OuterInterpreter(vm, dictionary)
        outer.interpret(": MAKER CREATE DOES> ;")
        saved = (dictionary.here, dictionary.data_here, dictionary.latest)
        vm.push(123)

        with self.assertRaises(DictionaryFull):
            outer.interpret("MAKER CHILD")

        self.assertEqual(vm.data_stack, [123])
        self.assertEqual((dictionary.here, dictionary.data_here, dictionary.latest), saved)
        self.assertIsNone(dictionary.find("CHILD", include_hidden=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
