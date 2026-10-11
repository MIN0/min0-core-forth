"""Single-receipt RP2350 publication for main, helper thunks, and veneers.

R0.2 composes the already independent main/thunk and private-ABI veneer
auditors.  It deliberately publishes only an immutable, non-executable
snapshot; no call or execute operation is provided here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json

from min0_rp2350_disassembler import MachineAuditError, audit_private_abi_veneers
from min0_rp2350_publication import (
    LinkedMachineCandidate,
    MachineAuditReceipt,
    PublicationError,
    Rp2350PublicationPolicy,
    audit_publication_candidate,
    build_linked_candidate,
)
from min0_rp2350_veneer import (
    PrivateAbiVeneerImage,
    PrivateAbiVeneerPlan,
    emit_private_abi_veneers,
    link_private_abi_veneers,
    private_abi_symbol_addresses,
    private_abi_veneer_plans,
)
from min0_virtual_assembler_rp2350 import ARCHITECTURE, BackendPlan


ALIGNMENT_NOP = b"\x00\xBF"


@dataclass(frozen=True)
class IntegratedPublicationPolicy:
    image_base: int
    image_limit: int
    runtime_symbols: tuple[tuple[str, int], ...]
    architecture: str = ARCHITECTURE

    @classmethod
    def create(
        cls,
        *,
        image_base: int,
        image_limit: int,
        runtime_symbols: dict[str, int],
    ) -> "IntegratedPublicationPolicy":
        return cls(
            int(image_base),
            int(image_limit),
            tuple(sorted((str(name), int(address)) for name, address in runtime_symbols.items())),
        )

    def symbols(self) -> dict[str, int]:
        return dict(self.runtime_symbols)


@dataclass(frozen=True)
class IntegratedImageRegion:
    name: str
    offset: int
    size: int
    sha256: str


@dataclass(frozen=True)
class IntegratedMachineCandidate:
    linked: LinkedMachineCandidate
    veneer_plans: tuple[PrivateAbiVeneerPlan, ...]
    veneers: PrivateAbiVeneerImage
    image_base: int
    veneer_offset: int
    code: bytes
    runtime_symbols: tuple[tuple[str, int], ...]
    execution_authorized: bool = False

    def runtime_symbol_table(self) -> dict[str, int]:
        return dict(self.runtime_symbols)


@dataclass(frozen=True)
class IntegratedMachineAuditReceipt:
    format: str
    architecture: str
    word: str
    image_base: int
    image_size: int
    artifact_sha256: str
    policy_sha256: str
    linked_receipt_sha256: str
    regions: tuple[IntegratedImageRegion, ...]
    main_instruction_count: int
    thunk_count: int
    thunk_instruction_count: int
    veneer_count: int
    veneer_instruction_count: int
    byte_coverage: int
    execution_authorized: bool = False


@dataclass(frozen=True)
class IntegratedStagedImage:
    candidate: IntegratedMachineCandidate
    storage: bytearray
    permissions: str = "rw,nx"
    programmable: bool = True
    execution_authorized: bool = False

    def snapshot(self) -> IntegratedMachineCandidate:
        return replace(self.candidate, code=bytes(self.storage))

    def write(self, offset: int, data: bytes) -> None:
        if offset < 0 or offset + len(data) > len(self.storage):
            raise PublicationError("integrated staging write is outside the image")
        self.storage[offset:offset + len(data)] = data


@dataclass(frozen=True)
class IntegratedPublishedImage:
    architecture: str
    word: str
    image_base: int
    code: bytes
    artifact_sha256: str
    regions: tuple[IntegratedImageRegion, ...]
    permissions: str = "rx"
    programmable: bool = False
    sealed: bool = True
    execution_authorized: bool = False

    def read(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > len(self.code):
            raise PublicationError("integrated published read is outside the image")
        return self.code[offset:offset + length]


def build_integrated_candidate(
    plan: BackendPlan,
    capability_ids: dict[str, int],
    *,
    image_base: int,
    runtime_symbols: dict[str, int],
) -> IntegratedMachineCandidate:
    """Lay out main/thunks first and veneers at the following 4-byte boundary."""

    plans = private_abi_veneer_plans()
    unlinked_veneers = emit_private_abi_veneers()
    provisional_symbols = {
        name: (image_base + offset) | 1
        for name, offset in unlinked_veneers.labels.items()
    }
    preliminary = build_linked_candidate(
        plan,
        capability_ids,
        image_base=image_base,
        symbol_addresses=provisional_symbols,
    )
    veneer_base = _align_up(image_base + len(preliminary.fragment.code), 4)
    veneers = link_private_abi_veneers(
        unlinked_veneers,
        image_base=veneer_base,
        runtime_symbols=runtime_symbols,
    )
    helper_symbols = private_abi_symbol_addresses(veneers)
    linked = build_linked_candidate(
        plan,
        capability_ids,
        image_base=image_base,
        symbol_addresses=helper_symbols,
    )
    if len(linked.fragment.code) != len(preliminary.fragment.code):
        raise PublicationError("final helper addresses changed the linked image size")
    veneer_offset = veneer_base - image_base
    padding_size = veneer_offset - len(linked.fragment.code)
    if padding_size not in {0, 2}:
        raise PublicationError("integrated veneer alignment is not representable")
    code = linked.fragment.code + (ALIGNMENT_NOP if padding_size else b"") + veneers.code
    return IntegratedMachineCandidate(
        linked=linked,
        veneer_plans=plans,
        veneers=veneers,
        image_base=image_base,
        veneer_offset=veneer_offset,
        code=code,
        runtime_symbols=tuple(sorted((str(k), int(v)) for k, v in runtime_symbols.items())),
    )


def stage_integrated_candidate(
    candidate: IntegratedMachineCandidate,
) -> IntegratedStagedImage:
    return IntegratedStagedImage(candidate, bytearray(candidate.code))


def audit_integrated_staging(
    staging: IntegratedStagedImage,
    policy: IntegratedPublicationPolicy,
) -> IntegratedMachineAuditReceipt:
    if staging.permissions != "rw,nx" or staging.execution_authorized:
        raise PublicationError("integrated staging must remain writable and non-executable")
    return audit_integrated_candidate(staging.snapshot(), policy)


def audit_integrated_candidate(
    candidate: IntegratedMachineCandidate,
    policy: IntegratedPublicationPolicy,
) -> IntegratedMachineAuditReceipt:
    """Audit every byte and bind all component evidence into one receipt."""

    _verify_integrated_policy(policy)
    if candidate.execution_authorized:
        raise PublicationError("integrated candidate must not authorize execution")
    if candidate.image_base != policy.image_base:
        raise PublicationError("integrated image base is not approved")
    if candidate.runtime_symbols != policy.runtime_symbols:
        raise PublicationError("integrated runtime symbol table is not approved")
    if candidate.linked.image_base != candidate.image_base:
        raise PublicationError("linked main has the wrong image base")
    if candidate.veneers.image_base != candidate.image_base + candidate.veneer_offset:
        raise PublicationError("private veneers have the wrong image base")
    if candidate.veneers.execution_authorized or not candidate.veneers.link_complete:
        raise PublicationError("private veneers are not sealed for integrated audit")
    if candidate.veneer_offset % 4:
        raise PublicationError("private veneers are not 4-byte aligned")

    linked_code = candidate.linked.fragment.code
    padding = candidate.code[len(linked_code):candidate.veneer_offset]
    expected = linked_code + padding + candidate.veneers.code
    if candidate.code != expected:
        raise PublicationError("integrated image components do not match its bytes")
    if padding not in {b"", ALIGNMENT_NOP}:
        raise PublicationError("integrated alignment padding is not an audited NOP")
    image_end = candidate.image_base + len(candidate.code)
    if image_end > 0x1_0000_0000 or image_end > policy.image_limit:
        raise PublicationError("integrated image is outside the approved range")
    for name, address in candidate.runtime_symbols:
        target = address & ~1
        if candidate.image_base <= target < image_end:
            raise PublicationError(
                f"runtime symbol overlaps the generated image: {name}"
            )

    helper_symbols = private_abi_symbol_addresses(candidate.veneers)
    if candidate.linked.symbols() != helper_symbols:
        raise PublicationError("linked helper symbols do not name the integrated veneers")
    linked_policy = Rp2350PublicationPolicy.create(
        image_base=candidate.image_base,
        image_limit=policy.image_limit,
        approved_symbols=helper_symbols,
    )
    linked_receipt = audit_publication_candidate(candidate.linked, linked_policy)
    try:
        veneer_reports = audit_private_abi_veneers(
            candidate.veneer_plans,
            candidate.veneers,
            candidate.runtime_symbol_table(),
        )
    except MachineAuditError as error:
        raise PublicationError(str(error)) from error

    veneer_coverage = sum(
        instruction.size
        for report in veneer_reports.values()
        for instruction in report
    )
    if veneer_coverage != len(candidate.veneers.code):
        raise PublicationError("private veneer audit did not cover every byte")
    regions = _regions(candidate)
    if sum(region.size for region in regions) != len(candidate.code):
        raise PublicationError("integrated region map does not cover every byte")
    artifact_sha256 = _integrated_artifact_digest(candidate, regions)
    return IntegratedMachineAuditReceipt(
        format="min0-rp2350-integrated-machine-audit/0.2",
        architecture=policy.architecture,
        word=candidate.linked.plan.word,
        image_base=candidate.image_base,
        image_size=len(candidate.code),
        artifact_sha256=artifact_sha256,
        policy_sha256=_integrated_policy_digest(policy),
        linked_receipt_sha256=_linked_receipt_digest(linked_receipt),
        regions=regions,
        main_instruction_count=linked_receipt.main_instruction_count,
        thunk_count=linked_receipt.thunk_count,
        thunk_instruction_count=linked_receipt.thunk_instruction_count,
        veneer_count=len(veneer_reports),
        veneer_instruction_count=sum(len(report) for report in veneer_reports.values()),
        byte_coverage=linked_receipt.byte_coverage + len(padding) + veneer_coverage,
    )


def publish_integrated_staging(
    staging: IntegratedStagedImage,
    receipt: IntegratedMachineAuditReceipt,
    policy: IntegratedPublicationPolicy,
) -> IntegratedPublishedImage:
    if staging.permissions != "rw,nx" or staging.execution_authorized:
        raise PublicationError("integrated staging must remain non-executable")
    candidate = staging.snapshot()
    if receipt.execution_authorized:
        raise PublicationError("integrated R0.2 receipt must not authorize execution")
    if _integrated_policy_digest(policy) != receipt.policy_sha256:
        raise PublicationError("integrated publication policy changed after audit")
    fresh = audit_integrated_candidate(candidate, policy)
    if fresh.artifact_sha256 != receipt.artifact_sha256:
        raise PublicationError("integrated candidate changed after audit")
    if fresh != receipt:
        raise PublicationError("integrated receipt does not match the current candidate")
    return IntegratedPublishedImage(
        architecture=policy.architecture,
        word=candidate.linked.plan.word,
        image_base=candidate.image_base,
        code=bytes(candidate.code),
        artifact_sha256=receipt.artifact_sha256,
        regions=receipt.regions,
    )


def _regions(candidate: IntegratedMachineCandidate) -> tuple[IntegratedImageRegion, ...]:
    linked_code = candidate.linked.fragment.code
    thunk_offsets = [
        int(offset)
        for name, offset in candidate.linked.fragment.labels.items()
        if name.startswith("@helper-thunk-")
    ]
    thunk_start = min(thunk_offsets, default=len(linked_code))
    padding_start = len(linked_code)
    areas = (
        ("main", 0, thunk_start),
        ("helper-thunks-and-literals", thunk_start, len(linked_code) - thunk_start),
        ("alignment", padding_start, candidate.veneer_offset - padding_start),
        ("private-abi-veneers", candidate.veneer_offset, len(candidate.veneers.code)),
    )
    return tuple(
        IntegratedImageRegion(name, offset, size, hashlib.sha256(candidate.code[offset:offset + size]).hexdigest())
        for name, offset, size in areas
    )


def _integrated_artifact_digest(
    candidate: IntegratedMachineCandidate,
    regions: tuple[IntegratedImageRegion, ...],
) -> str:
    metadata = {
        "architecture": candidate.linked.fragment.architecture,
        "word": candidate.linked.plan.word,
        "image_base": candidate.image_base,
        "veneer_offset": candidate.veneer_offset,
        "linked_symbols": list(candidate.linked.symbol_addresses),
        "runtime_symbols": list(candidate.runtime_symbols),
        "regions": [(r.name, r.offset, r.size, r.sha256) for r in regions],
        "execution_authorized": False,
    }
    return _digest_metadata_and_code(metadata, candidate.code)


def _integrated_policy_digest(policy: IntegratedPublicationPolicy) -> str:
    metadata = {
        "architecture": policy.architecture,
        "image_base": policy.image_base,
        "image_limit": policy.image_limit,
        "runtime_symbols": list(policy.runtime_symbols),
        "execution_authorized": False,
    }
    return _digest_metadata_and_code(metadata, b"")


def _linked_receipt_digest(receipt: MachineAuditReceipt) -> str:
    return _digest_metadata_and_code(receipt.__dict__, b"")


def _digest_metadata_and_code(metadata: object, code: bytes) -> str:
    encoded = json.dumps(
        metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    digest = hashlib.sha256()
    digest.update(len(encoded).to_bytes(4, "little"))
    digest.update(encoded)
    digest.update(code)
    return digest.hexdigest()


def _verify_integrated_policy(policy: IntegratedPublicationPolicy) -> None:
    if policy.architecture != ARCHITECTURE:
        raise PublicationError("integrated policy has an unsupported architecture")
    if (
        policy.image_base < 0
        or policy.image_limit <= policy.image_base
        or policy.image_limit > 0x1_0000_0000
        or policy.image_base % 2
    ):
        raise PublicationError("integrated policy has an invalid image range")
    names = [name for name, _ in policy.runtime_symbols]
    if len(names) != len(set(names)):
        raise PublicationError("integrated policy repeats a runtime symbol")
    expected = {plan.runtime_symbol for plan in private_abi_veneer_plans()}
    if set(names) != expected:
        raise PublicationError("integrated policy runtime symbol set is incomplete")
    for name, address in policy.runtime_symbols:
        if not name or not 0 <= address <= 0xFFFF_FFFF or not address & 1:
            raise PublicationError("integrated policy has an invalid runtime symbol")


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) & -alignment
