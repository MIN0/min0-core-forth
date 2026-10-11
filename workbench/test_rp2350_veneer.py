from dataclasses import replace
import unittest

from min0_rp2350_disassembler import (
    MachineAuditError,
    audit_private_abi_veneers,
    decode_thumb_instruction,
)
from min0_rp2350_veneer import (
    UDF_SLOT,
    emit_private_abi_veneers,
    link_private_abi_veneers,
    private_abi_symbol_addresses,
    private_abi_veneer_plans,
)
from min0_rp2350_publication import (
    Rp2350PublicationPolicy,
    audit_publication_candidate,
    build_linked_candidate,
)
from min0_virtual_assembler import compile_code
from min0_virtual_assembler_rp2350 import lower_rp2350
from min0_virtual_assembler import VerifyError


IMAGE_BASE = 0x4000
RUNTIME_SYMBOLS = {
    "min0_runtime_frame_load": 0x6001,
    "min0_runtime_result_stage": 0x6101,
    "min0_runtime_checked_ld32": 0x6201,
    "min0_runtime_stage_st32": 0x6301,
    "min0_runtime_frame_commit": 0x6401,
    "min0_runtime_abort_transaction": 0x6501,
}


class Rp2350PrivateAbiVeneerTests(unittest.TestCase):
    def test_independent_decoder_understands_veneer_stack_instructions(self):
        cases = (
            (bytes.fromhex("04b5"), "PUSH", ("r2", "lr")),
            (bytes.fromhex("04bd"), "POP", ("r2", "pc")),
            (bytes.fromhex("82b0"), "SUB_SP", (8,)),
            (bytes.fromhex("02b0"), "ADD_SP", (8,)),
            (bytes.fromhex("01aa"), "ADD_FROM_SP", ("r2", 4)),
            (bytes.fromhex("0092"), "STR_SP", ("r2", 0)),
            (bytes.fromhex("039a"), "LDR_SP", ("r2", 12)),
        )
        for raw, mnemonic, operands in cases:
            with self.subTest(raw=raw.hex()):
                decoded = decode_thumb_instruction(raw)
                self.assertEqual((decoded.mnemonic, decoded.operands), (mnemonic, operands))

    def test_unlinked_veneers_keep_every_runtime_branch_udf_guarded(self):
        image = emit_private_abi_veneers()
        self.assertEqual(len(image.relocations), 6)
        self.assertFalse(image.link_complete)
        self.assertFalse(image.execution_authorized)
        for relocation in image.relocations:
            self.assertEqual(image.code[relocation.offset:relocation.offset + 4], UDF_SLOT)
        self.assertTrue(all(offset % 4 == 0 for offset in image.labels.values()))

    def test_linked_veneers_pass_independent_instruction_audit(self):
        plans = private_abi_veneer_plans()
        linked = link_private_abi_veneers(
            emit_private_abi_veneers(),
            image_base=IMAGE_BASE,
            runtime_symbols=RUNTIME_SYMBOLS,
        )
        reports = audit_private_abi_veneers(plans, linked, RUNTIME_SYMBOLS)
        self.assertEqual(set(reports), {plan.public_symbol for plan in plans})
        self.assertFalse(linked.execution_authorized)
        self.assertTrue(linked.link_complete)
        symbols = private_abi_symbol_addresses(linked)
        self.assertEqual(set(symbols), set(reports))
        self.assertTrue(all(address & 1 for address in symbols.values()))
        self.assertEqual(
            [item.mnemonic for item in reports["min0_stage_st32"]],
            ["STMDB", "BL", "LDMIA"],
        )
        self.assertIn(
            "LDMIA",
            [item.mnemonic for item in reports["min0_abort_transaction"]],
        )

    def test_checked_load_uses_aligned_24_byte_veneer_frame(self):
        linked = link_private_abi_veneers(
            emit_private_abi_veneers(),
            image_base=IMAGE_BASE,
            runtime_symbols=RUNTIME_SYMBOLS,
        )
        report = audit_private_abi_veneers(
            private_abi_veneer_plans(), linked, RUNTIME_SYMBOLS
        )["min0_checked_ld32"]
        self.assertEqual(
            [(item.mnemonic, item.operands) for item in report[:6]],
            [
                ("PUSH", ("r1", "r2", "r3", "lr")),
                ("SUB_SP", (8,)),
                ("ADD_FROM_SP", ("r2", 4)),
                ("STR_SP", ("r2", 0)),
                ("LDR_SP", ("r2", 12)),
                ("LDR_SP", ("r3", 16)),
            ],
        )
        self.assertEqual(report[-3].mnemonic, "ADD_SP")
        self.assertEqual(report[-3].operands, (12,))
        self.assertEqual(report[-2].mnemonic, "POP")
        self.assertEqual(report[-2].operands, ("r2", "r3", "pc"))
        self.assertEqual(report[-1].mnemonic, "NOP")

    def test_machine_tampering_is_rejected_by_independent_audit(self):
        linked = link_private_abi_veneers(
            emit_private_abi_veneers(),
            image_base=IMAGE_BASE,
            runtime_symbols=RUNTIME_SYMBOLS,
        )
        damaged = bytearray(linked.code)
        damaged[0:2] = bytes.fromhex("00bf")
        with self.assertRaisesRegex(MachineAuditError, "machine mismatch"):
            audit_private_abi_veneers(
                private_abi_veneer_plans(),
                replace(linked, code=bytes(damaged)),
                RUNTIME_SYMBOLS,
            )

    def test_missing_runtime_symbol_and_unlinked_publication_are_rejected(self):
        with self.assertRaisesRegex(VerifyError, "no address"):
            link_private_abi_veneers(
                emit_private_abi_veneers(),
                image_base=IMAGE_BASE,
                runtime_symbols={},
            )
        with self.assertRaisesRegex(VerifyError, "not link complete"):
            private_abi_symbol_addresses(emit_private_abi_veneers())

    def test_publication_candidate_binds_to_audited_veneer_symbols(self):
        plans = private_abi_veneer_plans()
        veneers = link_private_abi_veneers(
            emit_private_abi_veneers(),
            image_base=IMAGE_BASE,
            runtime_symbols=RUNTIME_SYMBOLS,
        )
        audit_private_abi_veneers(plans, veneers, RUNTIME_SYMBOLS)
        helper_symbols = private_abi_symbol_addresses(veneers)
        definition = compile_code("""CODE: COPY ( input -- output )
        IN V0, input
        OUT output, V0
        ;CODE""")
        candidate = build_linked_candidate(
            lower_rp2350(definition),
            {},
            image_base=0x2000,
            symbol_addresses=helper_symbols,
        )
        policy = Rp2350PublicationPolicy.create(
            image_base=0x2000,
            image_limit=0x3000,
            approved_symbols=helper_symbols,
        )
        receipt = audit_publication_candidate(candidate, policy)
        self.assertEqual(receipt.byte_coverage, len(candidate.fragment.code))


if __name__ == "__main__":
    unittest.main(verbosity=2)
