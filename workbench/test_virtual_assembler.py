import unittest

from min0_virtual_assembler import (
    ExecutionError,
    MemoryAccessError,
    MemoryWindow,
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

    def test_comparison_and_branch_select_one_output_path(self) -> None:
        maximum = compile_code("""CODE: MAX ( a b -- max )
        IN V0, a
        IN V1, b
        CMP V0, V1
        BGE @a-wins
        OUT max, V1
        BRA @done
@a-wins:
        OUT max, V0
@done:
        ;CODE""")
        self.assertEqual(maximum.execute([10, 20]), [20])
        self.assertEqual(maximum.execute([30, 20]), [30])

    def test_signed_and_unsigned_comparisons_differ(self) -> None:
        signed_less = compile_code("""CODE: SIGNED-LESS ( a b -- flag )
        IN V0, a
        IN V1, b
        CMP V0, V1
        BLT @yes
        LIT V2, 0
        BRA @result
@yes:
        LIT V2, 1
@result:
        OUT flag, V2
        ;CODE""")
        unsigned_less = signed_less.__class__(
            "UNSIGNED-LESS", signed_less.inputs, signed_less.outputs,
            tuple(
                instruction.__class__(
                    "BLTU" if instruction.opcode == "BLT" else instruction.opcode,
                    instruction.operands, instruction.line,
                )
                for instruction in signed_less.instructions
            ),
        )
        self.assertEqual(signed_less.execute([0xFFFF_FFFF, 1]), [1])
        self.assertEqual(unsigned_less.execute([0xFFFF_FFFF, 1]), [0])

    def test_branch_contracts_and_execution_budget_are_checked(self) -> None:
        with self.assertRaisesRegex(VerifyError, "requires CMP"):
            compile_code("CODE: BAD ( -- )\n BEQ done\n LABEL done\n ;CODE")
        with self.assertRaisesRegex(VerifyError, "unknown label"):
            compile_code("CODE: BAD ( -- )\n BRA missing\n ;CODE")
        looping = compile_code("""CODE: LOOP-MAYBE ( flag -- )
        IN V0, flag
        LIT V1, 0
@again:
        CMP V0, V1
        BEQ @done
        BRA @again
@done:
        ;CODE""")
        before = [1]
        with self.assertRaises(ExecutionError):
            looping.execute(before, max_steps=20)
        self.assertEqual(before, [1])

    def test_legacy_label_instruction_remains_compatible(self) -> None:
        legacy = compile_code("""CODE: LEGACY ( -- value )
        BRA old
        LIT V0, 0
        LABEL old
        LIT V0, 7
        OUT value, V0
        ;CODE""")
        self.assertEqual(legacy.execute([]), [7])

    def test_checked_load_with_positive_and_negative_offsets(self) -> None:
        memory = MemoryWindow(0x1000, 16)
        memory.write32(0x1004, 0x12345678)
        load = compile_code("""CODE: LOAD-PAIR ( address -- first second )
        IN V1, address
        LD32 V0, [V1]
        LD32 V2, [V1-4]
        OUT first, V0
        OUT second, V2
        ;CODE""")
        self.assertEqual(
            load.execute([0x1008], memory=memory), [0, 0x12345678]
        )

    def test_store_is_committed_only_after_success(self) -> None:
        memory = MemoryWindow(0x2000, 8)
        store = compile_code("""CODE: STORE ( value address -- )
        IN V0, value
        IN V1, address
        ST32 [V1+4], V0
        ;CODE""")
        self.assertEqual(store.execute([99, 0x2000], memory=memory), [])
        self.assertEqual(memory.read32(0x2004), 99)

        looping = compile_code("""CODE: STORE-THEN-LOOP ( value address -- )
        IN V0, value
        IN V1, address
        ST32 [V1], V0
@again:
        CMP V0, V0
        BEQ @again
        ;CODE""")
        memory.write32(0x2000, 7)
        with self.assertRaises(ExecutionError):
            looping.execute([88, 0x2000], memory=memory, max_steps=10)
        self.assertEqual(memory.read32(0x2000), 7)

    def test_store_forwarding_and_access_checks(self) -> None:
        memory = MemoryWindow(0x3000, 8)
        round_trip = compile_code("""CODE: ROUND-TRIP ( value address -- observed )
        IN V0, value
        IN V1, address
        ST32 [V1], V0
        LD32 V2, [V1]
        OUT observed, V2
        ;CODE""")
        self.assertEqual(round_trip.execute([55, 0x3000], memory=memory), [55])
        self.assertEqual(memory.read32(0x3000), 55)

        before = list(memory.data)
        with self.assertRaises(MemoryAccessError):
            round_trip.execute([66, 0x3001], memory=memory)
        self.assertEqual(list(memory.data), before)
        with self.assertRaises(MemoryAccessError):
            round_trip.execute([66, 0x3008], memory=memory)
        self.assertEqual(list(memory.data), before)

        read_only = MemoryWindow(0x3000, 8, writable=False)
        with self.assertRaises(MemoryAccessError):
            round_trip.execute([66, 0x3000], memory=read_only)


if __name__ == "__main__":
    unittest.main(verbosity=2)
