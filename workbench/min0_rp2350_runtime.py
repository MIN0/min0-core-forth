"""Host reference model for the MIN0 RP2350 private helper ABI 0.2.

This module models the transactional behavior required from the future target
runtime.  It does not execute generated RP2350 machine code and deliberately
keeps the caller's FORTH DATA stack and memory unchanged until FRAME_COMMIT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from min0_virtual_assembler import CELL_MASK, MemoryWindow
from min0_virtual_assembler_rp2350 import HELPER_ABI_VERSION


class HelperStatus(IntEnum):
    OK = 0
    INVALID_STATE = 1
    INPUT_INDEX = 2
    OUTPUT_INDEX = 3
    OUTPUT_DUPLICATE = 4
    OUTPUT_MISSING = 5
    CONTRACT_MISMATCH = 6
    UNKNOWN_CAPABILITY = 7
    ADDRESS_OVERFLOW = 8
    UNALIGNED_ADDRESS = 9
    ADDRESS_RANGE = 10
    READ_DENIED = 11
    WRITE_DENIED = 12
    ABORTED = 13
    PENDING_FULL = 14


@dataclass(frozen=True)
class RuntimeCapability:
    """Numeric capability ID bound to one checked memory window."""

    identifier: int
    name: str
    window: MemoryWindow

    def __post_init__(self) -> None:
        if not 0 <= self.identifier <= CELL_MASK:
            raise ValueError("capability identifier must be a 32-bit value")
        if not self.name:
            raise ValueError("capability name must not be empty")


@dataclass
class Rp2350ExecutionContext:
    """One invocation's stack frame and staged memory transaction."""

    data_stack: list[int]
    input_count: int
    output_count: int
    capabilities: tuple[RuntimeCapability, ...] = ()
    abi_version: str = HELPER_ABI_VERSION
    input_frame: tuple[int, ...] = field(init=False)
    original_stack: tuple[int, ...] = field(init=False)
    staged_outputs: list[int | None] = field(init=False)
    pending_writes: dict[tuple[int, int], int] = field(default_factory=dict)
    status: HelperStatus = HelperStatus.OK
    state: str = "active"

    def __post_init__(self) -> None:
        if self.abi_version != HELPER_ABI_VERSION:
            raise ValueError("execution context helper ABI version mismatch")
        if self.input_count < 0 or self.output_count < 0:
            raise ValueError("frame counts must not be negative")
        if len(self.data_stack) < self.input_count:
            raise ValueError("DATA stack does not contain the declared input frame")
        ids = [capability.identifier for capability in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("capability identifiers must be unique")
        self.original_stack = tuple(self.data_stack)
        if self.input_count:
            self.input_frame = tuple(
                value & CELL_MASK
                for value in self.original_stack[-self.input_count:]
            )
        else:
            self.input_frame = ()
        self.staged_outputs = [None] * self.output_count

    def capability(self, identifier: int) -> RuntimeCapability | None:
        return next(
            (item for item in self.capabilities if item.identifier == identifier),
            None,
        )


def min0_frame_load(
    context: Rp2350ExecutionContext, input_index: int,
) -> tuple[HelperStatus, int]:
    status = _active_status(context)
    if status:
        return status, 0
    if not 0 <= input_index < context.input_count:
        return _fail(context, HelperStatus.INPUT_INDEX), 0
    return HelperStatus.OK, context.input_frame[input_index]


def min0_result_stage(
    context: Rp2350ExecutionContext, output_index: int, value: int,
) -> HelperStatus:
    status = _active_status(context)
    if status:
        return status
    if not 0 <= output_index < context.output_count:
        return _fail(context, HelperStatus.OUTPUT_INDEX)
    if context.staged_outputs[output_index] is not None:
        return _fail(context, HelperStatus.OUTPUT_DUPLICATE)
    context.staged_outputs[output_index] = value & CELL_MASK
    return HelperStatus.OK


def min0_checked_ld32(
    context: Rp2350ExecutionContext,
    capability_id: int,
    base: int,
    offset: int,
) -> tuple[HelperStatus, int]:
    status = _active_status(context)
    if status:
        return status, 0
    resolved = _checked_address(context, capability_id, base, offset, write=False)
    if isinstance(resolved, HelperStatus):
        return resolved, 0
    capability, address = resolved
    key = (capability.identifier, address)
    if key in context.pending_writes:
        return HelperStatus.OK, context.pending_writes[key]
    window_offset = address - capability.window.base
    value = int.from_bytes(
        capability.window.data[window_offset:window_offset + 4], "little"
    )
    return HelperStatus.OK, value


def min0_stage_st32(
    context: Rp2350ExecutionContext,
    capability_id: int,
    base: int,
    offset: int,
    value: int,
) -> HelperStatus:
    status = _active_status(context)
    if status:
        return status
    resolved = _checked_address(context, capability_id, base, offset, write=True)
    if isinstance(resolved, HelperStatus):
        return resolved
    capability, address = resolved
    context.pending_writes[(capability.identifier, address)] = value & CELL_MASK
    return HelperStatus.OK


def min0_frame_commit(
    context: Rp2350ExecutionContext, input_count: int, output_count: int,
) -> HelperStatus:
    status = _active_status(context)
    if status:
        return status
    if (input_count, output_count) != (context.input_count, context.output_count):
        return _fail(context, HelperStatus.CONTRACT_MISMATCH)
    if any(value is None for value in context.staged_outputs):
        return _fail(context, HelperStatus.OUTPUT_MISSING)

    # Every access was checked while staging.  Snapshot the small affected set
    # as a defensive host-model proof that commit itself is all-or-nothing.
    originals: dict[tuple[int, int], bytes] = {}
    try:
        for (identifier, address), value in context.pending_writes.items():
            capability = context.capability(identifier)
            if capability is None:  # Context mutation must not weaken atomicity.
                raise RuntimeError("staged capability disappeared")
            start = address - capability.window.base
            originals[(identifier, address)] = bytes(
                capability.window.data[start:start + 4]
            )
            capability.window.data[start:start + 4] = value.to_bytes(4, "little")
    except Exception:
        for (identifier, address), original in originals.items():
            capability = context.capability(identifier)
            if capability is not None:
                start = address - capability.window.base
                capability.window.data[start:start + 4] = original
        return _fail(context, HelperStatus.INVALID_STATE)

    prefix_length = len(context.original_stack) - context.input_count
    committed = list(context.original_stack[:prefix_length])
    committed.extend(int(value) for value in context.staged_outputs if value is not None)
    context.data_stack[:] = committed
    context.pending_writes.clear()
    context.state = "committed"
    return HelperStatus.OK


def min0_abort_transaction(
    context: Rp2350ExecutionContext,
    status: HelperStatus | int | None = None,
) -> HelperStatus:
    """Discard all staging; repeated aborts return the original abort status."""

    if context.state == "committed":
        return HelperStatus.INVALID_STATE
    if context.state == "aborted":
        return context.status
    requested = HelperStatus(status) if status is not None else context.status
    if requested == HelperStatus.OK:
        requested = HelperStatus.ABORTED
    context.status = requested
    context.pending_writes.clear()
    context.staged_outputs[:] = [None] * context.output_count
    context.data_stack[:] = context.original_stack
    context.state = "aborted"
    return requested


def _active_status(context: Rp2350ExecutionContext) -> HelperStatus:
    if context.state != "active":
        return context.status if context.status else HelperStatus.INVALID_STATE
    return context.status


def _fail(
    context: Rp2350ExecutionContext, status: HelperStatus,
) -> HelperStatus:
    if context.status == HelperStatus.OK:
        context.status = status
    return context.status


def _checked_address(
    context: Rp2350ExecutionContext,
    capability_id: int,
    base: int,
    offset: int,
    *,
    write: bool,
) -> tuple[RuntimeCapability, int] | HelperStatus:
    capability = context.capability(capability_id)
    if capability is None:
        return _fail(context, HelperStatus.UNKNOWN_CAPABILITY)
    if not 0 <= base <= CELL_MASK:
        return _fail(context, HelperStatus.ADDRESS_OVERFLOW)
    address = base + offset
    if not 0 <= address <= CELL_MASK or address + 4 > 0x1_0000_0000:
        return _fail(context, HelperStatus.ADDRESS_OVERFLOW)
    if address % 4:
        return _fail(context, HelperStatus.UNALIGNED_ADDRESS)
    window = capability.window
    if address < window.base or address + 4 > window.base + window.size:
        return _fail(context, HelperStatus.ADDRESS_RANGE)
    if write and not window.writable:
        return _fail(context, HelperStatus.WRITE_DENIED)
    if not write and not window.readable:
        return _fail(context, HelperStatus.READ_DENIED)
    return capability, address
