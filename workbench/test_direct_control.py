import unittest

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import (
    STATE_DIRECT_CONTROL,
    STATE_INTERPRET,
    CompileStateError,
    OuterInterpreter,
    install_core_primitives,
)
from min0_core_forth_vm import LoopFrame, Min0CoreForthVM, signed


def build_outer(
    *, direct_token_limit: int = 4096, direct_execution_limit: int = 100_000
) -> OuterInterpreter:
    vm = Min0CoreForthVM()
    dictionary = RuntimeDictionary(vm)
    install_core_primitives(dictionary)
    return OuterInterpreter(
        vm,
        dictionary,
        direct_token_limit=direct_token_limit,
        direct_execution_limit=direct_execution_limit,
    )


class DirectControlTests(unittest.TestCase):
    def test_if_else_then_selects_one_branch(self) -> None:
        outer = build_outer()
        self.assertEqual(outer.interpret("1 IF 10 ELSE 20 THEN"), [10])
        outer.vm.data_stack.clear()
        self.assertEqual(outer.interpret("0 IF 10 ELSE 20 THEN"), [20])

    def test_if_can_span_inputs_and_emit_output(self) -> None:
        outer = build_outer()
        self.assertEqual(outer.interpret("1 IF"), [])
        self.assertEqual(outer.state, STATE_DIRECT_CONTROL)
        self.assertTrue(outer.awaiting_direct_control)
        self.assertEqual(outer.interpret('7 . ." ok"'), [])
        self.assertEqual(outer.interpret("THEN"), [])
        self.assertEqual(outer.state, STATE_INTERPRET)
        self.assertEqual(outer.terminal_text, "7ok")

    def test_nested_if_is_structurally_matched(self) -> None:
        outer = build_outer()
        self.assertEqual(
            outer.interpret("1 IF 0 IF 10 ELSE 20 THEN ELSE 30 THEN"),
            [20],
        )

    def test_begin_until_and_begin_while_repeat(self) -> None:
        outer = build_outer()
        self.assertEqual(outer.interpret("0 BEGIN 1 + DUP 3 = UNTIL"), [3])
        outer.vm.data_stack.clear()
        self.assertEqual(
            outer.interpret("0 BEGIN DUP 3 < WHILE 1 + REPEAT"), [3]
        )

    def test_begin_again_is_bounded(self) -> None:
        outer = build_outer(direct_execution_limit=20)
        with self.assertRaisesRegex(CompileStateError, "execution limit"):
            outer.interpret("BEGIN AGAIN")
        self.assertEqual(outer.state, STATE_INTERPRET)
        self.assertEqual(outer.vm.data_stack, [])

    def test_do_qdo_loop_and_plus_loop(self) -> None:
        outer = build_outer()
        self.assertEqual(outer.interpret("5 2 DO I LOOP"), [2, 3, 4])
        outer.vm.data_stack.clear()
        self.assertEqual(outer.interpret("4 4 ?DO 99 LOOP"), [])
        self.assertEqual(outer.interpret("6 0 DO I 2 +LOOP"), [0, 2, 4])
        outer.vm.data_stack.clear()
        self.assertEqual(
            [signed(value) for value in outer.interpret("-5 0 DO I -1 +LOOP")],
            [0, -1, -2, -3, -4],
        )

    def test_nested_do_and_for_use_i_and_j(self) -> None:
        outer = build_outer()
        self.assertEqual(
            outer.interpret("2 0 DO 2 FOR J I NEXT LOOP"),
            [0, 0, 0, 1, 1, 0, 1, 1],
        )
        self.assertEqual(outer.vm.loop_stack, [])

    def test_leave_exits_innermost_direct_counted_loop(self) -> None:
        outer = build_outer()
        self.assertEqual(
            outer.interpret("5 0 DO I DUP 2 = IF LEAVE THEN LOOP"),
            [0, 1, 2],
        )
        self.assertEqual(outer.vm.loop_stack, [])

    def test_mismatched_structure_rolls_back_without_execution(self) -> None:
        outer = build_outer()
        with self.assertRaisesRegex(CompileStateError, "direct DO"):
            outer.interpret("1 IF 99 . LOOP")
        self.assertEqual(outer.state, STATE_INTERPRET)
        self.assertEqual(outer.vm.data_stack, [])
        self.assertEqual(outer.terminal_text, "")

    def test_unfinished_structure_is_rejected_at_eof(self) -> None:
        outer = build_outer()
        outer.interpret("1 IF 10")
        with self.assertRaisesRegex(CompileStateError, "matching THEN"):
            outer.finish_input()
        self.assertEqual(outer.state, STATE_INTERPRET)
        self.assertEqual(outer.vm.data_stack, [])

    def test_execution_error_restores_preexisting_loop_stack(self) -> None:
        outer = build_outer(direct_execution_limit=20)
        outer.vm.loop_stack.append(LoopFrame(limit=9, index=4))
        with self.assertRaisesRegex(CompileStateError, "execution limit"):
            outer.interpret("BEGIN AGAIN")
        self.assertEqual(
            [(frame.limit, frame.index) for frame in outer.vm.loop_stack],
            [(9, 4)],
        )

    def test_direct_control_can_be_nested_in_direct_for(self) -> None:
        outer = build_outer()
        self.assertEqual(
            outer.interpret("3 FOR I DUP 1 = IF 9 ELSE 8 THEN NEXT"),
            [0, 8, 1, 9, 2, 8],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
