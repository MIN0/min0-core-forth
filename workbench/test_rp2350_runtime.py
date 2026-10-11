import unittest

from min0_rp2350_runtime import (
    HelperStatus,
    Rp2350ExecutionContext,
    RuntimeCapability,
    min0_abort_transaction,
    min0_checked_ld32,
    min0_frame_commit,
    min0_frame_load,
    min0_result_stage,
    min0_stage_st32,
)
from min0_virtual_assembler import MemoryWindow


def _context(
    stack=(99, 10, 20, 0x1000), *, input_count=3, output_count=2,
    window=None,
):
    memory = window or MemoryWindow(0x1000, 16)
    return Rp2350ExecutionContext(
        list(stack), input_count, output_count,
        (RuntimeCapability(7, "DATA", memory),),
    ), memory


class Rp2350RuntimeHelperTests(unittest.TestCase):
    def test_successful_commit_atomically_replaces_inputs_and_writes_memory(self):
        context, memory = _context()
        self.assertEqual(min0_frame_load(context, 0), (HelperStatus.OK, 10))
        self.assertEqual(min0_frame_load(context, 2), (HelperStatus.OK, 0x1000))
        self.assertEqual(
            min0_stage_st32(context, 7, 0x1000, 4, 0x12345678),
            HelperStatus.OK,
        )
        self.assertEqual(min0_result_stage(context, 0, 30), HelperStatus.OK)
        self.assertEqual(min0_result_stage(context, 1, 40), HelperStatus.OK)
        self.assertEqual(memory.read32(0x1004), 0)
        self.assertEqual(context.data_stack, [99, 10, 20, 0x1000])

        self.assertEqual(min0_frame_commit(context, 3, 2), HelperStatus.OK)
        self.assertEqual(context.data_stack, [99, 30, 40])
        self.assertEqual(memory.read32(0x1004), 0x12345678)
        self.assertEqual(context.state, "committed")

    def test_pending_store_is_forwarded_to_checked_read_before_commit(self):
        context, memory = _context(output_count=0)
        memory.write32(0x1000, 7)
        self.assertEqual(
            min0_stage_st32(context, 7, 0x1000, 0, 88), HelperStatus.OK
        )
        self.assertEqual(
            min0_checked_ld32(context, 7, 0x1000, 0),
            (HelperStatus.OK, 88),
        )
        self.assertEqual(memory.read32(0x1000), 7)

    def test_abort_after_partial_sequence_restores_stack_and_memory(self):
        context, memory = _context()
        before_stack = list(context.data_stack)
        memory.write32(0x1000, 7)
        self.assertEqual(min0_result_stage(context, 0, 30), HelperStatus.OK)
        self.assertEqual(
            min0_stage_st32(context, 7, 0x1000, 0, 88), HelperStatus.OK
        )
        self.assertEqual(
            min0_abort_transaction(context, HelperStatus.ABORTED),
            HelperStatus.ABORTED,
        )
        self.assertEqual(context.data_stack, before_stack)
        self.assertEqual(memory.read32(0x1000), 7)
        self.assertEqual(context.pending_writes, {})
        self.assertEqual(context.staged_outputs, [None, None])

    def test_repeated_abort_is_idempotent(self):
        context, _ = _context(stack=(99, -1, 0x1_0000_0001, 0x1000))
        before = list(context.data_stack)
        self.assertEqual(
            min0_abort_transaction(context, HelperStatus.INPUT_INDEX),
            HelperStatus.INPUT_INDEX,
        )
        self.assertEqual(
            min0_abort_transaction(context, HelperStatus.WRITE_DENIED),
            HelperStatus.INPUT_INDEX,
        )
        self.assertEqual(context.state, "aborted")
        self.assertEqual(context.data_stack, before)

    def test_input_and_output_indexes_and_duplicate_output_are_rejected(self):
        context, _ = _context()
        self.assertEqual(min0_frame_load(context, 3)[0], HelperStatus.INPUT_INDEX)
        self.assertEqual(
            min0_result_stage(context, 0, 1), HelperStatus.INPUT_INDEX,
            "the first failure remains latched until abort",
        )
        min0_abort_transaction(context)

        context, _ = _context()
        self.assertEqual(min0_result_stage(context, 2, 1), HelperStatus.OUTPUT_INDEX)
        context, _ = _context()
        self.assertEqual(min0_result_stage(context, 0, 1), HelperStatus.OK)
        self.assertEqual(
            min0_result_stage(context, 0, 2), HelperStatus.OUTPUT_DUPLICATE
        )

    def test_commit_rejects_wrong_counts_and_missing_output_without_mutation(self):
        for expected in (HelperStatus.CONTRACT_MISMATCH, HelperStatus.OUTPUT_MISSING):
            with self.subTest(expected=expected):
                context, memory = _context()
                before = list(context.data_stack)
                min0_stage_st32(context, 7, 0x1000, 0, 55)
                if expected == HelperStatus.CONTRACT_MISMATCH:
                    status = min0_frame_commit(context, 2, 2)
                else:
                    min0_result_stage(context, 0, 1)
                    status = min0_frame_commit(context, 3, 2)
                self.assertEqual(status, expected)
                self.assertEqual(context.data_stack, before)
                self.assertEqual(memory.read32(0x1000), 0)
                self.assertEqual(min0_abort_transaction(context), expected)

    def test_unknown_unaligned_out_of_range_and_overflow_addresses_are_rejected(self):
        cases = (
            ((99, 0x1000, 0), HelperStatus.UNKNOWN_CAPABILITY),
            ((7, 0x1000, 2), HelperStatus.UNALIGNED_ADDRESS),
            ((7, 0x1000, 16), HelperStatus.ADDRESS_RANGE),
            ((7, 0xFFFF_FFFC, 4), HelperStatus.ADDRESS_OVERFLOW),
        )
        for arguments, expected in cases:
            with self.subTest(expected=expected):
                context, _ = _context()
                status, value = min0_checked_ld32(context, *arguments)
                self.assertEqual((status, value), (expected, 0))

    def test_read_and_write_permissions_are_independent(self):
        unreadable = MemoryWindow(0x1000, 4, readable=False, writable=True)
        context, _ = _context(window=unreadable)
        self.assertEqual(
            min0_checked_ld32(context, 7, 0x1000, 0)[0],
            HelperStatus.READ_DENIED,
        )
        readonly = MemoryWindow(0x1000, 4, readable=True, writable=False)
        context, _ = _context(window=readonly)
        self.assertEqual(
            min0_stage_st32(context, 7, 0x1000, 0, 1),
            HelperStatus.WRITE_DENIED,
        )

    def test_zero_input_and_output_contract_commits_without_stack_change(self):
        context = Rp2350ExecutionContext([1, 2], 0, 0)
        self.assertEqual(min0_frame_commit(context, 0, 0), HelperStatus.OK)
        self.assertEqual(context.data_stack, [1, 2])

    def test_helpers_cannot_reopen_a_committed_transaction(self):
        context = Rp2350ExecutionContext([1], 1, 0)
        self.assertEqual(min0_frame_commit(context, 1, 0), HelperStatus.OK)
        self.assertEqual(
            min0_result_stage(context, 0, 99), HelperStatus.INVALID_STATE
        )
        self.assertEqual(
            min0_abort_transaction(context, HelperStatus.ABORTED),
            HelperStatus.INVALID_STATE,
        )
        self.assertEqual(context.data_stack, [])

    def test_access_failure_then_abort_preserves_original_state(self):
        readonly = MemoryWindow(
            0x1000, 4, readable=True, writable=False,
            initial=(7).to_bytes(4, "little"),
        )
        context, memory = _context(window=readonly)
        before = list(context.data_stack)
        status = min0_stage_st32(context, 7, 0x1000, 0, 99)
        self.assertEqual(status, HelperStatus.WRITE_DENIED)
        self.assertEqual(min0_abort_transaction(context, status), status)
        self.assertEqual(context.data_stack, before)
        self.assertEqual(memory.read32(0x1000), 7)

    def test_context_construction_rejects_underflow_and_duplicate_capabilities(self):
        with self.assertRaisesRegex(ValueError, "declared input frame"):
            Rp2350ExecutionContext([1], 2, 0)
        window = MemoryWindow(0, 4)
        duplicate = (
            RuntimeCapability(1, "A", window),
            RuntimeCapability(1, "B", window),
        )
        with self.assertRaisesRegex(ValueError, "must be unique"):
            Rp2350ExecutionContext([], 0, 0, duplicate)

    def test_context_rejects_wrong_helper_abi_version(self):
        with self.assertRaisesRegex(ValueError, "ABI version mismatch"):
            Rp2350ExecutionContext([], 0, 0, abi_version="wrong/0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
