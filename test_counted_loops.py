import unittest

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import (
    STATE_INTERPRET,
    CompileStateError,
    OuterInterpreter,
    install_core_primitives,
)
from min0_core_forth_vm import Min0CoreForthVM, LoopStackOverflow, Op


def build_outer(
    *, max_loop_depth: int = 32
) -> tuple[Min0CoreForthVM, RuntimeDictionary, OuterInterpreter]:
    vm = Min0CoreForthVM(max_loop_depth=max_loop_depth)
    dictionary = RuntimeDictionary(vm)
    install_core_primitives(dictionary)
    return vm, dictionary, OuterInterpreter(vm, dictionary)


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

    def test_do_and_loop_are_compile_only(self) -> None:
        _vm, _dictionary, outer = build_outer()
        for token in ("DO", "LOOP"):
            with self.subTest(token=token), self.assertRaises(CompileStateError):
                outer.interpret(token)


if __name__ == "__main__":
    unittest.main(verbosity=2)
