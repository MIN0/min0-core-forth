import unittest

from min0_core_forth_compiler import CompileError, compile_source
from min0_core_forth_vm import Min0CoreForthVM


def run(source: str) -> list[int]:
    vm = Min0CoreForthVM()
    vm.load(compile_source(source))
    return vm.run()


class CompilerTests(unittest.TestCase):
    def test_colon_definitions(self) -> None:
        self.assertEqual(
            run(": SQUARE DUP * ; : DOUBLE DUP + ; 5 SQUARE 7 DOUBLE"),
            [25, 14],
        )

    def test_source_is_case_insensitive(self) -> None:
        self.assertEqual(run(": double dup + ; 9 DoUbLe"), [18])

    def test_forward_word_reference(self) -> None:
        self.assertEqual(run(": A B ; : B 41 1 + ; A"), [42])

    def test_comment_and_hex_literal(self) -> None:
        self.assertEqual(run("0x10 \\ ignored\n 2 *"), [32])

    def test_unknown_word_fails_at_compile_time(self) -> None:
        with self.assertRaises(CompileError):
            compile_source("MISSING")

    def test_unterminated_definition_fails(self) -> None:
        with self.assertRaises(CompileError):
            compile_source(": BAD 1 2 +")


if __name__ == "__main__":
    unittest.main(verbosity=2)
