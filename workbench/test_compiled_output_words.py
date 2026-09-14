import unittest

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import OuterInterpreter, install_core_primitives
from min0_core_forth_vm import MemoryFault, Min0CoreForthVM, StackUnderflow


def build_outer(*, max_data_depth: int = 256) -> OuterInterpreter:
    vm = Min0CoreForthVM(max_data_depth=max_data_depth)
    dictionary = RuntimeDictionary(vm)
    install_core_primitives(dictionary)
    return OuterInterpreter(vm, dictionary)


class CompiledOutputWordTests(unittest.TestCase):
    def test_emit_cr_and_dot_match_direct_execution(self) -> None:
        direct = build_outer()
        self.assertEqual(direct.interpret("65 EMIT CR -42 ."), [])

        compiled = build_outer()
        compiled.interpret(": OUTPUT 65 EMIT CR -42 . ;")
        self.assertEqual(compiled.interpret("OUTPUT"), [])
        self.assertEqual(compiled.output, direct.output)
        self.assertEqual(compiled.terminal_text, "A\n-42")

    def test_compiled_type_consumes_compiled_string_range(self) -> None:
        outer = build_outer()
        outer.interpret(': SAY-ABC S" ABC" TYPE ;')
        self.assertEqual(outer.interpret("SAY-ABC"), [])
        self.assertEqual(outer.terminal_text, "ABC")

    def test_compiled_emit_runs_inside_counted_loop(self) -> None:
        outer = build_outer()
        outer.interpret(": DIGITS 3 FOR I 48 + EMIT NEXT ;")
        self.assertEqual(outer.interpret("DIGITS"), [])
        self.assertEqual(outer.terminal_text, "012")

    def test_compiled_output_faults_preserve_arguments_and_output(self) -> None:
        outer = build_outer()
        outer.interpret(": NEED-CHAR EMIT ;")
        outer.interpret("65 EMIT")
        with self.assertRaises(StackUnderflow):
            outer.interpret("NEED-CHAR")
        self.assertEqual(outer.vm.data_stack, [])
        self.assertEqual(outer.terminal_text, "A")

        outer.interpret(": OUT-RANGE TYPE ;")
        outer.vm.data_stack[:] = [65534, 4]
        with self.assertRaises(MemoryFault):
            outer.interpret("OUT-RANGE")
        self.assertEqual(outer.vm.data_stack, [65534, 4])
        self.assertEqual(outer.terminal_text, "A")

    def test_compiled_cr_uses_no_temporary_data_stack_cell(self) -> None:
        outer = build_outer(max_data_depth=1)
        outer.interpret(": NEWLINE CR ;")
        outer.interpret("7")
        self.assertEqual(outer.interpret("NEWLINE"), [7])
        self.assertEqual(outer.terminal_text, "\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
