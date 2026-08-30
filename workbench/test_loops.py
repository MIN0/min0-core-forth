import unittest

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import (
    STATE_INTERPRET,
    CompileStateError,
    OuterInterpreter,
    install_core_primitives,
)
from min0_core_forth_vm import Min0CoreForthVM, Op, StepLimitExceeded


def build_outer() -> tuple[Min0CoreForthVM, RuntimeDictionary, OuterInterpreter]:
    vm = Min0CoreForthVM()
    dictionary = RuntimeDictionary(vm)
    install_core_primitives(dictionary)
    return vm, dictionary, OuterInterpreter(vm, dictionary)


class LoopTests(unittest.TestCase):
    def test_begin_until(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret(": COUNTDOWN BEGIN 1 - DUP 0 = UNTIL ;")
        self.assertEqual(outer.interpret("3 COUNTDOWN"), [0])

    def test_begin_while_repeat(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret(": DOWN BEGIN 0 OVER < WHILE 1 - REPEAT ;")
        self.assertEqual(outer.interpret("4 DOWN"), [0])

    def test_begin_again_and_step_limit(self) -> None:
        vm, dictionary, outer = build_outer()
        outer.interpret(": FOREVER BEGIN 1 AGAIN ;")
        forever = dictionary.find("FOREVER")
        self.assertIsNotNone(forever)
        self.assertEqual(
            bytes(vm.memory[0x1000 : outer.code_here]).hex(),
            "0101000000040010000003",
        )
        with self.assertRaises(StepLimitExceeded):
            vm.resume(forever.payload, return_to=outer.return_trampoline, max_steps=20)

    def test_if_nested_inside_loop(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret(
            ": WALK BEGIN DUP 2 = IF 2 - ELSE 1 - THEN DUP 0 = UNTIL ;"
        )
        self.assertEqual(outer.interpret("3 WALK"), [0])

    def test_loop_can_span_input_calls(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret(": DOWN BEGIN")
        outer.interpret("0 OVER < WHILE")
        outer.interpret("1 - REPEAT ;")
        self.assertEqual(outer.interpret("2 DOWN"), [0])

    def test_malformed_loops_roll_back(self) -> None:
        malformed = (
            ": BAD UNTIL ;",
            ": BAD AGAIN ;",
            ": BAD WHILE ;",
            ": BAD REPEAT ;",
            ": BAD BEGIN ;",
            ": BAD BEGIN WHILE 1 UNTIL ;",
            ": BAD BEGIN REPEAT ;",
        )
        for source in malformed:
            with self.subTest(source=source):
                _vm, dictionary, outer = build_outer()
                saved_dictionary_here = dictionary.here
                saved_code_here = outer.code_here
                with self.assertRaises(CompileStateError):
                    outer.interpret(source)
                self.assertEqual(outer.state, STATE_INTERPRET)
                self.assertEqual(outer.control_stack, [])
                self.assertEqual(dictionary.here, saved_dictionary_here)
                self.assertEqual(outer.code_here, saved_code_here)
                self.assertIsNone(dictionary.find("BAD", include_hidden=True))

    def test_loop_words_are_compile_only(self) -> None:
        _vm, _dictionary, outer = build_outer()
        for token in ("BEGIN", "UNTIL", "AGAIN", "WHILE", "REPEAT"):
            with self.subTest(token=token), self.assertRaises(CompileStateError):
                outer.interpret(token)


if __name__ == "__main__":
    unittest.main(verbosity=2)
