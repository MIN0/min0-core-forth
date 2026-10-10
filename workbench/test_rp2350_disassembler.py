from dataclasses import replace
import unittest

from min0_rp2350_disassembler import (
    MachineAuditError,
    audit_linked_helper_thunks,
    audit_linked_main,
    decode_thumb_instruction,
)
from min0_rp2350_linker import (
    emit_helper_thunks,
    link_function_frame,
    link_internal_branches,
    plan_helper_thunks,
    prepare_link,
    resolve_external_branches,
)
from min0_rp2350_thumb_emitter import emit_thumb_fragment
from min0_virtual_assembler import compile_code
from min0_virtual_assembler_rp2350 import lower_rp2350


class Rp2350IndependentDisassemblerTests(unittest.TestCase):
    def test_known_thumb_encodings_decode_without_encoder_helpers(self) -> None:
        cases = (
            (bytes.fromhex("2de9f047"), "STMDB", ("sp!", "r4", "r5", "r6", "r7", "r8", "r9", "r10", "lr")),
            (bytes.fromhex("1820c441"), "MOVS", ("r0", 24)),
            (bytes.fromhex("c441"), "ROR", ("r4", "r0")),
            (bytes.fromhex("d145"), "CMP", ("r9", "r10")),
            (bytes.fromhex("7047"), "BX", ("lr",)),
        )
        for raw, mnemonic, operands in cases:
            with self.subTest(raw=raw.hex()):
                decoded = decode_thumb_instruction(raw)
                self.assertEqual(decoded.mnemonic, mnemonic)
                self.assertEqual(decoded.operands, operands)

    def test_complete_main_body_matches_backend_plan(self) -> None:
        definition = compile_code("""CODE: MIXED ( a b -- result )
        IN V0, a
        IN V1, b
        LIT V2, 0x12345678
        XOR V0, V2
        CMP V0, V1
        ROL V0, 8
        BGEU @use-a
        OUT result, V1
        BRA @done
@use-a:
        OUT result, V0
@done:
        ;CODE""")
        plan = lower_rp2350(definition)
        original = emit_thumb_fragment(plan)
        main_size = len(original.code)
        prepared = link_internal_branches(link_function_frame(prepare_link(original)))
        thunk_plans = plan_helper_thunks(prepared, {})
        symbol_addresses = {
            "min0_frame_load": 0x5001,
            "min0_result_stage": 0x5101,
            "min0_frame_commit": 0x5201,
            "min0_abort_transaction": 0x5301,
        }
        linked = resolve_external_branches(
            emit_helper_thunks(prepared, {}),
            0x2000,
            symbol_addresses,
        )
        decoded = audit_linked_main(plan, linked, main_size, image_base=0x2000)
        thunk_reports = audit_linked_helper_thunks(
            thunk_plans, linked, symbol_addresses, image_base=0x2000
        )
        self.assertTrue(any(item.mnemonic == "LDR_LITERAL" for item in decoded))
        self.assertTrue(any(item.mnemonic == "ROR" for item in decoded))
        self.assertTrue(any(item.mnemonic == "BGEU" for item in decoded))
        self.assertEqual(len(thunk_reports), len(thunk_plans))
        self.assertTrue(all(
            any(item.mnemonic == "BL" for item in report)
            for report in thunk_reports.values()
        ))

    def test_machine_tampering_is_reported_as_plan_mismatch(self) -> None:
        definition = compile_code("""CODE: COPY ( input -- output )
        IN V0, input
        OUT output, V0
        ;CODE""")
        plan = lower_rp2350(definition)
        original = emit_thumb_fragment(plan)
        main_size = len(original.code)
        linked = resolve_external_branches(
            emit_helper_thunks(link_function_frame(prepare_link(original)), {}),
            0x2000,
            {
                "min0_frame_load": 0x5001,
                "min0_result_stage": 0x5101,
                "min0_frame_commit": 0x5201,
                "min0_abort_transaction": 0x5301,
            },
        )
        damaged = bytearray(linked.code)
        damaged[0:4] = bytes.fromhex("00bf00bf")
        with self.assertRaisesRegex(MachineAuditError, "machine mismatch"):
            audit_linked_main(
                plan, replace(linked, code=bytes(damaged)), main_size, image_base=0x2000
            )

    def test_memory_helper_thunks_match_private_abi_plan(self) -> None:
        definition = compile_code("""CODE: ROUND-TRIP ( value address -- observed )
        IN V0, value
        IN V1, address
        ST32 [IO: V1], V0
        LD32 V2, [IO: V1]
        OUT observed, V2
        ;CODE""")
        plan = lower_rp2350(definition)
        original = emit_thumb_fragment(plan)
        main_size = len(original.code)
        prepared = link_function_frame(prepare_link(original))
        thunk_plans = plan_helper_thunks(prepared, {"IO": 7})
        symbol_addresses = {
            "min0_frame_load": 0x5001,
            "min0_result_stage": 0x5101,
            "min0_checked_ld32": 0x5201,
            "min0_stage_st32": 0x5301,
            "min0_frame_commit": 0x5401,
            "min0_abort_transaction": 0x5501,
        }
        linked = resolve_external_branches(
            emit_helper_thunks(prepared, {"IO": 7}),
            0x2000,
            symbol_addresses,
        )
        audit_linked_main(plan, linked, main_size, image_base=0x2000)
        reports = audit_linked_helper_thunks(
            thunk_plans, linked, symbol_addresses, image_base=0x2000
        )
        mnemonics = [
            instruction.mnemonic
            for report in reports.values()
            for instruction in report
        ]
        self.assertIn("LDR_LITERAL", mnemonics)
        self.assertIn("B.W", mnemonics)


if __name__ == "__main__":
    unittest.main(verbosity=2)
