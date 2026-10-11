"""Audited, non-executing publication gate for linked RP2350 fragments.

R0 deliberately stops after producing an immutable rx snapshot.  It does not
provide a call or execute operation; real RP2350 execution remains a later gate.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

from min0_rp2350_disassembler import (
    DecodedInstruction,
    MachineAuditError,
    audit_linked_helper_thunks,
    audit_linked_main,
)
from min0_rp2350_linker import (
    HelperThunkPlan,
    emit_helper_thunks,
    link_function_frame,
    link_internal_branches,
    plan_helper_thunks,
    prepare_link,
    resolve_external_branches,
)
from min0_rp2350_thumb_emitter import (
    MachineFragment,
    emit_thumb_fragment,
    verify_machine_fragment,
)
from min0_virtual_assembler import VerifyError
from min0_virtual_assembler_rp2350 import (
    ARCHITECTURE,
    BackendPlan,
    verify_backend_plan,
)


class PublicationError(VerifyError):
    pass


@dataclass(frozen=True)
class Rp2350PublicationPolicy:
    image_base: int
    image_limit: int
    approved_symbols: tuple[tuple[str, int], ...]
    architecture: str = ARCHITECTURE

    @classmethod
    def create(
        cls,
        *,
        image_base: int,
        image_limit: int,
        approved_symbols: dict[str, int],
    ) -> "Rp2350PublicationPolicy":
        return cls(
            image_base,
            image_limit,
            tuple(sorted((str(name), int(address)) for name, address in approved_symbols.items())),
        )

    def symbols(self) -> dict[str, int]:
        return dict(self.approved_symbols)


@dataclass(frozen=True)
class LinkedMachineCandidate:
    plan: BackendPlan
    fragment: MachineFragment
    main_size: int
    thunk_plans: tuple[HelperThunkPlan, ...]
    image_base: int
    symbol_addresses: tuple[tuple[str, int], ...]

    def symbols(self) -> dict[str, int]:
        return dict(self.symbol_addresses)


@dataclass(frozen=True)
class MachineAuditReceipt:
    format: str
    architecture: str
    word: str
    image_base: int
    image_size: int
    main_size: int
    artifact_sha256: str
    policy_sha256: str
    main_instruction_count: int
    thunk_count: int
    thunk_instruction_count: int
    byte_coverage: int
    execution_authorized: bool = False


@dataclass(frozen=True)
class StagedMachineImage:
    candidate: LinkedMachineCandidate
    storage: bytearray
    permissions: str = "rw,nx"
    programmable: bool = True
    execution_authorized: bool = False

    def snapshot(self) -> LinkedMachineCandidate:
        return replace_candidate_code(self.candidate, bytes(self.storage))

    def write(self, offset: int, data: bytes) -> None:
        if offset < 0 or offset + len(data) > len(self.storage):
            raise PublicationError("staging write is outside the machine image")
        self.storage[offset:offset + len(data)] = data


@dataclass(frozen=True)
class PublishedMachineImage:
    architecture: str
    word: str
    image_base: int
    code: bytes
    artifact_sha256: str
    permissions: str = "rx"
    programmable: bool = False
    sealed: bool = True
    execution_authorized: bool = False

    def read(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > len(self.code):
            raise PublicationError("published machine read is outside the image")
        return self.code[offset:offset + length]


def build_linked_candidate(
    plan: BackendPlan,
    capability_ids: dict[str, int],
    *,
    image_base: int,
    symbol_addresses: dict[str, int],
) -> LinkedMachineCandidate:
    """Run the approved R0 link sequence without granting publication."""

    verify_backend_plan(plan)
    original = emit_thumb_fragment(plan)
    main_size = len(original.code)
    prepared = link_internal_branches(link_function_frame(prepare_link(original)))
    thunk_plans = plan_helper_thunks(prepared, capability_ids)
    linked = resolve_external_branches(
        emit_helper_thunks(prepared, capability_ids),
        image_base,
        symbol_addresses,
    )
    return LinkedMachineCandidate(
        plan,
        linked,
        main_size,
        thunk_plans,
        image_base,
        tuple(sorted((str(name), int(address)) for name, address in symbol_addresses.items())),
    )


def stage_linked_candidate(candidate: LinkedMachineCandidate) -> StagedMachineImage:
    """Copy linked bytes into writable, explicitly non-executable staging."""

    return StagedMachineImage(candidate, bytearray(candidate.fragment.code))


def audit_staged_image(
    staging: StagedMachineImage,
    policy: Rp2350PublicationPolicy,
) -> MachineAuditReceipt:
    if staging.permissions != "rw,nx" or staging.execution_authorized:
        raise PublicationError("machine staging must remain writable and non-executable")
    return audit_publication_candidate(staging.snapshot(), policy)


def audit_publication_candidate(
    candidate: LinkedMachineCandidate,
    policy: Rp2350PublicationPolicy,
) -> MachineAuditReceipt:
    """Prove every linked byte belongs to the reviewed plan or its literal data."""

    _verify_policy(policy)
    verify_backend_plan(candidate.plan)
    verify_machine_fragment(candidate.fragment)
    if candidate.plan.architecture != policy.architecture:
        raise PublicationError("backend plan architecture is not approved")
    if candidate.fragment.architecture != policy.architecture:
        raise PublicationError("machine fragment architecture is not approved")
    if candidate.image_base != policy.image_base:
        raise PublicationError("machine image base is not approved")
    if candidate.symbol_addresses != policy.approved_symbols:
        raise PublicationError("machine helper symbol table is not approved")
    if candidate.fragment.relocations:
        raise PublicationError("machine fragment still has unresolved relocations")
    if not candidate.fragment.executable:
        raise PublicationError("machine fragment is not link complete")
    image_end = candidate.image_base + len(candidate.fragment.code)
    if image_end > 0x1_0000_0000 or image_end > policy.image_limit:
        raise PublicationError("machine fragment is outside the approved image range")

    symbols = candidate.symbols()
    try:
        main_report = audit_linked_main(
            candidate.plan,
            candidate.fragment,
            candidate.main_size,
            image_base=candidate.image_base,
        )
        thunk_reports = audit_linked_helper_thunks(
            candidate.thunk_plans,
            candidate.fragment,
            symbols,
            image_base=candidate.image_base,
        )
    except MachineAuditError as error:
        raise PublicationError(str(error)) from error

    required_symbols = _required_symbols(candidate.thunk_plans)
    missing = sorted(required_symbols - symbols.keys())
    if missing:
        raise PublicationError(
            "approved helper symbol table is incomplete: " + ", ".join(missing)
        )
    coverage = _audit_complete_byte_coverage(
        candidate,
        main_report,
        tuple(thunk_reports.values()),
    )
    artifact_sha256 = _artifact_digest(candidate)
    return MachineAuditReceipt(
        format="min0-rp2350-machine-audit/0.1",
        architecture=policy.architecture,
        word=candidate.plan.word,
        image_base=candidate.image_base,
        image_size=len(candidate.fragment.code),
        main_size=candidate.main_size,
        artifact_sha256=artifact_sha256,
        policy_sha256=_policy_digest(policy),
        main_instruction_count=len(main_report),
        thunk_count=len(thunk_reports),
        thunk_instruction_count=sum(len(report) for report in thunk_reports.values()),
        byte_coverage=coverage,
    )


def publish_audited_candidate(
    candidate: LinkedMachineCandidate,
    receipt: MachineAuditReceipt,
    policy: Rp2350PublicationPolicy,
) -> PublishedMachineImage:
    """Copy an unchanged audited candidate into an immutable rx snapshot."""

    if receipt.execution_authorized:
        raise PublicationError("R0 audit receipt must not authorize execution")
    if _artifact_digest(candidate) != receipt.artifact_sha256:
        raise PublicationError("machine candidate changed after audit")
    if _policy_digest(policy) != receipt.policy_sha256:
        raise PublicationError("machine publication policy changed after audit")
    fresh = audit_publication_candidate(candidate, policy)
    if fresh != receipt:
        raise PublicationError("machine audit receipt does not match current candidate")
    return PublishedMachineImage(
        architecture=candidate.fragment.architecture,
        word=candidate.plan.word,
        image_base=candidate.image_base,
        code=bytes(candidate.fragment.code),
        artifact_sha256=receipt.artifact_sha256,
    )


def publish_audited_staging(
    staging: StagedMachineImage,
    receipt: MachineAuditReceipt,
    policy: Rp2350PublicationPolicy,
) -> PublishedMachineImage:
    """Publish only the current audited staging snapshot into detached rx bytes."""

    if staging.permissions != "rw,nx" or staging.execution_authorized:
        raise PublicationError("machine staging must remain non-executable")
    return publish_audited_candidate(staging.snapshot(), receipt, policy)


def replace_candidate_code(
    candidate: LinkedMachineCandidate,
    code: bytes,
) -> LinkedMachineCandidate:
    """Create a metadata-preserving snapshot without mutating the linked candidate."""

    return LinkedMachineCandidate(
        candidate.plan,
        MachineFragment(
            candidate.fragment.architecture,
            bytes(code),
            candidate.fragment.relocations,
            dict(candidate.fragment.labels),
        ),
        candidate.main_size,
        candidate.thunk_plans,
        candidate.image_base,
        candidate.symbol_addresses,
    )


def _verify_policy(policy: Rp2350PublicationPolicy) -> None:
    if policy.architecture != ARCHITECTURE:
        raise PublicationError("publication policy has an unsupported architecture")
    if (
        policy.image_base < 0
        or policy.image_limit <= policy.image_base
        or policy.image_limit > 0x1_0000_0000
        or policy.image_base % 2
    ):
        raise PublicationError("publication policy has an invalid image range")
    names = [name for name, _ in policy.approved_symbols]
    if len(names) != len(set(names)):
        raise PublicationError("publication policy repeats a helper symbol")
    for name, address in policy.approved_symbols:
        if not name or not 0 <= address <= 0xFFFF_FFFF:
            raise PublicationError("publication policy has an invalid helper symbol")


def _required_symbols(plans: tuple[HelperThunkPlan, ...]) -> set[str]:
    required: set[str] = set()
    for plan in plans:
        if plan.helper_symbol:
            required.add(plan.helper_symbol)
        for instruction in plan.instructions:
            if instruction.opcode == "BL":
                required.add(str(instruction.operands[0]))
            elif instruction.opcode == "ABORT_IF_NONZERO":
                required.add(str(instruction.operands[1]))
    return required


def _audit_complete_byte_coverage(
    candidate: LinkedMachineCandidate,
    main_report: tuple[DecodedInstruction, ...],
    thunk_reports: tuple[tuple[DecodedInstruction, ...], ...],
) -> int:
    code = candidate.fragment.code
    covered = bytearray(len(code))
    literal_starts: set[int] = set()

    def mark(start: int, length: int, description: str) -> None:
        if start < 0 or length <= 0 or start + length > len(code):
            raise PublicationError(f"{description} is outside the machine image")
        if any(covered[start:start + length]):
            raise PublicationError(f"{description} overlaps another audited object")
        covered[start:start + length] = b"\x01" * length

    reports: Iterable[tuple[DecodedInstruction, ...]] = (main_report,) + thunk_reports
    for report in reports:
        for instruction in report:
            mark(instruction.offset, instruction.size, "decoded instruction")
            if instruction.mnemonic == "LDR_LITERAL":
                literal_offset = int(instruction.operands[1]) - candidate.image_base
                literal_starts.add(literal_offset)

    for literal_offset in sorted(literal_starts):
        if literal_offset % 4:
            raise PublicationError("literal pool cell is not 4-byte aligned")
        mark(literal_offset, 4, "literal pool cell")

    object_starts = set(literal_starts)
    object_starts.update(
        int(offset)
        for name, offset in candidate.fragment.labels.items()
        if name.startswith("@helper-thunk-")
    )
    for offset in range(0, len(code), 2):
        if covered[offset]:
            continue
        if (
            offset + 2 <= len(code)
            and offset % 4 == 2
            and offset + 2 in object_starts
            and code[offset:offset + 2] == b"\x00\xBF"
        ):
            mark(offset, 2, "alignment NOP")
            continue
        raise PublicationError(f"machine byte at offset {offset} is not independently audited")
    return sum(covered)


def _artifact_digest(candidate: LinkedMachineCandidate) -> str:
    metadata = {
        "architecture": candidate.fragment.architecture,
        "word": candidate.plan.word,
        "image_base": candidate.image_base,
        "main_size": candidate.main_size,
        "labels": sorted(candidate.fragment.labels.items()),
        "symbols": list(candidate.symbol_addresses),
        "code_size": len(candidate.fragment.code),
    }
    encoded = json.dumps(
        metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    digest = hashlib.sha256()
    digest.update(len(encoded).to_bytes(4, "little"))
    digest.update(encoded)
    digest.update(candidate.fragment.code)
    return digest.hexdigest()


def _policy_digest(policy: Rp2350PublicationPolicy) -> str:
    encoded = json.dumps(
        {
            "architecture": policy.architecture,
            "image_base": policy.image_base,
            "image_limit": policy.image_limit,
            "approved_symbols": list(policy.approved_symbols),
            "execution_authorized": False,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()
