import unittest

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import (
    STATE_INTERPRET,
    CompileStateError,
    OuterInterpreter,
    install_core_primitives,
)
from min0_core_forth_vm import (
    Assembler,
    Min0CoreForthVM,
    LoopStackUnderflow,
    Op,
    StepLimitExceeded,
    signed,
)


def build_outer() -> tuple[Min0CoreForthVM, RuntimeDictionary, OuterInterpreter]:
    vm = Min0CoreForthVM()
    dictionary = RuntimeDictionary(vm)
    install_core_primitives(dictionary)
    return vm, dictionary, OuterInterpreter(vm, dictionary)


class ExtendedCountedLoopTests(unittest.TestCase):
    def test_plus_loop_positive_increment_and_crossing(self) -> None:
        vm, _dictionary, outer = build_outer()
        outer.interpret(": EVENS 10 0 DO I 2 +LOOP ;")
        self.assertEqual(outer.interpret("EVENS"), [0, 2, 4, 6, 8])
        vm.data_stack.clear()
        outer.interpret(": THREES 10 0 DO I 3 +LOOP ;")
        self.assertEqual(outer.interpret("THREES"), [0, 3, 6, 9])
        self.assertEqual(vm.loop_stack, [])

    def test_plus_loop_negative_increment(self) -> None:
        vm, _dictionary, outer = build_outer()
        outer.interpret(": DOWN -5 0 DO I -1 +LOOP ;")
        self.assertEqual(
            [signed(value) for value in outer.interpret("DOWN")],
            [0, -1, -2, -3, -4],
        )
        self.assertEqual(vm.loop_stack, [])

    def test_zero_increment_is_caught_by_step_limit(self) -> None:
        assembler = Assembler()
        assembler.emit(Op.LIT, 5)
        assembler.emit(Op.LIT, 0)
        assembler.emit(Op.DO)
        assembler.label("body")
        assembler.emit(Op.LIT, 0)
        assembler.emit(Op.PLOOP, "body")
        assembler.emit(Op.HALT)
        vm = Min0CoreForthVM()
        vm.load(assembler.build())
        with self.assertRaises(StepLimitExceeded):
            vm.run(max_steps=20)

    def test_question_do_zero_trip_and_normal_trip(self) -> None:
        vm, _dictionary, outer = build_outer()
        outer.interpret(": ZERO 0 0 ?DO I LOOP ;")
        self.assertEqual(outer.interpret("ZERO"), [])
        outer.interpret(": THREE 3 0 ?DO I LOOP ;")
        self.assertEqual(outer.interpret("THREE"), [0, 1, 2])
        self.assertEqual(vm.loop_stack, [])

    def test_j_reports_outer_loop_index(self) -> None:
        vm, _dictionary, outer = build_outer()
        outer.interpret(": PAIRS 2 0 DO 3 0 DO J I LOOP LOOP ;")
        self.assertEqual(
            outer.interpret("PAIRS"),
            [0, 0, 0, 1, 0, 2, 1, 0, 1, 1, 1, 2],
        )
        self.assertEqual(vm.loop_stack, [])

    def test_j_underflow_restores_stacks(self) -> None:
        vm, _dictionary, outer = build_outer()
        with self.assertRaises(LoopStackUnderflow):
            outer.interpret("J")
        self.assertEqual(vm.data_stack, [])
        self.assertEqual(vm.return_stack, [])
        self.assertEqual(vm.loop_stack, [])

    def test_leave_exits_innermost_loop(self) -> None:
        vm, _dictionary, outer = build_outer()
        outer.interpret(": STOP 10 0 DO I DUP 3 = IF LEAVE THEN LOOP ;")
        self.assertEqual(outer.interpret("STOP"), [0, 1, 2, 3])
        vm.data_stack.clear()
        outer.interpret(
            ": INNERLEAVE 2 0 DO 5 0 DO I 1 = IF LEAVE THEN LOOP I LOOP ;"
        )
        self.assertEqual(outer.interpret("INNERLEAVE"), [0, 1])
        self.assertEqual(vm.loop_stack, [])

    def test_extended_loop_errors_roll_back_definition(self) -> None:
        sources = (
            ": BAD ?DO ;",
            ": BAD +LOOP ;",
            ": BAD LEAVE ;",
            ": BAD DO IF LEAVE THEN ;",
        )
        for source in sources:
            with self.subTest(source=source):
                _vm, dictionary, outer = build_outer()
                saved_here = dictionary.here
                saved_code_here = outer.code_here
                with self.assertRaises(CompileStateError):
                    outer.interpret(source)
                self.assertEqual(outer.state, STATE_INTERPRET)
                self.assertEqual(outer.control_stack, [])
                self.assertEqual(dictionary.here, saved_here)
                self.assertEqual(outer.code_here, saved_code_here)
                self.assertIsNone(dictionary.find("BAD", include_hidden=True))

    def test_extended_control_words_are_compile_only(self) -> None:
        _vm, _dictionary, outer = build_outer()
        for token in ("?DO", "+LOOP", "LEAVE"):
            with self.subTest(token=token), self.assertRaises(CompileStateError):
                outer.interpret(token)


if __name__ == "__main__":
    unittest.main(verbosity=2)
