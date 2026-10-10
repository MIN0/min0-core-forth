import unittest

from min0_rp2350_linker import (
    NOP,
    THUNK_PUSH_R12_LR,
    bind_helper_symbols,
    emit_helper_thunks,
    encode_thumb_b_w,
    encode_thumb_bl,
    link_literal_constants,
    plan_helper_thunks,
    prepare_link,
    resolve_external_branches,
)
from min0_rp2350_thumb_emitter import UDF_RELOCATION_SLOT
from min0_rp2350_thumb_emitter import emit_thumb_fragment
from min0_virtual_assembler import VerifyError, compile_code
from min0_virtual_assembler_rp2350 import lower_rp2350


class Rp2350LinkerTests(unittest.TestCase):
    def test_literal_linker_resolves_32_bit_constant(self) -> None:
        definition = compile_code("""CODE: CONST ( -- value )
        LIT V0, 0x12345678
        OUT value, V0
        ;CODE""")
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        relocation = next(item for item in fragment.relocations if item.opcode == "MOV_IMM32")
        linked = link_literal_constants(fragment)
        self.assertFalse(any(item.opcode == "MOV_IMM32" for item in linked.relocations))
        ldr = int.from_bytes(linked.code[relocation.offset:relocation.offset + 2], "little")
        self.assertEqual(ldr & 0xF800, 0x4800)
        self.assertEqual((ldr >> 8) & 7, 4)
        self.assertEqual(
            int.from_bytes(linked.code[relocation.offset + 2:relocation.offset + 4], "little"),
            NOP,
        )
        self.assertEqual(linked.code[-4:], bytes.fromhex("78563412"))

    def test_equal_literals_share_one_pool_cell(self) -> None:
        definition = compile_code("""CODE: TWO-CONSTS ( -- a b )
        LIT V0, 99
        LIT V1, 99
        OUT a, V0
        OUT b, V1
        ;CODE""")
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        linked = link_literal_constants(fragment)
        self.assertEqual(len(linked.code) - ((len(fragment.code) + 3) & ~3), 4)
        self.assertEqual(linked.code[-4:], (99).to_bytes(4, "little"))

    def test_helper_actions_bind_to_private_abi_symbols(self) -> None:
        definition = compile_code("""CODE: LOAD ( address -- value )
        IN V1, address
        LD32 V0, [DATA: V1]
        OUT value, V0
        ;CODE""")
        fragment = emit_thumb_fragment(lower_rp2350(definition))
        bound = bind_helper_symbols(fragment)
        helpers = {
            item.opcode: item for item in bound.relocations
            if item.kind == "RP2350_HELPER_THUNK_CALL"
        }
        self.assertEqual(helpers["CHECKED_LD32"].symbol, "min0_checked_ld32")
        self.assertEqual(helpers["FRAME_COMMIT"].symbol, "min0_frame_commit")

    def test_linked_fragment_stays_non_executable_while_relocations_remain(self) -> None:
        definition = compile_code("""CODE: CONST ( -- value )
        LIT V0, 7
        OUT value, V0
        ;CODE""")
        linked = link_literal_constants(emit_thumb_fragment(lower_rp2350(definition)))
        self.assertGreater(len(linked.relocations), 0)
        self.assertFalse(linked.executable)

    def test_checked_load_thunk_marshals_private_abi(self) -> None:
        definition = compile_code("""CODE: LOAD ( address -- value )
        IN V1, address
        LD32 V0, [DATA: V1+4]
        OUT value, V0
        ;CODE""")
        bound = bind_helper_symbols(emit_thumb_fragment(lower_rp2350(definition)))
        plans = plan_helper_thunks(bound, {"DATA": 3})
        load = next(plan for plan in plans if plan.helper_symbol == "min0_checked_ld32")
        operations = [(item.opcode, item.operands) for item in load.instructions]
        self.assertIn(("MOV", ("r0", "r8")), operations)
        self.assertIn(("MOV_IMM32", ("r1", 3)), operations)
        self.assertIn(("MOV", ("r2", "r5")), operations)
        self.assertIn(("MOV_IMM32", ("r3", 4)), operations)
        self.assertIn(("MOV", ("r4", "r1")), operations)
        self.assertEqual(operations[0], ("THUNK_ENTER_8", ("r12", "lr")))
        self.assertEqual(operations[-1], ("THUNK_RETURN_8", ("r12", "pc")))

    def test_store_thunk_passes_value_in_r12_and_unwinds_on_error(self) -> None:
        definition = compile_code("""CODE: STORE ( value address -- )
        IN V0, value
        IN V2, address
        ST32 [IO: V2], V0
        ;CODE""")
        bound = bind_helper_symbols(emit_thumb_fragment(lower_rp2350(definition)))
        plans = plan_helper_thunks(bound, {"IO": 9})
        store = next(plan for plan in plans if plan.helper_symbol == "min0_stage_st32")
        operations = [(item.opcode, item.operands) for item in store.instructions]
        self.assertIn(("MOV", ("r12", "r4")), operations)
        self.assertIn(
            ("ABORT_IF_NONZERO", ("r0", "min0_abort_transaction", 8)),
            operations,
        )

    def test_unknown_capability_has_no_implicit_numeric_id(self) -> None:
        definition = compile_code("""CODE: LOAD ( address -- value )
        IN V1, address
        LD32 V0, [DATA: V1]
        OUT value, V0
        ;CODE""")
        bound = bind_helper_symbols(emit_thumb_fragment(lower_rp2350(definition)))
        with self.assertRaisesRegex(VerifyError, "no numeric ID"):
            plan_helper_thunks(bound, {})

    def test_thumb_wide_branch_known_zero_displacement_encodings(self) -> None:
        self.assertEqual(encode_thumb_bl(0x100, 0x104), bytes.fromhex("00f000f8"))
        self.assertEqual(encode_thumb_b_w(0x100, 0x104), bytes.fromhex("00f000b8"))
        self.assertEqual(
            encode_thumb_bl(0x080001A6, 0x08000DB8), bytes.fromhex("00f007fe")
        )

    def test_helper_thunks_are_four_byte_aligned_and_call_sites_are_linked(self) -> None:
        definition = compile_code("""CODE: LOAD ( address -- value )
        IN V1, address
        LD32 V0, [DATA: V1+4]
        OUT value, V0
        ;CODE""")
        original = emit_thumb_fragment(lower_rp2350(definition))
        prepared = prepare_link(original)
        helper_site = next(
            item.offset for item in prepared.relocations
            if item.kind == "RP2350_HELPER_THUNK_CALL" and item.opcode == "CHECKED_LD32"
        )
        emitted = emit_helper_thunks(prepared, {"DATA": 3})
        thunk_offset = emitted.labels[f"@helper-thunk-{helper_site:08x}"]
        self.assertEqual(thunk_offset % 4, 0)
        self.assertEqual(emitted.code[thunk_offset:thunk_offset + 4], THUNK_PUSH_R12_LR)
        self.assertNotEqual(emitted.code[helper_site:helper_site + 4], UDF_RELOCATION_SLOT)
        self.assertFalse(any(item.offset == helper_site for item in emitted.relocations))
        self.assertTrue(any(
            item.kind == "RP2350_THUNK_HELPER_CALL"
            and item.symbol == "min0_checked_ld32"
            for item in emitted.relocations
        ))
        self.assertTrue(any(
            item.kind == "RP2350_THUNK_ABORT_BRANCH"
            and item.symbol == "min0_abort_transaction"
            for item in emitted.relocations
        ))

    def test_external_symbol_linker_resolves_thunk_calls_and_abort_paths(self) -> None:
        definition = compile_code("""CODE: LOAD ( address -- value )
        IN V1, address
        LD32 V0, [DATA: V1]
        OUT value, V0
        ;CODE""")
        emitted = emit_helper_thunks(
            prepare_link(emit_thumb_fragment(lower_rp2350(definition))), {"DATA": 3}
        )
        external_offsets = {
            item.offset for item in emitted.relocations
            if item.kind.startswith("RP2350_THUNK_")
        }
        linked = resolve_external_branches(emitted, 0x2000, {
            "min0_checked_ld32": 0x3001,
            "min0_frame_commit": 0x3101,
            "min0_abort_transaction": 0x3201,
        })
        self.assertFalse(any(
            item.kind.startswith("RP2350_THUNK_") for item in linked.relocations
        ))
        for offset in external_offsets:
            self.assertNotEqual(linked.code[offset:offset + 4], UDF_RELOCATION_SLOT)

    def test_external_symbol_linker_rejects_missing_address(self) -> None:
        definition = compile_code("""CODE: LOAD ( address -- value )
        IN V1, address
        LD32 V0, [DATA: V1]
        OUT value, V0
        ;CODE""")
        emitted = emit_helper_thunks(
            prepare_link(emit_thumb_fragment(lower_rp2350(definition))), {"DATA": 3}
        )
        with self.assertRaisesRegex(VerifyError, "no address"):
            resolve_external_branches(emitted, 0x2000, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
