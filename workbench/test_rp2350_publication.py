from dataclasses import replace
import unittest

from min0_rp2350_publication import (
    PublicationError,
    Rp2350PublicationPolicy,
    audit_publication_candidate,
    audit_staged_image,
    build_linked_candidate,
    publish_audited_candidate,
    publish_audited_staging,
    stage_linked_candidate,
)
from min0_rp2350_thumb_emitter import emit_thumb_fragment
from min0_virtual_assembler import compile_code
from min0_virtual_assembler_rp2350 import lower_rp2350


IMAGE_BASE = 0x2000
SYMBOLS = {
    "min0_frame_load": 0x5001,
    "min0_result_stage": 0x5101,
    "min0_checked_ld32": 0x5201,
    "min0_stage_st32": 0x5301,
    "min0_frame_commit": 0x5401,
    "min0_abort_transaction": 0x5501,
}


def _definition():
    return compile_code("""CODE: SAFE-MIX ( value address -- observed )
    IN V0, value
    IN V1, address
    ST32 [IO: V1], V0
    LD32 V2, [IO: V1]
    XOR V2, V0
    OUT observed, V2
    ;CODE""")


def _policy(symbols=None, *, image_limit=0x4000):
    return Rp2350PublicationPolicy.create(
        image_base=IMAGE_BASE,
        image_limit=image_limit,
        approved_symbols=SYMBOLS if symbols is None else symbols,
    )


def _candidate():
    return build_linked_candidate(
        lower_rp2350(_definition()),
        {"IO": 7},
        image_base=IMAGE_BASE,
        symbol_addresses=SYMBOLS,
    )


class Rp2350PublicationGateTests(unittest.TestCase):
    def test_audited_candidate_becomes_sealed_rx_snapshot_without_execution(self) -> None:
        candidate = _candidate()
        staging = stage_linked_candidate(candidate)
        receipt = audit_staged_image(staging, _policy())
        published = publish_audited_staging(staging, receipt, _policy())
        self.assertEqual(staging.permissions, "rw,nx")
        self.assertTrue(staging.programmable)
        self.assertFalse(staging.execution_authorized)
        self.assertEqual(receipt.byte_coverage, len(candidate.fragment.code))
        self.assertEqual(published.permissions, "rx")
        self.assertFalse(published.programmable)
        self.assertTrue(published.sealed)
        self.assertFalse(receipt.execution_authorized)
        self.assertFalse(published.execution_authorized)
        self.assertEqual(published.code, candidate.fragment.code)
        self.assertFalse(hasattr(published, "execute"))

    def test_branched_word_passes_the_same_full_byte_gate(self) -> None:
        plan = lower_rp2350(compile_code("""CODE: MAX ( a b -- result )
        IN V0, a
        IN V1, b
        CMP V0, V1
        BGE @a-wins
        OUT result, V1
        BRA @done
@a-wins:
        OUT result, V0
@done:
        ;CODE"""))
        candidate = build_linked_candidate(
            plan,
            {},
            image_base=IMAGE_BASE,
            symbol_addresses=SYMBOLS,
        )
        receipt = audit_publication_candidate(candidate, _policy())
        self.assertEqual(receipt.byte_coverage, len(candidate.fragment.code))
        self.assertGreater(receipt.main_instruction_count, 0)

    def test_runtime_snapshot_is_detached_from_later_staging_writes(self) -> None:
        staging = stage_linked_candidate(_candidate())
        policy = _policy()
        receipt = audit_staged_image(staging, policy)
        published = publish_audited_staging(staging, receipt, policy)
        before = published.code
        staging.write(0, b"\x00\xBF")
        self.assertNotEqual(bytes(staging.storage), before)
        self.assertEqual(published.code, before)

    def test_unresolved_relocation_is_rejected_before_audit(self) -> None:
        plan = lower_rp2350(_definition())
        fragment = emit_thumb_fragment(plan)
        candidate = replace(
            _candidate(),
            fragment=fragment,
            main_size=len(fragment.code),
            thunk_plans=(),
        )
        with self.assertRaisesRegex(PublicationError, "unresolved relocations"):
            audit_publication_candidate(candidate, _policy())

    def test_main_machine_tampering_is_rejected(self) -> None:
        candidate = _candidate()
        damaged = bytearray(candidate.fragment.code)
        damaged[0:4] = bytes.fromhex("00bf00bf")
        tampered = replace(
            candidate,
            fragment=replace(candidate.fragment, code=bytes(damaged)),
        )
        with self.assertRaisesRegex(PublicationError, "machine mismatch"):
            audit_publication_candidate(tampered, _policy())

    def test_helper_thunk_tampering_is_rejected(self) -> None:
        candidate = _candidate()
        thunk_offset = min(
            offset
            for name, offset in candidate.fragment.labels.items()
            if name.startswith("@helper-thunk-")
        )
        damaged = bytearray(candidate.fragment.code)
        damaged[thunk_offset:thunk_offset + 4] = bytes.fromhex("00bf00bf")
        tampered = replace(
            candidate,
            fragment=replace(candidate.fragment, code=bytes(damaged)),
        )
        with self.assertRaisesRegex(PublicationError, "machine mismatch"):
            audit_publication_candidate(tampered, _policy())

    def test_unapproved_helper_address_is_rejected(self) -> None:
        changed = dict(SYMBOLS)
        changed["min0_checked_ld32"] = 0x5A01
        with self.assertRaisesRegex(PublicationError, "symbol table is not approved"):
            audit_publication_candidate(_candidate(), _policy(changed))

    def test_candidate_change_after_audit_is_rejected_by_digest(self) -> None:
        staging = stage_linked_candidate(_candidate())
        policy = _policy()
        receipt = audit_staged_image(staging, policy)
        staging.storage[-1] ^= 1
        with self.assertRaisesRegex(PublicationError, "changed after audit"):
            publish_audited_staging(staging, receipt, policy)

    def test_policy_change_after_audit_is_rejected(self) -> None:
        candidate = _candidate()
        receipt = audit_publication_candidate(candidate, _policy())
        with self.assertRaisesRegex(PublicationError, "policy changed after audit"):
            publish_audited_candidate(
                candidate,
                receipt,
                _policy(image_limit=0x3800),
            )

    def test_appended_unreviewed_machine_bytes_are_rejected(self) -> None:
        candidate = _candidate()
        extended = replace(
            candidate,
            fragment=replace(candidate.fragment, code=candidate.fragment.code + b"\x00\xBF"),
        )
        with self.assertRaisesRegex(PublicationError, "not independently audited"):
            audit_publication_candidate(extended, _policy())

    def test_candidate_outside_approved_image_range_is_rejected(self) -> None:
        candidate = _candidate()
        with self.assertRaisesRegex(PublicationError, "approved image range"):
            audit_publication_candidate(
                candidate,
                _policy(image_limit=IMAGE_BASE + len(candidate.fragment.code) - 1),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
