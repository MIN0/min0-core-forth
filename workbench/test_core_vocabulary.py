import unittest

from min0_core_forth_vm import DivisionByZero, DivisionOverflow
from min0_forth import make_host


class CoreVocabularyTests(unittest.TestCase):
    def run_source(self, source: str):
        return make_host().interpret(source)

    def test_observation_words(self) -> None:
        host = make_host()
        self.assertEqual(host.interpret("10 20 DEPTH"), [10, 20, 2])
        host.interpret(".S")
        self.assertEqual(host.terminal_text, "<3> 10 20 2")
        self.assertEqual(host.vm.data_stack, [10, 20, 2])

    def test_stack_words(self) -> None:
        self.assertEqual(self.run_source("1 2 3 ROT"), [2, 3, 1])
        self.assertEqual(self.run_source("1 2 2DUP"), [1, 2, 1, 2])
        self.assertEqual(self.run_source("1 2 2DROP"), [])

    def test_numeric_words(self) -> None:
        self.assertEqual(self.run_source("-7 3 /MOD"), [0xFFFFFFFF, 0xFFFFFFFE])
        self.assertEqual(self.run_source("-7 3 /"), [0xFFFFFFFE])
        self.assertEqual(self.run_source("-7 3 MOD"), [0xFFFFFFFF])
        self.assertEqual(self.run_source("-5 ABS NEGATE"), [0xFFFFFFFB])
        self.assertEqual(self.run_source("5 1+ 1-"), [5])
        self.assertEqual(self.run_source("0 0= 1 0="), [0xFFFFFFFF, 0])

    def test_division_errors_are_atomic(self) -> None:
        for source, error, stack in (
            ("7 0 /MOD", DivisionByZero, [7, 0]),
            ("-2147483648 -1 /MOD", DivisionOverflow, [0x80000000, 0xFFFFFFFF]),
        ):
            with self.subTest(source=source):
                host = make_host()
                with self.assertRaises(error):
                    host.interpret(source)
                self.assertEqual(host.vm.data_stack, stack)

    def test_derived_words_are_available_while_compiling(self) -> None:
        self.assertEqual(
            self.run_source(": HALF / ; : CLEAN 2DROP ; -9 2 HALF 4 5 CLEAN"),
            [0xFFFFFFFC],
        )

    def test_words_lists_all_78_candidate_words(self) -> None:
        host = make_host()
        host.interpret("WORDS")
        startup, _user = host.terminal_text.split(
            "--- ここから先はユーザーが : で定義したワードなどです ---"
        )
        listed = {
            word for word in startup.split()
            if word != "起動時から使えるワード"
        }
        self.assertEqual(len(listed), 78)


if __name__ == "__main__":
    unittest.main(verbosity=2)
