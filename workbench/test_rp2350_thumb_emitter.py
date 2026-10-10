import unittest

from min0_rp2350_thumb_emitter import (
    UDF_RELOCATION_SLOT,
    emit_thumb_fragment,
    verify_machine_fragment,
)
from min0_virtual_assembler import compile_code
from min0_virtual_assembler_rp2350 import lower_rp2350


class ThumbEmitterTests(unittest.TestCase):
    def test_known_alu_halfwords_are_little_endian(self) -> None:
        definition = compile_code("""CODE: ALU ( a b -- result )
        IN V0, a
        IN V1, b
        MOV V3, V0
        ADD V0, V1
        SUB V0, V1
        AND V0, V1
        XOR V0, V1
        OR V0, V1
        MUL V0, V1
        NOT V0
        CMP V0, V1
        LSL V0, 1
        OUT result, V0
        ;CODE""")
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        encoded = fragment.code
        expected_halfwords = (0x4627, 0x1964, 0x1B64, 0x402C, 0x406C,
                              0x432C, 0x436C, 0x43E4, 0x46A1, 0x46AA, 0x0064)
        for halfword in expected_halfwords:
            self.assertIn(halfword.to_bytes(2, "little"), encoded)

    def test_unresolved_actions_are_udf_guarded_and_not_executable(self) -> None:
        definition = compile_code("""CODE: COPY ( source destination -- )
        IN V1, source
        IN V2, destination
        LD32 V0, [DATA: V1]
        ST32 [IO: V2], V0
        ;CODE""")
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        self.assertFalse(fragment.executable)
        self.assertGreater(len(fragment.relocations), 0)
        for relocation in fragment.relocations:
            self.assertEqual(
                fragment.code[relocation.offset:relocation.offset + 4],
                UDF_RELOCATION_SLOT,
            )
        verify_machine_fragment(fragment)

    def test_labels_record_machine_offsets_without_emitting_bytes(self) -> None:
        definition = compile_code("""CODE: PICK ( a b -- max )
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
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        self.assertIn("@a-wins", fragment.labels)
        self.assertIn("@done", fragment.labels)
        self.assertLess(fragment.labels["@a-wins"], fragment.labels["@done"])

    def test_zero_shift_is_encoded_as_register_move(self) -> None:
        definition = compile_code("""CODE: SHIFT-ZERO ( x -- y )
        IN V0, x
        LSL V0, 0
        OUT y, V0
        ;CODE""")
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        self.assertIn((0x4624).to_bytes(2, "little"), fragment.code)

    def test_comparison_values_are_snapshotted_before_flag_clobber(self) -> None:
        definition = compile_code("""CODE: COMPARE-LATER ( a b -- result )
        IN V0, a
        IN V1, b
        CMP V0, V1
        ADD V0, V1
        BEQ @equal
        OUT result, V0
        BRA @done
@equal:
        OUT result, V1
@done:
        ;CODE""")
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        snapshot = bytes.fromhex("a146aa46")  # MOV r9,r4; MOV r10,r5
        add = (0x1964).to_bytes(2, "little")
        self.assertIn(snapshot + add, fragment.code)

    def test_rotate_immediates_use_r0_without_unresolved_actions(self) -> None:
        definition = compile_code("""CODE: ROTATE ( x -- left right same )
        IN V0, x
        MOV V1, V0
        MOV V2, V0
        ROL V0, 8
        ROR V1, 4
        ROL V2, 0
        OUT left, V0
        OUT right, V1
        OUT same, V2
        ;CODE""")
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        self.assertIn(bytes.fromhex("1820c441"), fragment.code)  # r0=24; ROR r4,r0
        self.assertIn(bytes.fromhex("0420c541"), fragment.code)  # r0=4; ROR r5,r0
        self.assertIn(bytes.fromhex("364600bf"), fragment.code)  # MOV r6,r6; NOP
        self.assertFalse(any(
            item.opcode in {"ROL", "ROR"} for item in fragment.relocations
        ))

    def test_rotate_between_cmp_and_branch_keeps_comparison_snapshot(self) -> None:
        definition = compile_code("""CODE: ROTATE-LATER ( a b -- result )
        IN V0, a
        IN V1, b
        CMP V0, V1
        ROR V0, 3
        BEQ @equal
        OUT result, V0
        BRA @done
@equal:
        OUT result, V1
@done:
        ;CODE""")
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        self.assertIn(bytes.fromhex("a146aa460320c441"), fragment.code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
