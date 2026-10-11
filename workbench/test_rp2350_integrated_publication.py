from dataclasses import replace
import unittest

from min0_rp2350_integrated_publication import (
    IntegratedPublicationPolicy,
    audit_integrated_candidate,
    audit_integrated_staging,
    build_integrated_candidate,
    publish_integrated_staging,
    stage_integrated_candidate,
)
from min0_rp2350_publication import PublicationError
from min0_virtual_assembler import compile_code
from min0_virtual_assembler_rp2350 import lower_rp2350


IMAGE_BASE = 0x2000
RUNTIME_SYMBOLS = {
    "min0_runtime_frame_load": 0x6001,
    "min0_runtime_result_stage": 0x6101,
    "min0_runtime_checked_ld32": 0x6201,
    "min0_runtime_stage_st32": 0x6301,
    "min0_runtime_frame_commit": 0x6401,
    "min0_runtime_abort_transaction": 0x6501,
}


def _plan():
    return lower_rp2350(compile_code("""CODE: SAFE-MIX ( value address -- observed )
    IN V0, value
    IN V1, address
    ST32 [IO: V1], V0
    LD32 V2, [IO: V1]
    XOR V2, V0
    OUT observed, V2
    ;CODE"""))


def _candidate():
    return build_integrated_candidate(
        _plan(),
        {"IO": 7},
        image_base=IMAGE_BASE,
        runtime_symbols=RUNTIME_SYMBOLS,
    )


def _policy(*, runtime_symbols=None, image_limit=0x7000):
    return IntegratedPublicationPolicy.create(
        image_base=IMAGE_BASE,
        image_limit=image_limit,
        runtime_symbols=RUNTIME_SYMBOLS if runtime_symbols is None else runtime_symbols,
    )


class Rp2350IntegratedPublicationTests(unittest.TestCase):
    def test_single_receipt_covers_main_thunks_alignment_and_veneers(self):
        candidate = _candidate()
        receipt = audit_integrated_candidate(candidate, _policy())
        self.assertEqual(receipt.byte_coverage, len(candidate.code))
        self.assertEqual(
            [region.name for region in receipt.regions],
            [
                "main",
                "helper-thunks-and-literals",
                "alignment",
                "private-abi-veneers",
            ],
        )
        self.assertGreater(receipt.main_instruction_count, 0)
        self.assertGreater(receipt.thunk_count, 0)
        self.assertEqual(receipt.veneer_count, 6)
        self.assertFalse(receipt.execution_authorized)
        self.assertEqual(candidate.veneer_offset % 4, 0)
        self.assertEqual(
            candidate.linked.symbols(),
            {
                name: (candidate.veneers.image_base + offset) | 1
                for name, offset in candidate.veneers.labels.items()
            },
        )

    def test_w_x_staging_publishes_detached_rx_without_execute(self):
        candidate = _candidate()
        staging = stage_integrated_candidate(candidate)
        receipt = audit_integrated_staging(staging, _policy())
        published = publish_integrated_staging(staging, receipt, _policy())
        self.assertEqual(staging.permissions, "rw,nx")
        self.assertTrue(staging.programmable)
        self.assertFalse(staging.execution_authorized)
        self.assertEqual(published.permissions, "rx")
        self.assertFalse(published.programmable)
        self.assertTrue(published.sealed)
        self.assertFalse(published.execution_authorized)
        self.assertFalse(hasattr(published, "execute"))
        before = published.code
        staging.write(0, b"\x00\xBF")
        self.assertEqual(published.code, before)

    def test_main_or_thunk_change_after_audit_is_rejected(self):
        staging = stage_integrated_candidate(_candidate())
        receipt = audit_integrated_staging(staging, _policy())
        staging.storage[0] ^= 1
        with self.assertRaisesRegex(PublicationError, "components do not match"):
            publish_integrated_staging(staging, receipt, _policy())

    def test_veneer_change_after_audit_is_rejected(self):
        staging = stage_integrated_candidate(_candidate())
        receipt = audit_integrated_staging(staging, _policy())
        staging.storage[staging.candidate.veneer_offset] ^= 1
        with self.assertRaisesRegex(PublicationError, "components do not match"):
            publish_integrated_staging(staging, receipt, _policy())

    def test_unapproved_runtime_symbol_is_rejected(self):
        changed = dict(RUNTIME_SYMBOLS)
        changed["min0_runtime_checked_ld32"] = 0x6A01
        with self.assertRaisesRegex(PublicationError, "symbol table is not approved"):
            audit_integrated_candidate(_candidate(), _policy(runtime_symbols=changed))

    def test_missing_runtime_symbol_is_rejected(self):
        missing = dict(RUNTIME_SYMBOLS)
        missing.pop("min0_runtime_abort_transaction")
        with self.assertRaisesRegex(PublicationError, "symbol set is incomplete"):
            audit_integrated_candidate(_candidate(), _policy(runtime_symbols=missing))

    def test_even_runtime_function_pointer_is_rejected(self):
        changed = dict(RUNTIME_SYMBOLS)
        changed["min0_runtime_frame_load"] &= ~1
        with self.assertRaisesRegex(PublicationError, "invalid runtime symbol"):
            audit_integrated_candidate(_candidate(), _policy(runtime_symbols=changed))

    def test_runtime_symbol_cannot_overlap_generated_image(self):
        candidate = _candidate()
        changed = dict(RUNTIME_SYMBOLS)
        changed["min0_runtime_frame_load"] = candidate.image_base | 1
        policy = _policy(runtime_symbols=changed)
        modified = replace(
            candidate,
            runtime_symbols=policy.runtime_symbols,
        )
        with self.assertRaisesRegex(PublicationError, "overlaps the generated image"):
            audit_integrated_candidate(modified, policy)

    def test_alignment_region_is_explicit_and_contains_only_an_audited_nop(self):
        candidate = _candidate()
        padding_size = candidate.veneer_offset - len(candidate.linked.fragment.code)
        self.assertIn(padding_size, {0, 2})
        receipt = audit_integrated_candidate(candidate, _policy())
        alignment = next(region for region in receipt.regions if region.name == "alignment")
        self.assertEqual(alignment.size, padding_size)
        self.assertIn(
            candidate.code[alignment.offset:alignment.offset + alignment.size],
            {b"", b"\x00\xBF"},
        )

    def test_synchronized_main_tampering_is_rejected_by_independent_decoder(self):
        candidate = _candidate()
        damaged = bytearray(candidate.linked.fragment.code)
        damaged[0] ^= 1
        linked = replace(
            candidate.linked,
            fragment=replace(candidate.linked.fragment, code=bytes(damaged)),
        )
        combined = bytes(damaged) + candidate.code[len(damaged):]
        with self.assertRaisesRegex(
            PublicationError, "unsupported Thumb halfword|machine mismatch"
        ):
            audit_integrated_candidate(
                replace(candidate, linked=linked, code=combined),
                _policy(),
            )

    def test_synchronized_veneer_tampering_is_rejected_by_independent_decoder(self):
        candidate = _candidate()
        damaged = bytearray(candidate.veneers.code)
        damaged[0] ^= 1
        veneers = replace(candidate.veneers, code=bytes(damaged))
        combined = candidate.code[:candidate.veneer_offset] + bytes(damaged)
        with self.assertRaisesRegex(PublicationError, "machine mismatch"):
            audit_integrated_candidate(
                replace(candidate, veneers=veneers, code=combined),
                _policy(),
            )

    def test_image_limit_is_enforced_for_veneer_tail(self):
        candidate = _candidate()
        with self.assertRaisesRegex(PublicationError, "approved range"):
            audit_integrated_candidate(
                candidate,
                _policy(image_limit=IMAGE_BASE + len(candidate.code) - 1),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
