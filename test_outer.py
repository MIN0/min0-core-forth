import unittest

from min0_core_forth_dictionary import RuntimeDictionary
from min0_core_forth_outer import (
    STATE_COMPILE,
    STATE_INTERPRET,
    CompileStateError,
    OuterInterpreter,
    UnknownWord,
    install_core_primitives,
)
from min0_core_forth_vm import (
    Min0CoreForthVM,
    MemoryRegion,
    Op,
    RegionMemory,
    StackUnderflow,
)


class OuterInterpreterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.vm = Min0CoreForthVM()
        self.dictionary = RuntimeDictionary(self.vm)
        install_core_primitives(self.dictionary)
        self.vm.load(bytes([Op.DUP, Op.MUL, Op.EXIT]), 0x100)
        self.vm.load(bytes([Op.DUP, Op.ADD, Op.EXIT]), 0x110)
        self.dictionary.add_colon("SQUARE", 0x100)
        self.dictionary.add_colon("DOUBLE", 0x110)
        self.outer = OuterInterpreter(self.vm, self.dictionary)

    def test_numbers_and_colon_words(self) -> None:
        self.assertEqual(self.outer.interpret("5 SQUARE 7 DOUBLE"), [25, 14])
        self.assertEqual(self.vm.return_stack, [])

    def test_primitive_execution(self) -> None:
        self.assertEqual(self.outer.interpret("3 DUP *"), [9])

    def test_dot_emits_signed_number_and_consumes_it(self) -> None:
        self.assertEqual(self.outer.interpret("2 3 4 * + ."), [])
        self.assertEqual(self.outer.interpret("2 3 * 4 + ."), [])
        self.assertEqual(self.outer.interpret("0 1 - ."), [])
        self.assertEqual(self.outer.output, ["14", "10", "-1"])

    def test_dot_underflow_does_not_change_output(self) -> None:
        with self.assertRaises(StackUnderflow):
            self.outer.interpret(".")
        self.assertEqual(self.outer.output, [])

    def test_emit_and_cr_build_an_exact_terminal_stream(self) -> None:
        self.assertEqual(self.outer.interpret("65 EMIT 66 EMIT CR"), [])
        self.assertEqual(self.outer.output, ["A", "B", "\n"])
        self.assertEqual(self.outer.terminal_text, "AB\n")

    def test_emit_uses_the_low_eight_bits(self) -> None:
        self.assertEqual(self.outer.interpret("0x141 EMIT 0x1FF EMIT"), [])
        self.assertEqual(self.outer.terminal_text, "Aÿ")

    def test_emit_underflow_does_not_change_output(self) -> None:
        with self.assertRaises(StackUnderflow):
            self.outer.interpret("EMIT")
        self.assertEqual(self.outer.output, [])

    def test_host_words_are_reserved_as_interpret_only_words(self) -> None:
        for name in (".", "EMIT", "CR", "WORDS"):
            with self.subTest(name=name), self.assertRaises(CompileStateError):
                self.outer.interpret(f": {name} DUP ;")
            self.assertEqual(self.outer.state, STATE_INTERPRET)

    def test_words_separates_startup_and_user_definitions(self) -> None:
        self.outer.interpret(": CUBE DUP DUP * * ; : SQUARE DUP + ; WORDS")
        startup, user = self.outer.terminal_text.split(
            "--- ここから先はユーザーが : で定義したワードなどです ---"
        )
        startup_words = startup.split()
        user_words = user.split()

        self.assertIn("WORDS", startup_words)
        self.assertIn("DOUBLE", startup_words)
        self.assertNotIn("SQUARE", startup_words)
        self.assertIn("CUBE", user_words)
        self.assertEqual(user_words.count("SQUARE"), 1)

    def test_words_reports_no_user_words_and_omits_hidden_entries(self) -> None:
        self.dictionary.add_colon("SECRET", 0x100, hidden=True)
        self.outer.interpret("WORDS")
        self.assertIn("（まだありません）", self.outer.terminal_text)
        self.assertNotIn("SECRET", self.outer.terminal_text)

    def test_case_and_line_comment(self) -> None:
        self.assertEqual(self.outer.interpret("8 double \\ ignore\n 2 +"), [18])

    def test_state_persists_across_calls(self) -> None:
        self.outer.interpret("6")
        self.assertEqual(self.outer.interpret("SQUARE"), [36])

    def test_hidden_word_is_unknown(self) -> None:
        self.dictionary.add_colon("SECRET", 0x100, hidden=True)
        with self.assertRaises(UnknownWord):
            self.outer.interpret("SECRET")

    def test_unknown_word_is_reported(self) -> None:
        with self.assertRaises(UnknownWord):
            self.outer.interpret("MISSING")

    def test_interactive_colon_definition(self) -> None:
        initial_code_here = self.outer.code_here
        self.assertEqual(self.outer.interpret(": CUBE DUP DUP * * ; 3 CUBE"), [27])
        cube = self.dictionary.find("CUBE")
        self.assertIsNotNone(cube)
        self.assertEqual(cube.payload, initial_code_here)
        self.assertEqual(
            bytes(self.vm.memory[initial_code_here : self.outer.code_here]),
            bytes([Op.DUP, Op.DUP, Op.MUL, Op.MUL, Op.EXIT]),
        )
        self.assertEqual(self.outer.state, STATE_INTERPRET)

    def test_definition_can_span_input_calls(self) -> None:
        self.outer.interpret(": QUAD")
        self.assertEqual(self.outer.state, STATE_COMPILE)
        self.assertIsNone(self.dictionary.find("QUAD"))
        self.outer.interpret("DOUBLE DOUBLE ;")
        self.assertEqual(self.outer.state, STATE_INTERPRET)
        self.assertEqual(self.outer.interpret("3 QUAD"), [12])

    def test_latest_redefinition_wins(self) -> None:
        self.outer.interpret(": SQUARE DUP + ;")
        self.assertEqual(self.outer.interpret("5 SQUARE"), [10])

    def test_compile_error_rolls_back_dictionary_and_code(self) -> None:
        saved_dictionary_here = self.dictionary.here
        saved_latest = self.dictionary.latest
        saved_code_here = self.outer.code_here
        with self.assertRaises(UnknownWord):
            self.outer.interpret(": BROKEN 1 MISSING ;")
        self.assertEqual(self.outer.state, STATE_INTERPRET)
        self.assertEqual(self.dictionary.here, saved_dictionary_here)
        self.assertEqual(self.dictionary.latest, saved_latest)
        self.assertEqual(self.outer.code_here, saved_code_here)
        self.assertIsNone(self.dictionary.find("BROKEN", include_hidden=True))

    def test_semicolon_outside_definition_is_error(self) -> None:
        with self.assertRaises(CompileStateError):
            self.outer.interpret(";")

    def test_outer_and_dictionary_run_on_separate_memory_regions(self) -> None:
        bus = RegionMemory(
            0x10000,
            [
                MemoryRegion("CODE", 0x0000, 0x8000, "rwx", programmable=True),
                MemoryRegion("DICTIONARY", 0x8000, 0x8000, "rw"),
            ],
        )
        vm = Min0CoreForthVM(memory_bus=bus)
        dictionary = RuntimeDictionary(vm)
        install_core_primitives(dictionary)
        outer = OuterInterpreter(vm, dictionary)

        self.assertEqual(outer.interpret(": SQUARE DUP * ; 5 SQUARE"), [25])
        self.assertIsNotNone(dictionary.find("SQUARE"))
        self.assertGreater(len(bus.region_bytes("DICTIONARY").rstrip(b"\x00")), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
