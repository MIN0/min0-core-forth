from dataclasses import replace
import unittest

from min0_rp2350_integrated_publication import (
    IntegratedPublicationPolicy,
    audit_integrated_candidate,
    build_integrated_candidate,
)
from min0_rp2350_publication import PublicationError
from min0_rp2350_target_publication import (
    RP2350_SRAM_BASE,
    Rp2350TargetPublicationAdapter,
    TargetPublicationState,
)
from min0_virtual_assembler import compile_code
from min0_virtual_assembler_rp2350 import lower_rp2350


IMAGE_BASE = 0x2007_0000
RUNTIME_SYMBOLS = {
    "min0_runtime_frame_load": 0x2001_0001,
    "min0_runtime_result_stage": 0x2001_0101,
    "min0_runtime_checked_ld32": 0x2001_0201,
    "min0_runtime_stage_st32": 0x2001_0301,
    "min0_runtime_frame_commit": 0x2001_0401,
    "min0_runtime_abort_transaction": 0x2001_0501,
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


def _candidate(*, image_base=IMAGE_BASE, runtime_symbols=RUNTIME_SYMBOLS):
    return build_integrated_candidate(
        _plan(),
        {"IO": 7},
        image_base=image_base,
        runtime_symbols=runtime_symbols,
    )


def _policy(*, image_base=IMAGE_BASE, runtime_symbols=RUNTIME_SYMBOLS):
    return IntegratedPublicationPolicy.create(
        image_base=image_base,
        image_limit=image_base + 0x1000,
        runtime_symbols=runtime_symbols,
    )


def _prepared():
    candidate = _candidate()
    policy = _policy()
    receipt = audit_integrated_candidate(candidate, policy)
    adapter = Rp2350TargetPublicationAdapter()
    adapter.begin(candidate, policy)
    midpoint = len(candidate.code) // 2
    adapter.write(0, candidate.code[:midpoint])
    adapter.write(midpoint, candidate.code[midpoint:])
    return adapter, candidate, policy, receipt


class Rp2350TargetPublicationTests(unittest.TestCase):
    def test_valid_sequence_seals_detached_rx_image_without_execute(self):
        adapter, candidate, _, receipt = _prepared()
        adapter.verify(receipt)
        adapter.data_sync_before_mpu()
        adapter.apply_mpu_rx()
        adapter.data_sync_after_mpu()
        published = adapter.instruction_sync_after_mpu()
        self.assertEqual(adapter.state, TargetPublicationState.SEALED_RX)
        self.assertEqual(published.code, candidate.code)
        self.assertEqual(published.permissions, "rx")
        self.assertFalse(published.programmable)
        self.assertFalse(published.execution_authorized)
        self.assertFalse(hasattr(published, "execute"))
        self.assertEqual(
            published.events[-4:],
            ("DSB_BEFORE_MPU", "MPU_APPLY_RX", "DSB_AFTER_MPU", "ISB_AFTER_MPU"),
        )

    def test_xip_candidate_is_rejected(self):
        xip_symbols = {
            name: 0x1001_0001 + index * 0x100
            for index, name in enumerate(RUNTIME_SYMBOLS)
        }
        candidate = _candidate(image_base=0x1002_0000, runtime_symbols=xip_symbols)
        adapter = Rp2350TargetPublicationAdapter()
        with self.assertRaisesRegex(PublicationError, "internal SRAM"):
            adapter.begin(
                candidate,
                _policy(image_base=0x1002_0000, runtime_symbols=xip_symbols),
            )
        self.assertEqual(adapter.state, TargetPublicationState.REJECTED)

    def test_candidate_below_sram_is_rejected(self):
        candidate = _candidate(image_base=RP2350_SRAM_BASE - 0x1000)
        adapter = Rp2350TargetPublicationAdapter()
        with self.assertRaisesRegex(PublicationError, "internal SRAM"):
            adapter.begin(candidate, _policy(image_base=RP2350_SRAM_BASE - 0x1000))

    def test_incomplete_transfer_is_rejected(self):
        candidate = _candidate()
        policy = _policy()
        adapter = Rp2350TargetPublicationAdapter()
        adapter.begin(candidate, policy)
        adapter.write(0, candidate.code[:-1])
        with self.assertRaisesRegex(PublicationError, "incomplete"):
            adapter.verify(audit_integrated_candidate(candidate, policy))

    def test_overlapping_transfer_is_rejected(self):
        adapter, _, _, _ = _prepared()
        with self.assertRaisesRegex(PublicationError, "only once"):
            adapter.write(0, b"\x00")
        self.assertEqual(adapter.state, TargetPublicationState.REJECTED)

    def test_transferred_byte_change_is_rejected_by_reaudit(self):
        candidate = _candidate()
        policy = _policy()
        receipt = audit_integrated_candidate(candidate, policy)
        damaged = bytearray(candidate.code)
        damaged[0] ^= 1
        adapter = Rp2350TargetPublicationAdapter()
        adapter.begin(candidate, policy)
        adapter.write(0, bytes(damaged))
        with self.assertRaisesRegex(PublicationError, "byte recheck failed"):
            adapter.verify(receipt)

    def test_receipt_mismatch_is_rejected(self):
        adapter, _, _, receipt = _prepared()
        forged = replace(receipt, artifact_sha256="0" * 64)
        with self.assertRaisesRegex(PublicationError, "receipt does not match"):
            adapter.verify(forged)

    def test_mpu_before_pre_barrier_is_rejected(self):
        adapter, _, _, receipt = _prepared()
        adapter.verify(receipt)
        with self.assertRaisesRegex(PublicationError, "order error"):
            adapter.apply_mpu_rx()
        self.assertEqual(adapter.state, TargetPublicationState.REJECTED)

    def test_post_mpu_barrier_cannot_be_skipped(self):
        adapter, _, _, receipt = _prepared()
        adapter.verify(receipt)
        adapter.data_sync_before_mpu()
        adapter.apply_mpu_rx()
        with self.assertRaisesRegex(PublicationError, "order error"):
            adapter.instruction_sync_after_mpu()

    def test_instruction_barrier_cannot_precede_mpu(self):
        adapter, _, _, receipt = _prepared()
        adapter.verify(receipt)
        adapter.data_sync_before_mpu()
        with self.assertRaisesRegex(PublicationError, "order error"):
            adapter.instruction_sync_after_mpu()

    def test_post_seal_write_and_republish_are_rejected_without_mutation(self):
        adapter, _, _, receipt = _prepared()
        adapter.verify(receipt)
        adapter.data_sync_before_mpu()
        adapter.apply_mpu_rx()
        adapter.data_sync_after_mpu()
        published = adapter.instruction_sync_after_mpu()
        before = published.code
        with self.assertRaisesRegex(PublicationError, "order error"):
            adapter.write(0, b"\x00")
        self.assertEqual(adapter.state, TargetPublicationState.SEALED_RX)
        self.assertEqual(adapter.published().code, before)
        with self.assertRaisesRegex(PublicationError, "order error"):
            adapter.begin(_candidate(), _policy())

    def test_published_read_checks_bounds(self):
        adapter, candidate, _, receipt = _prepared()
        adapter.verify(receipt)
        adapter.data_sync_before_mpu()
        adapter.apply_mpu_rx()
        adapter.data_sync_after_mpu()
        published = adapter.instruction_sync_after_mpu()
        self.assertEqual(published.read(0, 2), candidate.code[:2])
        with self.assertRaisesRegex(PublicationError, "outside"):
            published.read(-1, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
