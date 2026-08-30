import unittest

from min0_core_forth_compiler import CompileError, QuotedText, compile_source, tokenize
from min0_core_forth_dictionary import DICTIONARY_BASE, DictionaryFull, RuntimeDictionary
from min0_core_forth_outer import (
    CompileStateError,
    OuterInterpreter,
    UnknownWord,
    install_core_primitives,
)
from min0_core_forth_vm import DataStackOverflow, Min0CoreForthVM


def build_outer(
    *, limit: int | None = None, install_primitives: bool = True,
    max_data_depth: int = 256,
) -> tuple[Min0CoreForthVM, RuntimeDictionary, OuterInterpreter]:
    vm = Min0CoreForthVM(max_data_depth=max_data_depth)
    dictionary = RuntimeDictionary(vm, limit=limit)
    if install_primitives:
        install_core_primitives(dictionary)
    return vm, dictionary, OuterInterpreter(vm, dictionary)


class StringOutputTests(unittest.TestCase):
    def test_tokenizer_preserves_quoted_case_spaces_and_backslash(self) -> None:
        tokens = tokenize('1 s" MiXeD  \\ text" ." done" \\ outside\n2')
        self.assertEqual(
            tokens,
            [
                "1",
                QuotedText('S"', "MiXeD  \\ text"),
                QuotedText('."', "done"),
                "2",
            ],
        )

    def test_s_quote_and_type_preserve_exact_text(self) -> None:
        vm, dictionary, outer = build_outer()
        before = dictionary.data_here
        self.assertEqual(outer.interpret('S" Hello  World"'), [before, 12])
        self.assertEqual(vm.read_bytes(before, 12), b"Hello  World")
        self.assertEqual(outer.interpret("TYPE"), [])
        self.assertEqual(outer.output, ["Hello  World"])

    def test_dot_quote_outputs_without_allocating(self) -> None:
        _vm, dictionary, outer = build_outer()
        before = dictionary.data_here
        self.assertEqual(outer.interpret('." MiXeD Case"'), [])
        self.assertEqual(outer.output, ["MiXeD Case"])
        self.assertEqual(dictionary.data_here, before)

    def test_empty_and_latin_one_strings_follow_byte_model(self) -> None:
        vm, dictionary, outer = build_outer()
        before = dictionary.data_here
        self.assertEqual(outer.interpret('S""'), [before, 0])
        self.assertEqual(dictionary.data_here, before)
        self.assertEqual(outer.interpret("TYPE"), [])
        self.assertEqual(outer.output, [])

        self.assertEqual(outer.interpret('S" café"'), [before, 4])
        self.assertEqual(vm.read_bytes(before, 4), b"caf\xE9")
        self.assertEqual(outer.interpret("TYPE"), [])
        self.assertEqual(outer.terminal_text, "café")

    def test_backslash_inside_quotes_is_data_but_outside_starts_comment(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret('." A\\B" \\ ignored\n ." C"')
        self.assertEqual(outer.output, ["A\\B", "C"])

    def test_unterminated_or_nonbyte_text_changes_nothing(self) -> None:
        vm, dictionary, outer = build_outer()
        before = dictionary.data_here
        with self.assertRaises(CompileError):
            outer.interpret('65 EMIT ." missing')
        self.assertEqual(vm.data_stack, [])
        self.assertEqual(outer.output, [])
        self.assertEqual(dictionary.data_here, before)

        with self.assertRaises(CompileStateError):
            outer.interpret('S" \u0100"')
        self.assertEqual(vm.data_stack, [])
        self.assertEqual(outer.output, [])
        self.assertEqual(dictionary.data_here, before)

    def test_s_quote_capacity_failures_are_atomic(self) -> None:
        vm, dictionary, outer = build_outer(
            limit=DICTIONARY_BASE + 1, install_primitives=False
        )
        before = dictionary.data_here
        with self.assertRaises(DictionaryFull):
            outer.interpret('S" AB"')
        self.assertEqual(vm.data_stack, [])
        self.assertEqual(dictionary.data_here, before)

        vm, dictionary, outer = build_outer(max_data_depth=1)
        before = dictionary.data_here
        with self.assertRaises(DataStackOverflow):
            outer.interpret('S" A"')
        self.assertEqual(vm.data_stack, [])
        self.assertEqual(dictionary.data_here, before)

    def test_compiled_s_quote_pushes_address_and_length(self) -> None:
        vm, dictionary, outer = build_outer()
        outer.interpret(': MESSAGE S" Compiled" ;')
        entry = dictionary.find("MESSAGE")
        self.assertIsNotNone(entry)
        stack = outer.interpret("MESSAGE")
        self.assertEqual(stack[-1], 8)
        self.assertEqual(vm.read_bytes(stack[-2], stack[-1]), b"Compiled")
        self.assertEqual(outer.interpret("TYPE"), [])
        self.assertEqual(outer.terminal_text, "Compiled")
        record = outer.relocation_manifest()[-1]
        self.assertEqual(record["target"], "data")
        self.assertEqual(record["kind"], "string-address")

    def test_compiled_s_quote_supports_multiple_and_empty_literals(self) -> None:
        vm, dictionary, outer = build_outer()
        outer.interpret(': STRINGS S" A" S" BC" S"" ;')
        stack = outer.interpret("STRINGS")
        self.assertEqual([stack[1], stack[3], stack[5]], [1, 2, 0])
        self.assertEqual(vm.read_bytes(stack[0], 1), b"A")
        self.assertEqual(vm.read_bytes(stack[2], 2), b"BC")
        self.assertEqual(stack[4], dictionary.body_base)
        self.assertEqual(
            [record["kind"] for record in outer.relocation_manifest()[-3:]],
            ["string-address", "string-address", "string-address"],
        )

    def test_compiled_dot_quote_outputs_inside_nested_colon_words(self) -> None:
        _vm, _dictionary, outer = build_outer()
        outer.interpret(': HELLO ." Hello" ;')
        outer.interpret(': GREET HELLO ."  World" ."" ;')
        self.assertEqual(outer.interpret("GREET"), [])
        self.assertEqual(outer.output, ["Hello", " World"])
        self.assertEqual(outer.terminal_text, "Hello World")
        records = [
            record
            for record in outer.relocation_manifest()
            if record["kind"] == "string-address"
        ]
        self.assertEqual(len(records), 3)
        self.assertTrue(all(record["target"] == "data" for record in records))

    def test_compiled_string_failures_roll_back(self) -> None:
        vm, dictionary, outer = build_outer()
        before_here = dictionary.here
        before_code = outer.code_here
        before_manifest = outer.relocation_manifest()
        for source, error in (
            (': BAD S" text" MISSING ;', UnknownWord),
            (': BAD ." text" MISSING ;', UnknownWord),
            (': BAD S" \u0100" ;', CompileStateError),
            (': BAD ." \u0100" ;', CompileStateError),
        ):
            with self.subTest(source=source):
                with self.assertRaises(error):
                    outer.interpret(source)
                self.assertIsNone(dictionary.find("BAD"))
                self.assertEqual(dictionary.here, before_here)
                self.assertEqual(outer.code_here, before_code)
                self.assertEqual(outer.relocation_manifest(), before_manifest)
                self.assertEqual(vm.read_bytes(before_here, 8), b"\x00" * 8)

    def test_raw_compiler_rejects_quoted_outer_words_cleanly(self) -> None:
        for source in ('S" text"', '." text"', ': BAD S" text" ;'):
            with self.subTest(source=source):
                with self.assertRaises(CompileError):
                    compile_source(source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
