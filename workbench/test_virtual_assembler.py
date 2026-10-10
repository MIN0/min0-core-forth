import unittest

from min0_virtual_assembler import (
    ParseError,
    StackUnderflow,
    VerifyError,
    compile_code,
)


SUM_XOR = """\
CODE: SUM-XOR ( a b c -- sum mix )
  IN  V0, a
  IN  V1, b
  IN  V2, c
  MOV V3, V0
  ADD V0, V1
  ADD V0, V2
  XOR V3, V1
  XOR V3, V2
  OUT sum, V0
  OUT mix, V3
;CODE
"""


class VirtualAssemblerTests(unittest.TestCase):
    def test_three_inputs_become_two_outputs(self) -> None:
        definition = compile_code(SUM_XOR)
        before = [10, 20, 30]
        self.assertEqual(definition.execute(before), [60, 0])
        self.assertEqual(before, [10, 20, 30])

    def test_stack_prefix_is_preserved(self) -> None:
        self.assertEqual(compile_code(SUM_XOR).execute([99, 10, 20, 30]), [99, 60, 0])

    def test_32_bit_wrap_and_literal(self) -> None:
        source = """CODE: INC ( x -- y )
        IN V0, x
        LIT V1, 1
        ADD V0, V1
        OUT y, V0
        ;CODE"""
        self.assertEqual(compile_code(source).execute([0xFFFF_FFFF]), [0])

    def test_shift_rotate_and_signed_shift(self) -> None:
        source = """CODE: BITS ( x -- left right signed rotated )
        IN V0, x
        MOV V1, V0
        MOV V2, V0
        MOV V3, V0
        LSL V0, 1
        LSR V1, 1
        ASR V2, 1
        ROR V3, 4
        OUT left, V0
        OUT right, V1
        OUT signed, V2
        OUT rotated, V3
        ;CODE"""
        self.assertEqual(
            compile_code(source).execute([0x8000_0001]),
            [2, 0x4000_0000, 0xC000_0000, 0x1800_0000],
        )

    def test_missing_and_duplicate_outputs_are_rejected(self) -> None:
        with self.assertRaisesRegex(VerifyError, "not assigned"):
            compile_code("CODE: BAD ( x -- y )\n IN V0, x\n ;CODE")
        with self.assertRaisesRegex(VerifyError, "assigned twice"):
            compile_code(
                "CODE: BAD ( x -- y )\n IN V0, x\n OUT y, V0\n OUT y, V0\n ;CODE"
            )

    def test_names_and_register_initialization_are_verified(self) -> None:
        with self.assertRaisesRegex(VerifyError, "unknown input"):
            compile_code("CODE: BAD ( x -- y )\n IN V0, z\n OUT y, V0\n ;CODE")
        with self.assertRaisesRegex(VerifyError, "uninitialized"):
            compile_code("CODE: BAD ( x -- y )\n OUT y, V0\n ;CODE")
        with self.assertRaisesRegex(VerifyError, "unknown output"):
            compile_code("CODE: BAD ( x -- y )\n IN V0, x\n OUT z, V0\n ;CODE")

    def test_invalid_opcode_and_shift_are_rejected(self) -> None:
        with self.assertRaisesRegex(ParseError, "unknown opcode"):
            compile_code("CODE: BAD ( x -- y )\n PUSH V0\n ;CODE")
        with self.assertRaisesRegex(VerifyError, "0..31"):
            compile_code("CODE: BAD ( x -- y )\n IN V0, x\n LSL V0, 32\n OUT y, V0\n ;CODE")

    def test_underflow_does_not_modify_caller_stack(self) -> None:
        before = [10, 20]
        with self.assertRaises(StackUnderflow):
            compile_code(SUM_XOR).execute(before)
        self.assertEqual(before, [10, 20])

    def test_empty_input_and_output_contracts(self) -> None:
        constant = compile_code(
            "CODE: ANSWER ( -- value )\n LIT V0, 42\n OUT value, V0\n ;CODE"
        )
        discard = compile_code("CODE: DISCARD ( value -- )\n ;CODE")
        self.assertEqual(constant.execute([7]), [7, 42])
        self.assertEqual(discard.execute([7, 42]), [7])


if __name__ == "__main__":
    unittest.main(verbosity=2)
