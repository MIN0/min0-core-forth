import unittest

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import (
    STATE_INTERPRET,
    CompileStateError,
    OuterInterpreter,
    install_core_primitives,
)
from min0_core_forth_vm import Min0CoreForthVM


def build_outer() -> tuple[Min0CoreForthVM, RuntimeDictionary, OuterInterpreter]:
    vm = Min0CoreForthVM()
    dictionary = RuntimeDictionary(vm)
    install_core_primitives(dictionary)
    return vm, dictionary, OuterInterpreter(vm, dictionary)


class ControlFlowTests(unittest.TestCase):
    def test_if_else_then(self) -> None:
        vm, _dictionary, outer = build_outer()
        outer.interpret(": CHOOSE IF 111 ELSE 222 THEN ;")
        self.assertEqual(outer.interpret("0 CHOOSE 1 CHOOSE"), [222, 111])
        self.assertEqual(
            bytes(vm.memory[0x1000 : outer.code_here]).hex(),
            "050f100000016f000000041410000001de00000003",
        )

    def test_if_then_without_else(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret(": MAYBE IF 7 THEN ;")
        self.assertEqual(outer.interpret("0 MAYBE 1 MAYBE"), [7])

    def test_nested_conditionals(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret(": NEST IF IF 1 ELSE 2 THEN ELSE 3 THEN ;")
        self.assertEqual(outer.interpret("0 NEST 0 1 NEST 1 1 NEST"), [3, 2, 1])

    def test_control_structure_can_span_inputs(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret(": SPLIT IF 10")
        outer.interpret("ELSE 20")
        outer.interpret("THEN ;")
        self.assertEqual(outer.interpret("0 SPLIT 1 SPLIT"), [20, 10])

    def test_unresolved_if_rolls_back_definition(self) -> None:
        _vm, dictionary, outer = build_outer()
        saved_dictionary_here = dictionary.here
        saved_code_here = outer.code_here
        with self.assertRaises(CompileStateError):
            outer.interpret(": BROKEN IF 1 ;")
        self.assertEqual(outer.state, STATE_INTERPRET)
        self.assertEqual(dictionary.here, saved_dictionary_here)
        self.assertEqual(outer.code_here, saved_code_here)
        self.assertEqual(outer.control_stack, [])
        self.assertIsNone(dictionary.find("BROKEN", include_hidden=True))

    def test_else_then_and_if_are_compile_only(self) -> None:
        _vm, _dictionary, outer = build_outer()
        for token in ("IF", "ELSE", "THEN"):
            with self.subTest(token=token), self.assertRaises(CompileStateError):
                outer.interpret(token)

    def test_mismatched_else_rolls_back(self) -> None:
        _vm, dictionary, outer = build_outer()
        with self.assertRaises(CompileStateError):
            outer.interpret(": BAD ELSE ;")
        self.assertIsNone(dictionary.find("BAD", include_hidden=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
