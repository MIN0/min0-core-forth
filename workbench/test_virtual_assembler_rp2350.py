import unittest

from min0_virtual_assembler import VerifyError, compile_code
from min0_virtual_assembler_rp2350 import (
    ARCHITECTURE,
    BackendInstruction,
    BackendPlan,
    lower_rp2350,
    verify_backend_plan,
)


class Rp2350LoweringTests(unittest.TestCase):
    def test_stack_contract_uses_frame_helpers_not_push_pop(self) -> None:
        definition = compile_code("""CODE: SUM ( a b -- sum )
        IN V0, a
        IN V1, b
        ADD V0, V1
        OUT sum, V0
        ;CODE""")
        plan = lower_rp2350(definition)
        opcodes = [instruction.opcode for instruction in plan.instructions]
        self.assertEqual(opcodes.count("FRAME_LOAD"), 2)
        self.assertEqual(opcodes.count("RESULT_STAGE"), 1)
        self.assertEqual(opcodes.count("FRAME_COMMIT"), 1)
        self.assertNotIn("PUSH_DATA", opcodes)
        self.assertNotIn("POP_DATA", opcodes)
        self.assertEqual(plan.instructions[-3].operands, (2, 1))

    def test_virtual_register_mapping_is_stable(self) -> None:
        definition = compile_code("""CODE: COPY ( x -- y )
        IN V0, x
        MOV V3, V0
        OUT y, V3
        ;CODE""")
        listing = lower_rp2350(definition).listing()
        self.assertIn("FRAME_LOAD r4, 0", listing)
        self.assertIn("MOV r7, r4", listing)
        self.assertIn("RESULT_STAGE 0, r7", listing)

    def test_memory_access_lowers_only_to_checked_helpers(self) -> None:
        definition = compile_code("""CODE: COPY-CELL ( source destination -- )
        IN V1, source
        IN V2, destination
        LD32 V0, [DATA: V1+4]
        ST32 [IO: V2], V0
        ;CODE""")
        plan = lower_rp2350(definition)
        operations = {item.opcode: item.operands for item in plan.instructions}
        self.assertEqual(operations["CHECKED_LD32"], ("r4", "DATA", "r5", 4))
        self.assertEqual(operations["STAGE_ST32"], ("IO", "r6", 0, "r4"))
        self.assertNotIn("RAW_LDR", operations)
        self.assertNotIn("RAW_STR", operations)

    def test_labels_remain_visible_in_backend_plan(self) -> None:
        definition = compile_code("""CODE: CHOOSE ( a b -- max )
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
        listing = lower_rp2350(definition).listing()
        self.assertIn("BGE @a-wins", listing)
        self.assertIn("LABEL @a-wins", listing)
        self.assertIn("LABEL @done", listing)

    def test_unknown_or_raw_backend_operation_is_rejected(self) -> None:
        for opcode in ("RAW_LDR", "SURPRISE"):
            plan = BackendPlan(
                "BAD", ARCHITECTURE, 0, 0,
                (
                    BackendInstruction("PROLOGUE_SAVE", ("r4", "r5", "r6", "r7")),
                    BackendInstruction(opcode, ()),
                    BackendInstruction("FRAME_COMMIT", (0, 0)),
                    BackendInstruction("EPILOGUE_RESTORE", ("r4", "r5", "r6", "r7")),
                    BackendInstruction("RETURN", ()),
                ),
            )
            with self.assertRaises(VerifyError):
                verify_backend_plan(plan)


if __name__ == "__main__":
    unittest.main(verbosity=2)
