"""Host model of the RP2350 SRAM publication adapter.

This module models the target-side state transitions without programming an
MPU, flushing a cache, or executing generated code.  R0 accepts internal SRAM
only and makes publication a one-way rw,nx -> rx transition.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from min0_rp2350_integrated_publication import (
    IntegratedMachineAuditReceipt,
    IntegratedMachineCandidate,
    IntegratedPublicationPolicy,
    audit_integrated_candidate,
)
from min0_rp2350_publication import PublicationError


RP2350_SRAM_BASE = 0x2000_0000
RP2350_SRAM_END = 0x2008_2000
TARGET_PROFILE = "rp2350-sram-mpu/0.1"


class TargetPublicationState(Enum):
    EMPTY = "empty"
    STAGING_RW_NX = "staging-rw,nx"
    VERIFIED_RW_NX = "verified-rw,nx"
    PRE_MPU_DSB = "pre-mpu-dsb"
    RX_PENDING_DSB = "rx-pending-dsb"
    RX_PENDING_ISB = "rx-pending-isb"
    SEALED_RX = "sealed-rx"
    REJECTED = "rejected"


@dataclass(frozen=True)
class TargetPublishedImage:
    architecture: str
    word: str
    image_base: int
    code: bytes
    artifact_sha256: str
    target_profile: str
    events: tuple[str, ...]
    permissions: str = "rx"
    programmable: bool = False
    sealed: bool = True
    execution_authorized: bool = False

    def read(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > len(self.code):
            raise PublicationError("target published read is outside the image")
        return self.code[offset:offset + length]


class Rp2350TargetPublicationAdapter:
    """One-shot state machine for publishing audited bytes into RP2350 SRAM."""

    def __init__(self) -> None:
        self.state = TargetPublicationState.EMPTY
        self.permissions = "none"
        self.programmable = False
        self.execution_authorized = False
        self.events: list[str] = []
        self._candidate: IntegratedMachineCandidate | None = None
        self._policy: IntegratedPublicationPolicy | None = None
        self._storage = bytearray()
        self._written = bytearray()
        self._receipt: IntegratedMachineAuditReceipt | None = None
        self._published: TargetPublishedImage | None = None

    def begin(
        self,
        candidate: IntegratedMachineCandidate,
        policy: IntegratedPublicationPolicy,
    ) -> None:
        self._require(TargetPublicationState.EMPTY, "begin")
        image_end = candidate.image_base + len(candidate.code)
        if candidate.image_base < RP2350_SRAM_BASE or image_end > RP2350_SRAM_END:
            self._reject("target R0 publication requires RP2350 internal SRAM")
        if policy.image_base != candidate.image_base:
            self._reject("target policy and candidate image base differ")
        if policy.image_limit > RP2350_SRAM_END:
            self._reject("target policy extends beyond RP2350 internal SRAM")
        self._candidate = candidate
        self._policy = policy
        self._storage = bytearray(len(candidate.code))
        self._written = bytearray(len(candidate.code))
        self.state = TargetPublicationState.STAGING_RW_NX
        self.permissions = "rw,nx"
        self.programmable = True
        self.events.append("BEGIN_RW_NX")

    def write(self, offset: int, data: bytes) -> None:
        self._require(TargetPublicationState.STAGING_RW_NX, "write")
        if not data:
            self._reject("target staging write must not be empty")
        if offset < 0 or offset + len(data) > len(self._storage):
            self._reject("target staging write is outside the image")
        if any(self._written[offset:offset + len(data)]):
            self._reject("target staging bytes may be written only once")
        self._storage[offset:offset + len(data)] = data
        self._written[offset:offset + len(data)] = b"\x01" * len(data)
        self.events.append(f"WRITE:{offset}:{len(data)}")

    def verify(self, receipt: IntegratedMachineAuditReceipt) -> None:
        self._require(TargetPublicationState.STAGING_RW_NX, "verify")
        if not self._written or not all(self._written):
            self._reject("target staging image is incomplete")
        assert self._candidate is not None
        assert self._policy is not None
        snapshot = replace(self._candidate, code=bytes(self._storage))
        try:
            current = audit_integrated_candidate(snapshot, self._policy)
        except PublicationError as error:
            self._reject(f"target byte recheck failed: {error}")
        if current != receipt:
            self._reject("target receipt does not match the transferred image")
        self._receipt = current
        self.state = TargetPublicationState.VERIFIED_RW_NX
        self.events.append(f"VERIFY:{current.artifact_sha256}")

    def data_sync_before_mpu(self) -> None:
        self._advance(
            TargetPublicationState.VERIFIED_RW_NX,
            TargetPublicationState.PRE_MPU_DSB,
            "DSB_BEFORE_MPU",
        )

    def apply_mpu_rx(self) -> None:
        self._require(TargetPublicationState.PRE_MPU_DSB, "apply_mpu_rx")
        self.state = TargetPublicationState.RX_PENDING_DSB
        self.permissions = "rx,pending-sync"
        self.programmable = False
        self.events.append("MPU_APPLY_RX")

    def data_sync_after_mpu(self) -> None:
        self._advance(
            TargetPublicationState.RX_PENDING_DSB,
            TargetPublicationState.RX_PENDING_ISB,
            "DSB_AFTER_MPU",
        )

    def instruction_sync_after_mpu(self) -> TargetPublishedImage:
        self._require(TargetPublicationState.RX_PENDING_ISB, "instruction_sync_after_mpu")
        assert self._candidate is not None
        assert self._receipt is not None
        self.events.append("ISB_AFTER_MPU")
        self.state = TargetPublicationState.SEALED_RX
        self.permissions = "rx"
        self.programmable = False
        self._published = TargetPublishedImage(
            architecture=self._receipt.architecture,
            word=self._receipt.word,
            image_base=self._receipt.image_base,
            code=bytes(self._storage),
            artifact_sha256=self._receipt.artifact_sha256,
            target_profile=TARGET_PROFILE,
            events=tuple(self.events),
        )
        return self._published

    def published(self) -> TargetPublishedImage:
        self._require(TargetPublicationState.SEALED_RX, "published")
        assert self._published is not None
        return self._published

    def _advance(
        self,
        expected: TargetPublicationState,
        following: TargetPublicationState,
        event: str,
    ) -> None:
        self._require(expected, event.lower())
        self.state = following
        self.events.append(event)

    def _require(self, expected: TargetPublicationState, operation: str) -> None:
        if self.state is expected:
            return
        message = (
            f"target publication order error: {operation} requires "
            f"{expected.value}, got {self.state.value}"
        )
        if self.state is not TargetPublicationState.SEALED_RX:
            self.state = TargetPublicationState.REJECTED
            self.permissions = "none"
            self.programmable = False
            self.events.append(f"REJECT:{operation}")
        raise PublicationError(message)

    def _reject(self, message: str) -> None:
        self.state = TargetPublicationState.REJECTED
        self.permissions = "none"
        self.programmable = False
        self.events.append("REJECT")
        raise PublicationError(message)
