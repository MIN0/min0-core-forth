import unittest

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import (
    STATE_DIRECT_LOOP,
    STATE_INTERPRET,
    CompileStateError,
    OuterInterpreter,
    install_core_primitives,
)
from min0_core_forth_vm import Min0CoreForthVM, LoopStackOverflow, Op


def build_outer(
    *, max_loop_depth: int = 32, direct_token_limit: int = 4096
) -> tuple[Min0CoreForthVM, RuntimeDictionary, OuterInterpreter]:
    vm = Min0CoreForthVM(max_loop_depth=max_loop_depth)
    dictionary = RuntimeDictionary(vm)
    install_core_primitives(dictionary)
    return vm, dictionary, OuterInterpreter(
        vm, dictionary, direct_token_limit=direct_token_limit
    )


class CountedLoopTests(unittest.TestCase):
    def test_do_loop_and_i(self) -> None:
        vm, _dictionary, outer = build_outer()
        outer.interpret(": INDEXES 5 0 DO I LOOP ;")
        self.assertEqual(outer.interpret("INDEXES"), [0, 1, 2, 3, 4])
        self.assertEqual(vm.loop_stack, [])
        self.assertEqual(
            bytes(vm.memory[0x1000 : outer.code_here]).hex(),
            "010500000001000000001517160b10000003",
        )

    def test_nonzero_start(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret(": RANGE 5 2 DO I LOOP ;")
        self.assertEqual(outer.interpret("RANGE"), [2, 3, 4])

    def test_nested_do_loop_uses_innermost_i(self) -> None:
        vm, _dictionary, outer = build_outer()
        outer.interpret(": GRID 2 0 DO 3 0 DO I LOOP LOOP ;")
        self.assertEqual(outer.interpret("GRID"), [0, 1, 2, 0, 1, 2])
        self.assertEqual(vm.loop_stack, [])

    def test_do_loop_can_span_inputs(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret(": THREE 3 0 DO")
        outer.interpret("I")
        outer.interpret("LOOP ;")
        self.assertEqual(outer.interpret("THREE"), [0, 1, 2])

    def test_unloop_opcode_removes_frame(self) -> None:
        vm = Min0CoreForthVM()
        program = bytes(
            [
                Op.LIT, 2, 0, 0, 0,
                Op.LIT, 0, 0, 0, 0,
                Op.DO,
                Op.UNLOOP,
                Op.HALT,
            ]
        )
        vm.load(program)
        self.assertEqual(vm.run(), [])
        self.assertEqual(vm.loop_stack, [])

    def test_nested_loop_limit_is_checked(self) -> None:
        vm, _dictionary, outer = build_outer(max_loop_depth=1)
        outer.interpret(": NESTED 2 0 DO 2 0 DO I LOOP LOOP ;")
        with self.assertRaises(LoopStackOverflow):
            outer.interpret("NESTED")
        self.assertEqual(vm.data_stack, [])
        self.assertEqual(vm.return_stack, [])
        self.assertEqual(vm.loop_stack, [])

    def test_malformed_do_loop_rolls_back(self) -> None:
        for source in (": BAD DO ;", ": BAD LOOP ;", ": BAD DO IF LOOP THEN ;"):
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

    def test_direct_do_collects_and_unmatched_loop_is_rejected(self) -> None:
        _vm, _dictionary, outer = build_outer()
        self.assertEqual(outer.interpret("3 0 DO"), [])
        self.assertTrue(outer.awaiting_direct_control)
        with self.assertRaisesRegex(CompileStateError, "matching LOOP"):
            outer.finish_input()
        self.assertEqual(outer.vm.data_stack, [])
        with self.assertRaisesRegex(CompileStateError, "direct DO"):
            outer.interpret("LOOP")

    def test_compiled_for_next_matches_direct_for_next(self) -> None:
        _vm, _dictionary, outer = build_outer()
        self.assertEqual(outer.interpret("3 FOR I NEXT"), [0, 1, 2])
        outer.vm.data_stack.clear()
        outer.interpret(": INDEXES 3 FOR I NEXT ;")
        self.assertEqual(outer.interpret("INDEXES"), [0, 1, 2])

    def test_for_zero_iterations_skips_its_body(self) -> None:
        _vm, _dictionary, outer = build_outer()
        self.assertEqual(outer.interpret("0 FOR 99 NEXT"), [])
        outer.interpret(": ZERO 0 FOR 99 NEXT ;")
        self.assertEqual(outer.interpret("ZERO"), [])

    def test_direct_for_can_span_inputs_and_emit_output(self) -> None:
        vm, _dictionary, outer = build_outer()
        self.assertEqual(outer.interpret("3 FOR"), [])
        self.assertEqual(outer.state, STATE_DIRECT_LOOP)
        self.assertTrue(outer.awaiting_direct_loop)
        self.assertEqual(outer.interpret("I ."), [])
        self.assertEqual(outer.state, STATE_DIRECT_LOOP)
        self.assertEqual(outer.interpret("NEXT"), [])
        self.assertEqual(outer.state, STATE_INTERPRET)
        self.assertFalse(outer.awaiting_direct_loop)
        self.assertEqual(outer.terminal_text, "012")
        self.assertEqual(vm.loop_stack, [])

    def test_nested_direct_for_uses_i_and_j(self) -> None:
        vm, _dictionary, outer = build_outer()
        expected = [0, 0, 0, 1, 0, 2, 1, 0, 1, 1, 1, 2]
        self.assertEqual(outer.interpret("2 FOR 3 FOR J I NEXT NEXT"), expected)
        self.assertEqual(vm.loop_stack, [])
        vm.data_stack.clear()
        outer.interpret(": GRID 2 FOR 3 FOR J I NEXT NEXT ;")
        self.assertEqual(outer.interpret("GRID"), expected)

    def test_leave_can_exit_a_compiled_for(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret(": STOP 5 FOR I DUP 2 = IF LEAVE THEN NEXT ;")
        self.assertEqual(outer.interpret("STOP"), [0, 1, 2])

    def test_unfinished_direct_for_can_be_rejected_at_eof(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret("3 FOR I")
        with self.assertRaisesRegex(CompileStateError, "matching NEXT"):
            outer.finish_input()
        self.assertEqual(outer.state, STATE_INTERPRET)
        self.assertEqual(outer.vm.data_stack, [])

    def test_direct_for_buffer_and_depth_limits_roll_back(self) -> None:
        _vm, _dictionary, outer = build_outer(direct_token_limit=2)
        with self.assertRaisesRegex(CompileStateError, "exceeds 2 tokens"):
            outer.interpret("3 FOR 1 2 3")
        self.assertEqual(outer.state, STATE_INTERPRET)
        self.assertEqual(outer.vm.data_stack, [])

        vm, _dictionary, outer = build_outer(max_loop_depth=1)
        with self.assertRaises(LoopStackOverflow):
            outer.interpret("2 FOR 2 FOR I NEXT NEXT")
        self.assertEqual(vm.data_stack, [])
        self.assertEqual(vm.loop_stack, [])

    def test_direct_for_supports_nested_if(self) -> None:
        _vm, _dictionary, outer = build_outer()
        self.assertEqual(
            outer.interpret("3 FOR I DUP 1 = IF 9 ELSE 8 THEN NEXT"),
            [0, 8, 1, 9, 2, 8],
        )

    def test_compiled_for_structure_errors_roll_back(self) -> None:
        for source in (": BAD FOR ;", ": BAD NEXT ;", ": BAD FOR IF NEXT THEN ;"):
            with self.subTest(source=source):
                _vm, dictionary, outer = build_outer()
                with self.assertRaises(CompileStateError):
                    outer.interpret(source)
                self.assertEqual(outer.state, STATE_INTERPRET)
                self.assertIsNone(dictionary.find("BAD", include_hidden=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
