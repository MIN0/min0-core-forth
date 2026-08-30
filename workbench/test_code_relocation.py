import unittest

from code_relocation_demo import run_demo
from constructor_image_fixture import make_system
from min0_core_forth_outer import CompileStateError, OuterInterpreter, install_core_primitives
from full_image_relocation_demo import run_demo as run_full_image_demo


class CodeRelocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_demo()

    def test_mixed_compilation_emits_typed_manifest(self) -> None:
        self.assertEqual(len(self.result["manifest"]), 15)
        self.assertEqual(
            self.result["kind_counts"],
            {
                "branch": 2,
                "call": 2,
                "data-literal": 1,
                "does-body": 1,
                "does-call": 1,
                "leave": 1,
                "loop": 2,
                "ploop": 1,
                "qdo": 1,
                "zbranch": 3,
            },
        )
        self.assertEqual(
            self.result["target_counts"],
            {"code": 13, "dictionary": 0, "data": 2},
        )
        for record in self.result["manifest"]:
            self.assertEqual(record["section"], "code")
            self.assertEqual(record["width"], 4)

    def test_compiled_words_still_execute(self) -> None:
        self.assertEqual(
            self.result["stack"],
            [99, 2, 3, 3, 0, 2, 7, 0x8000],
        )
        self.assertEqual(self.result["slot"], 0x8000)
        self.assertEqual(self.result["answer"], 0x8004)

    def test_failed_definition_rolls_back_manifest(self) -> None:
        vm, dictionary = make_system()
        install_core_primitives(dictionary)
        outer = OuterInterpreter(vm, dictionary)
        outer.interpret(": GOOD IF 1 THEN ;")
        before = outer.relocation_manifest()
        with self.assertRaises(CompileStateError):
            outer.interpret(": BAD IF ;")
        self.assertEqual(outer.relocation_manifest(), before)

    def test_manifest_relocates_and_executes_full_image(self) -> None:
        result = run_full_image_demo()
        self.assertEqual(result["code_relocations"], 15)
        self.assertEqual(result["dictionary_relocations"], 53)
        self.assertEqual(
            result["dictionary_targets"],
            {"code": 12, "dictionary": 39, "data": 2},
        )
        self.assertEqual(result["stack"], [99, 2, 3, 3, 0, 2, 7, 0x9000])
        self.assertEqual(result["slot"], 0x9000)
        self.assertEqual(result["answer_body"], 0x9004)
        self.assertEqual(result["answer_value"], 7)
        self.assertEqual(result["data_here"], 0x9008)


if __name__ == "__main__":
    unittest.main(verbosity=2)
